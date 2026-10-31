"""Offline tests for the D118 LongMemEval accuracy runner, on a tiny synthetic dataset
in LongMemEval's shape. Never uses the owner's key, ledger or the real dataset."""

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
    "longmemeval_accuracy_live",
    Path(__file__).resolve().parents[1] / "scripts/longmemeval_accuracy_live.py",
)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)

TYPES = ("knowledge-update", "multi-session", "temporal-reasoning")
FILLER = "We talked about the weather and a recipe for soup, nothing else of note."


def item(number, kind, abstain=False):
    code = f"code-{number:02d}"
    sessions = [
        [{"role": "user", "content": f"{FILLER} {i}"}, {"role": "assistant", "content": "Ok."}]
        for i in range(12)
    ]
    sessions[3][0] = {"role": "user", "content": f"My locker code is {code}.", "has_answer": True}
    return {
        "question_id": f"q{number:02d}" + ("_abs" if abstain else ""),
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
    items = [item(n, TYPES[n % 3]) for n in range(9)] + [item(99, TYPES[0], abstain=True)]
    data = tmp_path / "longmemeval.json"
    data.write_text(json.dumps(items))
    monkeypatch.setattr(live.lme, "DATA", data)
    monkeypatch.setattr(live.lme, "SHA256", hashlib.sha256(data.read_bytes()).hexdigest())
    monkeypatch.setattr(live, "QUESTIONS", 6)
    monkeypatch.setattr(live, "MAX_CALLS", 12)
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")

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
    questions, slots, requests = live.build()
    manifest = live.identity(slots)
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return SimpleNamespace(
        questions=questions,
        manifest=manifest,
        requests=requests,
        store=store,
        advance=advance,
        clock=fake_time,
    )


class FakeTransport:
    namespace = InceptionTransport().namespace

    def __init__(self, questions, failure=None, at=1):
        self.calls, self.failure, self.at = 0, failure, at
        self.answers = {q["question"]: q["answer"] for q in questions}

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert payload["model"] == "mercury-3" and payload["max_completion_tokens"] == 256
        assert payload["temperature"] == 0.5 and api_key == "test-only"
        if self.failure and self.calls == self.at:
            raise TransportFailure(
                self.failure, uncertain=False, retryable=self.failure == "rate_limit"
            )
        answer = self.answers[payload["messages"][-1]["content"]]
        return Completion("mercury-3", f"t-{self.calls}", answer, "stop", Usage(900, 6, 0, 0))


def run(x, transport, **kwargs):
    provider = ProviderClient(
        store=x.store,
        quota=live.POLICY,
        prices=live.PRICES,
        api_key="test-only",
        generation=live.GENERATION,
        retries=live.RETRIES,
        transport=transport,
        clock=x.clock.time,
    )
    return asyncio.run(live.dispatch(x.manifest, x.requests, provider, sleep=x.advance, **kwargs))


def test_sample_is_seeded_stratified_and_skips_abstention(experiment):
    ids = [q["question_id"] for q in experiment.questions]
    assert len(ids) == 6 and not any(i.endswith("_abs") for i in ids)
    assert sorted(q["question_type"] for q in experiment.questions) == sorted(TYPES * 2)
    again = live.sample(live.eligible(live.load_items()), 6)
    assert [q["question_id"] for q in again] == ids
    slots = experiment.manifest["slots"]
    assert [s["setting"] for s in slots[:2]] == ["core_default", "chatmemory_default"]
    assert all(s["estimated_tokens"] <= live.BUDGET and s["evidence_any"] for s in slots)


def test_full_run_resume_report_and_private_answers(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "finished"
    assert run(experiment, transport) == "finished" and transport.calls == 12  # No resend.
    report = live.report(experiment.manifest, experiment.questions)
    assert report["status"] == "COMPLETE" and report["list_price_cost_microusd"] > 0
    for group in report["results"].values():
        assert group["answered"] == group["strict-v1"] == group["lenient-v2"] == 6
        assert group["evidence_but_wrong_lenient"] == group["right_without_evidence_lenient"] == 0
    assert "code-0" not in json.dumps(report)  # Answers stay private.


def test_max_slots_pauses_then_resumes(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport, max_slots=3) == "paused" and transport.calls == 3
    assert run(experiment, transport) == "finished" and transport.calls == 12


@pytest.mark.parametrize(
    "failure,outcome",
    [("billing_or_quota", "stopped_billing_or_quota"), ("rate_limit", "stopped_rate_limit")],
)
def test_billing_and_rate_limit_stop_without_retry(experiment, failure, outcome):
    transport = FakeTransport(experiment.questions, failure)
    assert run(experiment, transport) == outcome
    assert run(experiment, transport) == "preserved_error" and transport.calls == 1


def test_zero_token_rejection_is_skipped(experiment):
    transport = FakeTransport(experiment.questions, "provider_rejected", at=2)
    assert run(experiment, transport) == "finished" and transport.calls == 12
    report = live.report(experiment.manifest, experiment.questions)
    assert sum(g["rejected"] for g in report["results"].values()) == 1


def test_spend_cap_stops_before_sending(experiment, monkeypatch):
    monkeypatch.setattr(live, "CAP_MICROUSD", 1)
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "cap_would_exceed" and transport.calls == 0


def test_runner_limits_match_approval():
    assert (live.QUESTIONS, live.MAX_CALLS, live.BUDGET, live.SEED) == (95, 190, 3000, 118)
    assert live.TOTAL_CALLS == 200 and live.GENERATION.reasoning_effort == "instant"
    assert live.CAP_MICROUSD == 100_000 and live.MAX_REJECTIONS == 10
    assert live.GENERATION.model == "mercury-3" and live.GENERATION.max_completion_tokens == 256
    assert live.RETRIES.max_attempts == 1 and live.POLICY.daily_budget_microusd == 100_000
    assert live.SETTINGS == {
        "core_default": {"reserve": 280, "top_k": 4, "diverse_turns": False},
        "chatmemory_default": {"reserve": 1200, "top_k": 13, "diverse_turns": True},
    }
    assert live.LEDGER.name == "longmemeval-accuracy-account.sqlite"  # Separate ledger.


def test_report_command_works_after_spend_reaches_the_cap(experiment, monkeypatch, tmp_path):
    assert run(experiment, FakeTransport(experiment.questions)) == "finished"
    monkeypatch.setattr(live, "worst_cost", lambda tokens: live.CAP_MICROUSD)  # No room left.
    monkeypatch.setattr(live, "PUBLIC", tmp_path / "public")
    monkeypatch.setattr("sys.argv", ["runner", "report"])
    assert live.main() == 0
    assert json.loads((tmp_path / "public/report.json").read_text())["status"] == "COMPLETE"
