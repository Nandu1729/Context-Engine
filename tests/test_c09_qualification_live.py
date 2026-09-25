"""Offline tests for the external bounded runner. Never use the owner's ledger/key."""

import asyncio
import copy
import importlib.util
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage, fingerprint
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import GroqTransport

spec = importlib.util.spec_from_file_location(
    "c09_qualification_live",
    Path(__file__).resolve().parents[1] / "scripts/c09_qualification_live.py",
)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
qualification = live.qualification
live = live.live


@pytest.fixture(scope="module")
def preparation():
    return qualification.prepare()


@pytest.fixture
def experiment(tmp_path, monkeypatch, preparation):
    async def forbidden(*args, **kwargs):
        pytest.fail("No network in C09 runner tests")

    monkeypatch.setattr(GroqTransport, "send", forbidden)
    clock = [time.time()]
    monkeypatch.setattr(
        live, "time", SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    )

    async def advance(seconds):
        clock[0] += seconds

    dispatch = live.dispatch
    monkeypatch.setattr(live, "dispatch", lambda m, c: dispatch(m, c, sleep=advance))
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(live, "CONFIG", tmp_path / "config.json")
    # Separate TEST_ONLY fixtures; never use the real account or run directory.
    config = {
        "quota": asdict(live.POLICY),
        "prices": {live.MODEL: asdict(live.PRICES)},
        "ledger_path": str(live.LEDGER),
        "max_run_cost_microusd": 0,
    }
    live.save(live.CONFIG, config)
    live.CONFIG.chmod(0o600)
    store = RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    # Same tested preparation, avoid recomputing every row at every inspection.
    monkeypatch.setattr(live, "prepare", lambda **kwargs: copy.deepcopy(preparation))
    value = live.identity()
    value.update(baseline={}, provenance="TEST_ONLY")
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", value)
    return value, store


class FakeTransport:
    namespace = GroqTransport().namespace

    def __init__(self, mode="success"):
        self.mode, self.calls = mode, 0

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert api_key == "test-only" and timeout <= 20
        assert payload["model"] == live.MODEL and payload["max_completion_tokens"] == 256
        assert payload["include_reasoning"] is False and payload["n"] == 1
        if self.mode == "rate_limit":
            raise TransportFailure("rate_limit", uncertain=False, retryable=True)
        if self.mode == "uncertain":
            raise TransportFailure("timeout", uncertain=True, retryable=True)
        if self.mode == "crash":
            raise asyncio.CancelledError()
        return Completion(
            live.MODEL,
            f"test-{self.calls}",
            '{"answer":"UNKNOWN"}',
            "length" if self.mode == "truncated" else "stop",
            Usage(4000 if self.mode == "overrun" else 100, 4, 0, 0),
        )


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


def test_full_run_never_exceeds_32_and_resume_sends_nothing(experiment):
    manifest, store = experiment
    transport = FakeTransport()
    provider = client(store, transport)
    assert asyncio.run(live.dispatch(manifest, provider)) == "finished"
    assert transport.calls == 32
    assert asyncio.run(live.dispatch(manifest, provider)) == "finished"
    assert transport.calls == 32
    report = live.report(manifest, live.ledger())
    assert report["status"] == "COMPLETE" and report["provider_attempts"] == 32
    assert report["provenance"] == "TEST_ONLY" and report["quality_target"] == "NOT_EVALUATED"
    assert report["answer_quality"] == "NOT_EVALUATED"
    assert all(g["planned"] == 8 for g in report["groups"])
    assert sum(r["correct"] for r in report["rows"]) == 8  # two abstention cases × four


@pytest.mark.parametrize("mode", ["rate_limit", "uncertain", "truncated"])
def test_error_stops_and_is_never_retried(experiment, mode):
    manifest, store = experiment
    transport = FakeTransport(mode)
    provider = client(store, transport)
    assert asyncio.run(live.dispatch(manifest, provider)) == "provider_error_or_unknown_usage"
    assert transport.calls == 1
    assert asyncio.run(live.dispatch(manifest, provider)) == "preserved_error"
    assert transport.calls == 1
    report = live.report(manifest, live.ledger())
    assert report["planned"] == 32 and report["dispositions"]["missing"] == 31
    assert report["cost_uncertain"] == (mode == "uncertain")
    assert live.ledger()[0]["state"] == ("uncertain" if mode == "uncertain" else "rejected")


