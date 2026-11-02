"""Offline tests for the D125 1.0 confirmation runner (D123 + stage B runners, patched), on
a tiny synthetic dataset in LongMemEval's shape. Never uses the owner's key, ledger or
the real dataset."""

import asyncio
import hashlib
import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine import assemble_context
from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.models import KeyedPins
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import AnthropicTransport

spec = importlib.util.spec_from_file_location(
    "longmemeval_v1_live",
    Path(__file__).resolve().parents[1] / "scripts/longmemeval_v1_live.py",
)
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
v1.patch()
live = v1.b

FABLE, OPUS = "claude-fable-5-1", "claude-opus-5-5"
TYPES = ("knowledge-update", "multi-session", "temporal-reasoning")
FILLER = "We talked about the weather and a recipe for soup, nothing else of note."


def item(number, kind):
    code = f"code-{number:02d}"
    sessions = [
        [{"role": "user", "content": f"{FILLER} {i}"}, {"role": "assistant", "content": "Ok."}]
        for i in range(40)
    ]
    sessions[3][0] = {"role": "user", "content": f"My locker code is {code}.", "has_answer": True}
    return {
        "question_id": f"q{number:02d}",
        "question_type": kind,
        "question": f"What is my locker code, question {number}?",
        "question_date": "2023/06/30 (Fri) 23:40",
        "answer": code,
        "answer_session_ids": ["s3"],
        "haystack_dates": [f"2023/05/{1 + i % 28:02d} (Wed) {10 + i // 28}:00" for i in range(40)],
        "haystack_session_ids": [f"s{i}" for i in range(40)],
        "haystack_sessions": sessions,
    }


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    items = [item(n, TYPES[n % 3]) for n in range(6)]
    data = tmp_path / "longmemeval.json"
    data.write_text(json.dumps(items))
    monkeypatch.setattr(live.lme, "DATA", data)
    monkeypatch.setattr(live.lme, "SHA256", hashlib.sha256(data.read_bytes()).hexdigest())
    for module in (v1, live):
        monkeypatch.setattr(module, "QUESTIONS", 6)
        monkeypatch.setattr(module, "ANSWERS", 12)
        monkeypatch.setattr(module, "MAX_CALLS", 24)
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "PUBLIC", tmp_path / "public")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")

    async def forbidden(*args, **kwargs):
        pytest.fail("No network in runner tests")

    monkeypatch.setattr(AnthropicTransport, "send", forbidden)
    clock = [time.time()]
    fake_time = SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    monkeypatch.setattr(live, "time", fake_time)

    async def advance(seconds):
        clock[0] += seconds

    store = RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    questions, slots, requests, contexts = live.build()
    manifest = live.identity(slots)
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return SimpleNamespace(
        questions=questions,
        slots=slots,
        items={q["question_id"]: q for q in questions},
        manifest=manifest,
        requests=requests,
        contexts=contexts,
        store=store,
        advance=advance,
        clock=fake_time,
    )


class FakeTransport:
    namespace = AnthropicTransport().namespace

    def __init__(self, questions, failure=None, at=(), wrong_arm=None):
        self.calls, self.failure, self.at, self.payloads = 0, failure, at, []
        self.answers = {q["question"]: q["answer"] for q in questions}
        self.wrong_arm = wrong_arm

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        self.payloads.append(payload)
        assert api_key == "test-only" and "temperature" not in payload
        if self.calls in self.at and self.failure == "empty_response":
            raise TransportFailure("empty_response", uncertain=False, usage=Usage(900, 60, 0, 0))
        if self.calls in self.at:
            raise TransportFailure(self.failure, uncertain=False)
        if payload["model"] == OPUS:
            assert payload["max_tokens"] == 2048
            text = payload["messages"][0]["content"][0]["text"]
            verdict = "no" if "Model Response: wrong" in text else "yes"
            return Completion(OPUS, f"t-{self.calls}", verdict, "stop", Usage(300, 1))
        assert payload["model"] == FABLE and payload["max_tokens"] == 8192
        answer = self.answers[payload["messages"][-1]["content"][-1]["text"]]
        # Answer calls alternate arms: even = new_default, odd = old_default.
        arm = "old_default" if (self.calls - 1) % 2 else "new_default"
        reply = "wrong" if arm == self.wrong_arm else answer
        return Completion(FABLE, f"t-{self.calls}", reply, "stop", Usage(900, 6, 0, 0))


def run(x, transport, **kwargs):
    clients = [
        ProviderClient(
            store=x.store,
            quota=live.POLICY,
            prices=prices,
            api_key="test-only",
            generation=generation,
            retries=live.RETRIES,
            transport=transport,
            clock=x.clock.time,
        )
        for generation, prices in ((v1.ANSWER, v1.ANSWER_PRICES), (v1.JUDGE, v1.JUDGE_PRICES))
    ]
    return asyncio.run(
        live.dispatch(x.manifest, x.requests, x.items, clients, sleep=x.advance, **kwargs)
    )


