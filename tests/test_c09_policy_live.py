"""Offline fake16-call cap,receipt attribution,grading and safe-stop checks."""

import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

from context_engine.providers.contracts import Completion, Usage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "policy_live_test", ROOT / "scripts/c09_policy_live.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture(scope="module", autouse=True)
def candidate_runtime(candidate_harness):
    candidate_harness(module.q)


def test_alternating_unique_payloads_and_bounded_configuration(monkeypatch):
    monkeypatch.setattr(module.live, "configuration", lambda: None)
    identity = module.identity()
    rows = identity["preparation"]["rows"]
    assert identity["max_calls"] == len(rows) == 16
    assert identity["approval"] == "D088"
    assert identity["retries"]["max_attempts"] == 1
    assert {r["budget"] for r in rows} == {900}
    assert len({r["payload_hash"] for r in rows}) == 16
    assert [r["variant"] for r in rows[:4]] == ["BASELINE", "CANDIDATE", "CANDIDATE", "BASELINE"]


@pytest.mark.parametrize("mode", ["correct", "empty", "truncated"])
def test_dispatch_reporting_and_no_resend(tmp_path, monkeypatch, mode):
    live = module.live
    monkeypatch.setattr(live, "configuration", lambda: None)
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    live.RUN.mkdir()
    store = live.RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    manifest = module.identity()
    manifest.update(baseline={}, provenance="TEST_ONLY")
    live.save(live.RUN / "manifest.json", manifest)
    truth = live.read(module.q.DIRECTORY / "truth.json")

    class Fake:
        namespace = live.GroqTransport().namespace
        calls = 0

        async def send(self, payload, api_key, timeout):
            plan = manifest["preparation"]["rows"][self.calls]
            assert module.q.fingerprint(payload) == plan["payload_hash"]
            assert payload["response_format"]["json_schema"]["strict"] is True
            assert payload["max_completion_tokens"] == 256
            self.calls += 1
            return Completion(
                live.MODEL,
                f"fake-{self.calls}",
                "" if mode == "empty" else json.dumps({"answer": truth[plan["case"]]}),
                "length" if mode == "truncated" else "stop",
                Usage(40, 20, 0, 0),
            )

    fake = Fake()
    client = live.ProviderClient(
        store=store,
        quota=live.POLICY,
        prices=live.PRICES,
        api_key="offline",
        generation=live.GENERATION,
        retries=live.RETRIES,
        transport=fake,
    )
    first = asyncio.run(live.dispatch(manifest, client))
    second = asyncio.run(live.dispatch(manifest, client))
    if mode == "truncated":
        assert first == "provider_error_or_unknown_usage" and second == "preserved_error"
        assert fake.calls == 1
    else:
        assert first == second == "finished"
        assert fake.calls == 16
    report = module.report(manifest, live.ledger())
    assert report["quality_target"] == "NOT_EVALUATED"  # Fake answers never become live proof.
    assert report["broader_c09_gate"] == "OPEN"
    assert report["provider_attempts"] == fake.calls
    assert report["charged_tokens"] == 60 * fake.calls
    assert all(g["planned"] == 8 for g in report["groups"])
    if mode == "correct":
        assert all(g["correct"] == g["conforming"] == 8 for g in report["groups"])
        assert all(
            g["answerable_correct"] == g["abstention_correct"] == 4 for g in report["groups"]
        )
    else:
        assert all(g["correct"] == g["conforming"] == 0 for g in report["groups"])


def test_claim_without_receipt_cannot_be_reissued(tmp_path, monkeypatch):
    live = module.live
    monkeypatch.setattr(live, "configuration", lambda: None)
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    live.RUN.mkdir()
    store = live.RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    manifest = module.identity()
    manifest.update(baseline={}, provenance="TEST_ONLY")
    live.save(live.RUN / "manifest.json", manifest)
    execution = live.fingerprint(manifest)
    live.save(
        live.RUN / "claim-00.json",
        {
            "execution_id": execution,
            "slot": 0,
            "request_key": live.request_key(manifest["preparation"]["rows"][0], execution),
        },
    )
    assert asyncio.run(live.dispatch(manifest, None)) == "unreceipted_claim"
    assert module.report(manifest, live.ledger())["cost_uncertain"] is True