def test_cancelled_dispatch_keeps_claim_and_hold(experiment):
    manifest, store = experiment
    transport = FakeTransport("crash")
    provider = client(store, transport)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(live.dispatch(manifest, provider))
    assert asyncio.run(live.dispatch(manifest, provider)) == "unreceipted_claim"
    assert transport.calls == 1
    result = live.report(manifest, live.ledger())
    assert result["claims"] == 1 and result["cost_uncertain"]
    assert result["provider_attempts"] == result["unresolved_attempts"] == 1
    assert result["dispositions"] == {"uncertain": 1, "missing": 31}


def test_claim_before_dispatch_crash_never_sends(experiment):
    manifest, store = experiment
    execution_id = fingerprint(manifest)
    row = manifest["preparation"]["rows"][0]
    live.save(
        live.RUN / "claim-00.json",
        {
            "execution_id": execution_id,
            "slot": 0,
            "request_key": live.request_key(row, execution_id),
        },
    )
    transport = FakeTransport()
    assert asyncio.run(live.dispatch(manifest, client(store, transport))) == "unreceipted_claim"
    assert transport.calls == 0 and live.ledger() == []


@pytest.mark.parametrize(
    "fault", ["plan", "source", "generation", "extra_file", "receipt_without_claim"]
)
def test_drift_rejected_before_dispatch(experiment, fault):
    manifest, store = experiment
    if fault == "plan":
        manifest["preparation"]["rows"][0]["budget"] = 3001
    elif fault == "source":
        manifest["runner_sha256"] = "0" * 64
    elif fault == "generation":
        manifest["generation"]["max_completion_tokens"] = 257
    else:
        live.save(live.RUN / ("extra.json" if fault == "extra_file" else "receipt-00.json"), {})
    transport = FakeTransport()
    with pytest.raises(ValueError):
        asyncio.run(live.dispatch(manifest, client(store, transport)))
    assert transport.calls == 0


def test_receipt_tampering_rejected(experiment):
    manifest, store = experiment
    transport = FakeTransport("truncated")
    asyncio.run(live.dispatch(manifest, client(store, transport)))
    path = live.RUN / "receipt-00.json"
    receipt = live.read(path)
    receipt["result"]["completion"]["content"] = "fake-perfect-answer"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        live.report(manifest, live.ledger())
    assert transport.calls == 1


@pytest.mark.parametrize(
    "field,value", [("max_run_cost_microusd", 1), ("ledger_path", "/tmp/new-pool.sqlite")]
)
def test_paid_or_replacement_ledger_config_rejected(experiment, field, value):
    data = live.read(live.CONFIG)
    data[field] = value
    live.CONFIG.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        live.identity()


def test_preserved_baseline_and_unknown_traffic(experiment):
    manifest, store = experiment
    transport = FakeTransport("truncated")
    asyncio.run(live.dispatch(manifest, client(store, transport)))
    rows = live.ledger()
    # Receipt itself is bound to completion, usage and model; changing accounting fails.
    rows[0]["charged_tokens"] += 1
    with pytest.raises(ValueError):
        live.inspect(manifest, rows)
    rows = live.ledger()
    rows.append({**rows[0], "id": "unattributed"})
    with pytest.raises(ValueError):
        live.inspect(manifest, rows)


def test_pacing_uses_full_usage_and_stops_uncertain_or_daily_quota():
    now = 864000.0
    row = {
        "state": "completed",
        "cost": 0,
        "charged_tokens": 7000,
        "created": now,
        "settled": now,
        "request_count": 1,
    }
    assert live.pacing([row], 2000, now) == ("minute_wait", 30)
    assert live.pacing([row], 2000, now + 61) == ("ready", 0)
    assert live.pacing([{**row, "charged_tokens": 200000}], 1, now)[0] == "daily_quota"
    assert live.pacing([{**row, "state": "uncertain"}], 1, now)[0] == "unsafe_account"
    assert live.pacing([{**row, "cost": 1}], 1, now)[0] == "unsafe_account"
    assert live.pacing([], 8001, now)[0] == "unserviceable_reservation"


