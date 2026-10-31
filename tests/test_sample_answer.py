"""D105 synthetic safety checks: never use real credentials, corpus or ledger."""

import asyncio
import copy
import time
from dataclasses import replace

import pytest

from context_engine.config import BudgetConfig
from context_engine.models import ChatRequest, Message, Scope
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from scripts import sample_answer as live
from scripts.incident_demo import offline_network


@pytest.fixture
def run(tmp_path, monkeypatch):
    live.TiktokenCounter()
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    monkeypatch.setattr(live.safety, "LEDGER", tmp_path / "account.sqlite")
    live.RUN.mkdir()
    request = ChatRequest((Message("m", "user", "Synthetic database: PostgreSQL"),))
    budget = BudgetConfig(input_cap=900, summary_reserve=0)
    scope = Scope("synthetic", "sample")
    monkeypatch.setattr(live, "prepared", lambda: (request, budget, scope))
    tokens = live.validate_request(
        request=request, config=budget, counter=live.TiktokenCounter()
    ).estimated_tokens
    fixed = {
        "id": live.VERSION,
        "max_calls": 1,
        "request_hash": live.fingerprint(request.to_wire()),
        "estimated_tokens": tokens,
    }
    monkeypatch.setattr(live, "identity", lambda: copy.deepcopy(fixed))
    store = live.RuntimeStore(live.safety.LEDGER)
    with store.transaction() as db:
        store._account(db, live.safety.POLICY, time.time())
    manifest = {
        **fixed,
        "baseline": {},
        "provenance": "TEST_ONLY",
        "model_preflight": {
            "model": live.safety.MODEL,
            "listed": True,
            "active": True,
            "checked_at": time.time(),
        },
    }
    live.save(live.RUN / "manifest.json", manifest)
    with offline_network():
        yield store, manifest


class Fake:
    namespace = live.GroqTransport().namespace

    def __init__(self, mode="success"):
        self.mode, self.calls = mode, 0

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert payload["model"] == live.safety.MODEL
        assert payload["max_completion_tokens"] == 256
        assert "response_format" not in payload and "tools" not in payload
        if self.mode in {"error", "uncertain"}:
            raise TransportFailure(
                "provider_rejected", uncertain=self.mode == "uncertain", retryable=True
            )
        return Completion(
            live.safety.MODEL,
            "fake-1",
            "" if self.mode == "empty" else "PRIVATE_ANSWER PostgreSQL",
            "length" if self.mode == "truncated" else "stop",
            Usage(30, 10, 0, 0),
        )


def client(store, fake):
    return live.ProviderClient(
        store=store,
        quota=live.safety.POLICY,
        prices=live.safety.PRICES,
        api_key="synthetic",
        generation=live.safety.GENERATION,
        retries=live.safety.RETRIES,
        replay=live.ReplayPolicy(),
        transport=fake,
    )


@pytest.mark.parametrize("mode", ["success", "empty", "truncated", "error", "uncertain"])
def test_one_attempt_and_no_repeat_even_on_failure(run, mode):
    store, manifest = run
    fake = Fake(mode)
    provider = client(store, fake)
    assert asyncio.run(live.dispatch(manifest, provider)) == "recorded_no_more_calls"
    assert asyncio.run(live.dispatch(manifest, provider)) == "recorded_no_more_calls"
    assert fake.calls == 1
    result = live.status(manifest)
    assert result["provider_attempts"] == 1 and "answer" not in result
    assert "PRIVATE_ANSWER" not in str(result)
    assert result["usage_uncertain"] == (mode == "uncertain")
    if mode == "success":
        assert live.status(manifest, show_answer=True)["answer"] == "PRIVATE_ANSWER PostgreSQL"


def test_unreceipted_claim_never_resent(run):
    store, manifest = run
    live.save(
        live.RUN / "claim.json",
        {"execution_id": live.fingerprint(manifest), "request_key": live.request_key(manifest)},
    )
    fake = Fake()
    assert asyncio.run(live.dispatch(manifest, client(store, fake))) == "uncertain_do_not_resend"
    assert fake.calls == 0 and live.status(manifest)["usage_uncertain"]


@pytest.mark.parametrize("change", ["claim", "receipt", "baseline", "extra", "identity"])
def test_tamper_fails_closed(run, change):
    store, manifest = run
    asyncio.run(live.dispatch(manifest, client(store, Fake())))
    if change in {"claim", "receipt"}:
        path = live.RUN / f"{change}.json"
        value = live.read(path)
        if change == "claim":
            value["request_key"] = "wrong"
        else:
            value["result"]["completion"]["content"] = "forged"
        path.write_text(live.safety.canonical_json(value))
    elif change == "baseline":
        manifest["baseline"]["missing-history"] = "wrong"
    elif change == "extra":
        live.save(live.RUN / "claim-2.json", {})
    else:
        manifest["estimated_tokens"] += 1
    with pytest.raises(ValueError):
        live.inspect(manifest, live.safety.ledger())


@pytest.mark.parametrize("field", ["retries", "generation", "replay", "prices"])
def test_dispatch_settings_cannot_expand_approval(run, field):
    store, manifest = run
    fake = Fake()
    provider = client(store, fake)
    changes = {
        "retries": {"max_attempts": 2},
        "generation": {"max_completion_tokens": 512},
        "replay": {"enabled": True},
        "prices": {"input_per_million_microusd": 1},
    }
    setattr(provider, field, replace(getattr(provider, field), **changes[field]))
    with pytest.raises(ValueError):
        asyncio.run(live.dispatch(manifest, provider))
    assert fake.calls == 0 and not (live.RUN / "claim.json").exists()


def test_quota_stop_leaves_no_claim_or_call(run, monkeypatch):
    store, manifest = run
    monkeypatch.setattr(live.safety, "pacing", lambda *a: ("daily_quota", 0))
    fake = Fake()
    assert asyncio.run(live.dispatch(manifest, client(store, fake))) == "daily_quota"
    assert fake.calls == 0 and not (live.RUN / "claim.json").exists()


def test_exclusive_claim_and_lock_no_overwrite(run):
    with pytest.raises(FileExistsError):
        live.save(live.RUN / "manifest.json", {})
    with live.run_lock():
        with pytest.raises(FileExistsError), live.run_lock():
            pass
        assert (live.RUN / "runner.lock").exists()
    assert not (live.RUN / "runner.lock").exists()


def test_cli_requires_explicit_live_flag(run, monkeypatch):
    monkeypatch.setattr(live, "load_api_key", lambda *a: pytest.fail("Must not read credentials"))
    assert live.main(["init"]) == 1
    assert live.main(["run"]) == 1


def test_completed_cli_resume_does_not_read_credentials(run, monkeypatch):
    store, manifest = run
    manifest["provenance"] = "LIVE"
    (live.RUN / "manifest.json").write_text(live.safety.canonical_json(manifest))
    asyncio.run(live.dispatch(manifest, client(store, Fake())))
    monkeypatch.setattr(live, "load_api_key", lambda *a: pytest.fail("Must not read credentials"))
    assert live.main(["run", "--allow-live"]) == 0


def test_stale_preflight_stops_before_credentials(run, monkeypatch):
    _, manifest = run
    manifest["provenance"] = "LIVE"
    manifest["model_preflight"]["checked_at"] = time.time() - 301
    (live.RUN / "manifest.json").write_text(live.safety.canonical_json(manifest))
    monkeypatch.setattr(live, "load_api_key", lambda *a: pytest.fail("Must not read credentials"))
    assert live.main(["run", "--allow-live"]) == 1
    assert not (live.RUN / "claim.json").exists()
