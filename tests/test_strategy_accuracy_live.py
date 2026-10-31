"""Offline tests for the bounded strategy-accuracy runner. Never uses the owner's key/ledger."""

import asyncio
import importlib.util
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import GroqTransport

spec = importlib.util.spec_from_file_location(
    "strategy_accuracy_live",
    Path(__file__).resolve().parents[1] / "scripts/strategy_accuracy_live.py",
)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


@pytest.fixture(scope="module")
def plan():
    return live.build()


@pytest.fixture
def experiment(tmp_path, monkeypatch, plan):
    async def forbidden(*args, **kwargs):
        pytest.fail("No network in strategy-accuracy runner tests")

    monkeypatch.setattr(GroqTransport, "send", forbidden)
    clock = [time.time()]
    monkeypatch.setattr(
        live, "time", SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    )

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    store = RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    bundle, slots, requests = plan
    manifest = live.identity(slots)
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return manifest, requests, bundle, store, advance


class FakeTransport:
    namespace = GroqTransport().namespace

    def __init__(self, bundle, mode="correct", reject=()):
        self.mode, self.calls, self.reject = mode, 0, set(reject)
        self.answers = {f["question"]: f["expected"] for f in bundle.facts}

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert api_key == "test-only" and timeout <= 20
        assert payload["model"] == live.MODEL and payload["max_completion_tokens"] == 256
        if self.mode == "rate_limit":
            raise TransportFailure("rate_limit", uncertain=False, retryable=True)
        if self.mode == "reject_all" or self.calls in self.reject:
            raise TransportFailure("provider_rejected", uncertain=False)
        question = payload["messages"][-1]["content"]
        answer = self.answers[question] if self.mode == "correct" else "UNKNOWN"
        finish = "length" if self.mode == "truncated" else "stop"
        return Completion(live.MODEL, f"test-{self.calls}", answer, finish, Usage(100, 4, 0, 0))


def client(store, transport):
    return ProviderClient(
        store=store,
        quota=live.POLICY,
        prices=live.PRICES,
        api_key="test-only",
        generation=live.GENERATION,
        retries=live.RETRIES,
        transport=transport,
        clock=live.time.time,
    )


def test_plan_is_bounded_and_fits_budget(plan):
    _, slots, _ = plan
    assert len(slots) == live.MAX_CALLS == 155
    assert {s["strategy"] for s in slots} == set(live.STRATEGIES)
    assert all(s["estimated_tokens"] <= live.BUDGET for s in slots)
    # Fact-major order: each fact is tried on every strategy before the next fact.
    assert [s["strategy"] for s in slots[:5]] == list(live.STRATEGIES)


def test_full_run_grades_answers_and_resume_sends_nothing(experiment):
    manifest, requests, bundle, store, advance = experiment
    transport = FakeTransport(bundle)
    provider = client(store, transport)
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "finished"
    assert transport.calls == 155
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "finished"
    assert transport.calls == 155
    report = live.report(manifest, bundle)
    assert report["status"] == "COMPLETE" and report["provider_calls"] == 155
    for group in report["strategies"].values():
        assert group["answered"] == group["correct"] == 31
    assert report["tokens"]["input"] == 155 * 100


def test_rate_limit_stops_without_retry_or_resume(experiment):
    manifest, requests, bundle, store, advance = experiment
    transport = FakeTransport(bundle, "rate_limit")
    provider = client(store, transport)
    outcome = asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance))
    assert outcome == "stopped_rate_limit" and transport.calls == 1
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == (
        "preserved_error"
    )
    assert transport.calls == 1
    report = live.report(manifest, bundle)
    assert report["status"] == "PARTIAL" and report["provider_calls"] == 1


def test_truncated_answers_count_as_wrong_and_continue(experiment):
    manifest, requests, bundle, store, advance = experiment
    transport = FakeTransport(bundle, "truncated")
    provider = client(store, transport)
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "finished"
    report = live.report(manifest, bundle)
    assert all(g["correct"] == 0 and g["answered"] == 31 for g in report["strategies"].values())
    assert "UNKNOWN" not in json.dumps(report)  # Public report carries no answer content.