def test_missing_keeps_denominator_and_wilson_interval(experiment):
    manifest, _ = experiment
    result = live.report(manifest, [])
    assert result["planned"] == result["dispositions"]["missing"] == 32
    assert all(g["correct"] == 0 and g["planned"] == 8 for g in result["groups"])
    low, high = live.wilson(8, 8)
    assert 0.67 < low < 0.68 and high == pytest.approx(1)


def test_exclusive_evidence_cannot_be_overwritten(experiment):
    with pytest.raises(FileExistsError):
        live.save(live.RUN / "manifest.json", {"replacement": True})


def test_ground_truth_not_in_provider_request(experiment):
    manifest, _ = experiment
    _, truth, _ = qualification.load()
    plan = next(
        r
        for r in manifest["preparation"]["rows"]
        if r["case"] == "q2-middle" and r["variant"] == "CONTROL"
    )
    request, _, _ = live.reconstruct(plan)
    # Default CONTROL cannot retain the middle fact; truth must not sneak into inputs.
    assert truth["q2-middle"]["answer"] not in json.dumps(request.to_wire())


def test_account_baseline_change_rejected(experiment):
    manifest, store = experiment
    admission = store.admit(
        policy=live.POLICY,
        key="historical",
        model=live.MODEL,
        reserved_tokens=300,
        reserved_cost=0,
        prices=live.PRICES,
        replay=live.ReplayPolicy(),
        now=live.time.time(),
    )
    store.settle(admission.attempt_id, now=live.time.time(), usage=Usage(10, 2, 0, 0))
    rows = live.ledger()
    manifest["baseline"] = {rows[0]["id"]: fingerprint(rows[0])}
    assert live.inspect(manifest, rows) == ({}, set())
    rows[0]["reason"] = "rewritten"
    with pytest.raises(ValueError):
        live.inspect(manifest, rows)


def test_overruns_recorded_without_hiding_or_retrying(experiment):
    manifest, store = experiment
    transport = FakeTransport("overrun")
    assert asyncio.run(live.dispatch(manifest, client(store, transport))) == "finished"
    assert transport.calls == 32
    result = live.report(manifest, live.ledger())
    assert all(row["provider_input_overrun"] for row in result["rows"])
    assert result["known_input_tokens"] == 128000
    assert result["known_output_tokens"] == 128
    assert not result["cost_uncertain"]
    assert sum(g["input_overruns"] for g in result["groups"]) == 32


def test_minute_pacing_has_a_bounded_wait(experiment, monkeypatch):
    manifest, store = experiment
    monkeypatch.setattr(live, "pacing", lambda *args: ("minute_wait", 30))
    transport = FakeTransport()
    assert asyncio.run(live.dispatch(manifest, client(store, transport))) == "minute_wait"
    assert transport.calls == 0
    assert not list(live.RUN.glob("claim-*.json"))


def test_conservative_admission_margin():
    now = 864000.0
    row = {
        "state": "completed",
        "cost": 0,
        "charged_tokens": 6500,
        "created": now,
        "settled": now,
        "request_count": 1,
    }
    assert live.pacing([row], 1256, now)[0] == "minute_wait"


def test_strict_json_not_old_normalization(experiment):
    manifest, store = experiment
    transport = FakeTransport()
    assert asyncio.run(live.dispatch(manifest, client(store, transport))) == "finished"
    result = live.report(manifest, live.ledger())
    assert all(r["conforming"] for r in result["rows"])
    assert sum(r["correct_abstention"] for r in result["rows"]) == 8
    assert sum(r["wrong_abstention"] for r in result["rows"]) == 24
    assert len(result["pairs"]) == 16
    assert result["quality_target"] == "NOT_EVALUATED"