def test_settings_reuse_d123_models_and_stage_b_prompt():
    stage_b = v1._load("longmemeval_accuracy_live_b")  # Unpatched copy.
    assert v1.ARMS["old_default"] == stage_b.ARMS["core_default"]
    assert (v1.ANSWER, v1.JUDGE) == (v1.c.ANSWER, v1.c.JUDGE)
    assert (v1.ANSWER.model, v1.JUDGE.model) == (FABLE, OPUS)
    assert live.SYSTEM == stage_b.SYSTEM and live.JUDGE_TEMPLATES == stage_b.JUDGE_TEMPLATES
    assert live.LEDGER not in (stage_b.LEDGER, v1.c.LEDGER) and live.RUN_ID == v1.RUN_ID
    assert live.POLICY.daily_budget_microusd == v1.CAP_MICROUSD == 90_000_000
    assert live.POLICY.billing_mode == "metered" and live.RETRIES.max_attempts == 1
    assert v1.MAX_CALLS == 1880 <= v1.TOTAL_CALLS == live.POLICY.rpd
    assert v1.QUESTIONS == 470 and v1.ANSWERS == 940


def test_new_default_arm_passes_no_retrieval_settings(experiment):
    q = experiment.questions[0]
    result, _, _ = v1.assemble(q, "new_default")
    turns, _ = live.lme.history(q)
    explicit = assemble_context(
        turns,
        q["question"],
        KeyedPins(live.lme.SCOPE),
        BudgetConfig(
            input_cap=3000,
            retrieval_reserve=1200,
            completion_reservation=8192,
        ),
        system=live.SYSTEM.format(date=q["question_date"]),
        at=live.lme.parse_date(q["question_date"]),
        retrieval_config=RetrievalConfig(top_k=13),
        diverse_turns=True,
    )
    assert result.request == explicit.request
    assert result.diagnostics.config_fingerprint == explicit.diagnostics.config_fingerprint
    old, _, _ = v1.assemble(q, "old_default")
    assert old.diagnostics.config_fingerprint != result.diagnostics.config_fingerprint


def test_plan_reports_expected_and_worst_case(experiment):
    plan = live.plan(experiment.questions, experiment.slots)
    assert plan["calls"] == 24 and set(plan["arms"]) == set(v1.ARMS)
    assert plan["expected_microusd_at_d123_usage"] == v1.expected_total() > 0
    assert plan["worst_case_all_calls_microusd"] == v1.worst_total(experiment.slots)


def test_full_run_pairs_new_against_old_default(experiment):
    transport = FakeTransport(experiment.questions, wrong_arm="old_default")
    assert run(experiment, transport) == "finished" and transport.calls == 24
    assert run(experiment, transport) == "finished" and transport.calls == 24  # No resend.
    value, private, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["status"] == "COMPLETE" and value["approval"].startswith("D125")
    assert value["results"]["new_default"]["judge"]["correct"] == 6
    assert value["results"]["old_default"]["judge"]["correct"] == 0
    assert "paired_vs_d118" not in value["results"]["new_default"]
    paired = value["paired_new_vs_old_default"]
    assert paired["judge"] == {"improved": 6, "regressed": 0, "both_right": 0, "both_wrong": 0}
    assert paired["lenient-v3"]["improved"] == 6
    assert "code-0" not in json.dumps(value) and len(private) == 12


def test_empty_answer_is_counted_wrong_and_not_judged(experiment):
    transport = FakeTransport(experiment.questions, "empty_response", at=(1,))
    assert run(experiment, transport) == "finished" and transport.calls == 23
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["results"]["new_default"]["accepted_errors"] == 1
    assert value["rows"][0]["judge"] is False


@pytest.mark.parametrize("failure", ["billing_or_quota", "rate_limit", "authentication"])
def test_provider_errors_stop(experiment, failure):
    transport = FakeTransport(experiment.questions, failure, at=(2,))
    assert run(experiment, transport) == f"stopped_{failure}" and transport.calls == 2


def test_cap_is_a_spending_limit_checked_before_every_call(experiment, monkeypatch):
    first = v1.worst_answer(experiment.slots[0])
    monkeypatch.setattr(v1, "CAP_MICROUSD", first)  # Room for exactly one worst-case answer.
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "cap_would_exceed" and transport.calls == 1


def test_pacing_uses_each_calls_price_card_with_margin(monkeypatch):
    answer = v1.ANSWER_PRICES.reserve_cost(v1.margin(1000), 8192)
    monkeypatch.setattr(v1, "CAP_MICROUSD", answer - 1)
    now = time.time()
    assert v1.pacing([], 1000, 2048, now)[0] == "ready"
    assert v1.pacing([], 1000, 8192, now)[0] == "cap_would_exceed"