def test_key_loader_reads_only_groq_line_from_shared_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GROQ_API_KEY=gsk_test-only\nTESTPYPI_TOKEN=pypi-x\nINCEPTION_API_KEY=y\n")
    env.chmod(0o600)
    monkeypatch.setattr(live, "ROOT", tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert live.load_groq_key() == "gsk_test-only"


def test_runner_constants_match_approval():
    assert live.MODEL == "openai/gpt-oss-20b" and live.BUDGET == 900
    assert asdict(live.RETRIES)["max_attempts"] == 1
    assert live.POLICY.billing_mode == "free_tier" and live.PRICES.input_per_million_microusd == 0


def amended(manifest, slots):
    """Simulate D110: an earlier runner identity plus a recorded amendment."""
    base = {**manifest, "runner_sha256": "0" * 64}
    (live.RUN / "manifest.json").unlink()
    live.save(live.RUN / "manifest.json", base)
    return base


def write_amendment(failures):
    live.save(
        live.RUN / "amendment-001.json",
        {
            "decision": "D110",
            "base_runner_sha256": "0" * 64,
            "runner_sha256": live.runner_hash(),
            "rule": live.AMENDMENT_RULE,
            "reviewed_failures": failures,
            "max_rejections": live.MAX_REJECTIONS,
        },
    )


def test_rejection_stops_until_amended_then_is_skipped_never_retried(experiment, plan):
    manifest, requests, bundle, store, advance = experiment
    base = amended(manifest, plan[1])
    expected = live.identity(plan[1])
    with pytest.raises(ValueError):
        live.verify(base, expected)  # Changed runner without an amendment is refused.
    transport = FakeTransport(bundle, reject={2})
    provider = client(store, transport)
    outcome = asyncio.run(live.dispatch(base, requests, provider, sleep=advance))
    assert outcome == "stopped_provider_rejected" and transport.calls == 2
    done, _ = live.receipts(base)
    assert live.skippable(done[1]["result"], live.ledger())
    write_amendment([1])
    change = live.verify(base, expected)
    transport.reject = {5}
    outcome = asyncio.run(live.dispatch(base, requests, provider, sleep=advance, change=change))
    assert outcome == "finished"
    assert transport.calls == 155  # 2 before + 153 after: the rejected slot was not resent.
    report = live.report(base, bundle)
    assert report["status"] == "COMPLETE" and report["amendment"]["decision"] == "D110"
    assert sum(g["rejected"] for g in report["strategies"].values()) == 2
    assert sum(g["answered"] for g in report["strategies"].values()) == 153


def test_amendment_still_stops_on_rate_limit_and_rejection_cap(experiment, plan):
    manifest, requests, bundle, store, advance = experiment
    base = amended(manifest, plan[1])
    write_amendment([])
    change = live.verify(base, live.identity(plan[1]))
    limited = client(store, FakeTransport(bundle, "rate_limit"))
    outcome = asyncio.run(live.dispatch(base, requests, limited, sleep=advance, change=change))
    assert outcome == "stopped_rate_limit"
    assert (
        asyncio.run(live.dispatch(base, requests, limited, sleep=advance, change=change))
        == "preserved_error"
    )


def test_rejection_cap_stops_the_run(experiment, plan):
    manifest, requests, bundle, store, advance = experiment
    base = amended(manifest, plan[1])
    write_amendment([])
    change = live.verify(base, live.identity(plan[1]))
    transport = FakeTransport(bundle, "reject_all")
    provider = client(store, transport)
    outcome = asyncio.run(live.dispatch(base, requests, provider, sleep=advance, change=change))
    assert outcome == "too_many_rejections"
    assert transport.calls == live.MAX_REJECTIONS + 1
