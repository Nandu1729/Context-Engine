"""Offline tests for the D121 temporal output-limit runner (stage B runner, patched), on
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

from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import InceptionTransport

spec = importlib.util.spec_from_file_location(
    "longmemeval_temporal_tokens_live",
    Path(__file__).resolve().parents[1] / "scripts/longmemeval_temporal_tokens_live.py",
)
temporal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(temporal)
temporal.patch()
live = temporal.b

TYPES = ("knowledge-update", "multi-session", "temporal-reasoning")
FILLER = "We talked about the weather and a recipe for soup, nothing else of note."


def item(number, kind):
    code = f"code-{number:02d}"
    sessions = [
        [{"role": "user", "content": f"{FILLER} {i}"}, {"role": "assistant", "content": "Ok."}]
        for i in range(12)
    ]
    sessions[3][0] = {"role": "user", "content": f"My locker code is {code}.", "has_answer": True}
    return {
        "question_id": f"q{number:02d}",
        "question_type": kind,
        "question": f"What is my locker code, question {number}?",
        "question_date": "2023/05/30 (Tue) 23:40",
        "answer": code,
        "answer_session_ids": ["s3"],
        "haystack_dates": [f"2023/05/{10 + i:02d} (Wed) 10:00" for i in range(12)],
        "haystack_session_ids": [f"s{i}" for i in range(12)],
        "haystack_sessions": sessions,
    }


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    items = [item(n, TYPES[n % 3]) for n in range(12)]
    data = tmp_path / "longmemeval.json"
    data.write_text(json.dumps(items))
    monkeypatch.setattr(live.lme, "DATA", data)
    monkeypatch.setattr(live.lme, "SHA256", hashlib.sha256(data.read_bytes()).hexdigest())
    sample = live.d118.sample(live.d118.eligible(live.d118.load_items()), 9, live.SEED)
    count = sum(q["question_type"] == "temporal-reasoning" for q in sample)
    assert count >= 2
    monkeypatch.setattr(temporal, "STAGE_B_QUESTIONS", 9)
    for module in (temporal, live):
        monkeypatch.setattr(module, "QUESTIONS", count)
        monkeypatch.setattr(module, "ANSWERS", 2 * count)
        monkeypatch.setattr(module, "MAX_CALLS", 4 * count)
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "PUBLIC", tmp_path / "public")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(temporal, "STAGE_B_RUN", tmp_path / "stage-b")  # No manifest there.

    async def forbidden(*args, **kwargs):
        pytest.fail("No network in runner tests")

    monkeypatch.setattr(InceptionTransport, "send", forbidden)
    clock = [time.time()]
    fake_time = SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    monkeypatch.setattr(live, "time", fake_time)

    async def advance(seconds):
        clock[0] += seconds

    store = RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    questions, slots, requests, contexts = live.build()
    # Stage B baseline: every answer ran out of tokens (wrong for every grader).
    stage_b = tmp_path / "stage-b.json"
    stage_b.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "question_id": q["question_id"],
                        "arm": arm,
                        "out_of_tokens": True,
                        **dict.fromkeys(("strict-v1", "lenient-v2", "lenient-v3", "judge"), False),
                    }
                    for q in questions
                    for arm in ("core_default", "chatmemory_default", "chatmemory_8000")
                ]
            }
        )
    )
    monkeypatch.setattr(temporal, "STAGE_B", stage_b)
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
    namespace = InceptionTransport().namespace

    def __init__(self, questions, failure=None, at=()):
        self.calls, self.failure, self.at, self.payloads = 0, failure, at, []
        self.answers = {q["question"]: q["answer"] for q in questions}

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        self.payloads.append(payload)
        assert payload["model"] == "mercury-3" and api_key == "test-only"
        judge = payload["max_completion_tokens"] == 64
        if self.calls in self.at and self.failure == "empty_response":
            # As 0.17.1 parses mercury-3's content null + finish "stop": certain, usage known.
            usage = Usage(100, 2, 0, 0) if judge else Usage(900, 60, 0, 50)
            raise TransportFailure("empty_response", uncertain=False, usage=usage)
        if self.calls in self.at:
            raise TransportFailure(self.failure, uncertain=False)
        if judge:
            assert payload["reasoning_effort"] == "instant"
            return Completion("mercury-3", f"t-{self.calls}", "yes", "stop", Usage(300, 1))
        assert payload["max_completion_tokens"] == 2048 and payload["reasoning_effort"] == "low"
        answer = self.answers[payload["messages"][-1]["content"]]
        return Completion("mercury-3", f"t-{self.calls}", answer, "stop", Usage(900, 60, 0, 50))


def run(x, transport):
    clients = [
        ProviderClient(
            store=x.store,
            quota=live.POLICY,
            prices=live.PRICES,
            api_key="test-only",
            generation=generation,
            retries=live.RETRIES,
            transport=transport,
            clock=x.clock.time,
        )
        for generation in (live.ANSWER, live.JUDGE)
    ]
    return asyncio.run(live.dispatch(x.manifest, x.requests, x.items, clients, sleep=x.advance))


def test_settings_change_only_the_output_limit():
    assert temporal.ANSWER.max_completion_tokens == 2048
    stage_b = temporal._load("longmemeval_accuracy_live_b")  # Unpatched copy.
    assert temporal.ANSWER == stage_b.ANSWER.__class__(
        **{**stage_b.ANSWER.__dict__, "max_completion_tokens": 2048}
    )
    assert temporal.ARMS == {arm: stage_b.ARMS[arm] for arm in temporal.ARMS}
    assert live.SYSTEM == stage_b.SYSTEM and live.JUDGE == stage_b.JUDGE
    assert live.LEDGER != stage_b.LEDGER and live.RUN_ID != stage_b.RUN_ID
    assert live.POLICY.account_id == "inception-longmemeval-d121"
    assert live.POLICY.daily_budget_microusd == temporal.CAP_MICROUSD == 70_000
    assert temporal.MAX_CALLS <= temporal.TOTAL_CALLS == live.POLICY.rpd


def test_only_temporal_questions_in_two_arms(experiment):
    assert {q["question_type"] for q in experiment.questions} == {"temporal-reasoning"}
    assert [s["arm"] for s in experiment.slots[:2]] == ["core_default", "chatmemory_default"]
    assert experiment.manifest["stage_b_runner_sha256"] != experiment.manifest["runner_sha256"]
    plan = live.plan(experiment.questions, experiment.slots)
    assert plan["stage_b_out_of_tokens_on_these"] == dict.fromkeys(
        temporal.ARMS, len(experiment.questions)
    )
    assert "same_contexts_as_stage_b" not in plan  # Stage B's private manifest is absent.


def test_full_run_is_paired_with_stage_b(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "finished"
    assert transport.calls == live.MAX_CALLS
    assert run(experiment, transport) == "finished" and transport.calls == live.MAX_CALLS
    value, private, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["status"] == "COMPLETE" and value["answer_max_completion_tokens"] == 2048
    count = len(experiment.questions)
    for arm in temporal.ARMS:
        result = value["results"][arm]
        assert "paired_vs_d118" not in result
        assert result["paired_vs_stage_b"]["judge"]["improved"] == count
        assert result["stage_b_same_questions"]["out_of_tokens"] == count
        assert result["stage_b_same_questions"]["judge"]["correct"] == 0
        assert result["judge"]["correct"] == result["lenient-v3"]["correct"] == count
    assert "code-" not in json.dumps(value) and len(private) == 2 * count


def test_empty_response_answer_is_counted_wrong_and_never_resent(experiment):
    transport = FakeTransport(experiment.questions, "empty_response", at=(1,))
    assert run(experiment, transport) == "finished"
    calls = transport.calls
    assert calls == live.MAX_CALLS - 1  # The empty answer is not judged.
    assert run(experiment, transport) == "finished" and transport.calls == calls
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    core = value["results"]["core_default"]
    assert (
        core["accepted_errors"] == 1 and core["judge"]["correct"] == len(experiment.questions) - 1
    )
    assert value["rows"][0]["group"] == "invalid_response" and value["rows"][0]["judge"] is False


def test_empty_judge_reply_counts_no(experiment):
    answers = live.ANSWERS
    transport = FakeTransport(experiment.questions, "empty_response", at=(answers + 1,))
    assert run(experiment, transport) == "finished" and transport.calls == live.MAX_CALLS
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["rows"][0]["judge"] is False and value["rows"][0]["judge_no_text"]


def test_too_many_empty_responses_stop(experiment, monkeypatch):
    monkeypatch.setattr(live, "MAX_INVALID_RESPONSES", 1)
    transport = FakeTransport(experiment.questions, "empty_response", at=(1, 2))
    assert run(experiment, transport) == "stopped_empty_response" and transport.calls == 2
    assert run(experiment, transport) == "too_many_invalid_responses"  # Resume stays stopped.
    assert transport.calls == 2


@pytest.mark.parametrize("failure", ["billing_or_quota", "rate_limit"])
def test_charge_and_rate_errors_stop(experiment, failure):
    transport = FakeTransport(experiment.questions, failure, at=(2,))
    assert run(experiment, transport) == f"stopped_{failure}" and transport.calls == 2


def test_cap_stops_before_any_call(experiment, monkeypatch):
    monkeypatch.setattr(live, "CAP_MICROUSD", 1)
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "cap_would_exceed" and transport.calls == 0
