"""Offline tests for the D114 reworded-question runner. Never uses the owner's key/ledger."""

import asyncio
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.evaluation.strategies import load_paraphrases
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import GroqTransport
from tests.test_embeddings import Concepts

spec = importlib.util.spec_from_file_location(
    "semantic_accuracy_live",
    Path(__file__).resolve().parents[1] / "scripts/semantic_accuracy_live.py",
)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


@pytest.fixture(scope="module")
def plan():
    return live.build(Concepts("test-concepts"))


@pytest.fixture
def experiment(tmp_path, monkeypatch, plan):
    async def forbidden(*args, **kwargs):
        pytest.fail("No network in runner tests")

    monkeypatch.setattr(GroqTransport, "send", forbidden)
    clock = [time.time()]
    fake_time = SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    monkeypatch.setattr(live, "time", fake_time)

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live.base, "LEDGER", tmp_path / "account.sqlite")
    store = RuntimeStore(live.base.LEDGER)
    with store.transaction() as db:
        store._account(db, live.base.POLICY, time.time())
    bundle, slots, requests = plan
    manifest = live.identity(slots, "test-concepts")
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return manifest, requests, bundle, store, advance, fake_time


class FakeTransport:
    namespace = GroqTransport().namespace

    def __init__(self, bundle, mode="correct", reject=()):
        self.mode, self.calls, self.reject = mode, 0, set(reject)
        reworded = load_paraphrases(bundle)
        self.answers = {reworded[f["fact_id"]]: f["expected"] for f in bundle.facts}

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert payload["model"] == live.base.MODEL and payload["max_completion_tokens"] == 256
        if self.mode == "rate_limit":
            raise TransportFailure("rate_limit", uncertain=False, retryable=True)
        if self.calls in self.reject:
            raise TransportFailure("provider_rejected", uncertain=False)
        answer = self.answers[payload["messages"][-1]["content"]]
        return Completion(live.base.MODEL, f"t-{self.calls}", answer, "stop", Usage(100, 4, 0, 0))


def client(store, transport, clock):
    return ProviderClient(
        store=store,
        quota=live.base.POLICY,
        prices=live.base.PRICES,
        api_key="test-only",
        generation=live.base.GENERATION,
        retries=live.base.RETRIES,
        transport=transport,
        clock=clock.time,
    )


def test_plan_asks_reworded_questions_for_both_strategies(plan):
    bundle, slots, _ = plan
    assert len(slots) == live.MAX_CALLS == 62
    assert [s["strategy"] for s in slots[:2]] == ["combined", "combined_semantic"]
    assert all(s["estimated_tokens"] <= live.base.BUDGET for s in slots)


def test_full_run_resume_and_private_report(experiment):
    manifest, requests, bundle, store, advance, clock = experiment
    transport = FakeTransport(bundle)
    provider = client(store, transport, clock)
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "finished"
    assert asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "finished"
    assert transport.calls == 62
    report = live.report(manifest, bundle)
    assert report["status"] == "COMPLETE" and report["question_set"] == "paraphrased"
    assert all(g["correct"] == 31 for g in report["strategies"].values())
    assert "merchant-aurora" not in str(report)  # No answer text in the public report.


def test_rate_limit_stops_and_rejection_is_skipped_once(experiment):
    manifest, requests, bundle, store, advance, clock = experiment
    rejecting = client(store, FakeTransport(bundle, reject={3}), clock)
    assert asyncio.run(live.dispatch(manifest, requests, rejecting, sleep=advance)) == "finished"
    report = live.report(manifest, bundle)
    assert sum(g["rejected"] for g in report["strategies"].values()) == 1


def test_rate_limit_stops_without_retry(experiment):
    manifest, requests, bundle, store, advance, clock = experiment
    transport = FakeTransport(bundle, "rate_limit")
    provider = client(store, transport, clock)
    assert (
        asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance))
        == "stopped_rate_limit"
    )
    assert (
        asyncio.run(live.dispatch(manifest, requests, provider, sleep=advance)) == "preserved_error"
    )
    assert transport.calls == 1


def test_runner_limits_match_approval():
    assert live.base.MODEL == "openai/gpt-oss-20b" and live.base.BUDGET == 900
    assert live.base.RETRIES.max_attempts == 1 and live.MAX_REJECTIONS == 10
    assert live.base.POLICY.billing_mode == "free_tier"
