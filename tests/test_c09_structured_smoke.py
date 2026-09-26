"""Offline end-to-end checks for the separately frozen two-call smoke."""

import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke", ROOT / "scripts/c09_structured_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.fixture(scope="module", autouse=True)
def candidate_runtime(candidate_harness):
    candidate_harness(smoke.qualification)


def test_identity_and_schema_accounting(monkeypatch):
    monkeypatch.setattr(smoke.live, "configuration", lambda: None)
    identity = smoke.identity()
    assert identity["approval"] == "D084" and identity["max_calls"] == 2
    assert identity["retries"]["max_attempts"] == 1
    rows = identity["preparation"]["rows"]
    assert [(r["case"], r["variant"], r["budget"]) for r in rows] == [
        ("q2-long", "PRIMARY", 900),
        ("q2-conflict", "CONTROL", 900),
    ]
    for row in rows:
        request, _, _ = smoke.reconstruct(row)
        assert "response_format" in smoke.counter().serializer.serialize(request)
        assert row["estimated_tokens"] <= 900


@pytest.mark.parametrize(
    "answers", [('{"answer":"snap-782"}', '{"answer":"UNKNOWN"}'), ("", "bad JSON")]
)
def test_two_calls_bound_receipts_and_no_resend(tmp_path, monkeypatch, answers):
    live = smoke.live
    monkeypatch.setattr(live, "configuration", lambda: None)
    monkeypatch.setattr(live, "LEDGER", tmp_path / "ledger.sqlite")
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    monkeypatch.setattr(smoke.diagnostic, "SHAPES", tmp_path / "shapes")
    live.RUN.mkdir()
    smoke.diagnostic.SHAPES.mkdir()
    store = live.RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    manifest = smoke.identity()
    manifest.update(baseline={}, provenance="TEST_ONLY")
    live.save(live.RUN / "manifest.json", manifest)

    class Fake:
        namespace = live.GroqTransport().namespace
        calls = 0

        async def send(self, payload, api_key, timeout):
            assert payload["response_format"]["json_schema"]["strict"] is True
            assert payload["max_completion_tokens"] == 256
            assert "contract" not in payload
            content = answers[self.calls]
            self.calls += 1
            raw = json.dumps(
                {
                    "id": f"test-{self.calls}",
                    "object": "chat.completion",
                    "model": live.MODEL,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 47, "total_tokens": 87},
                }
            ).encode()
            return smoke.diagnostic.observed_parse(raw, live.MODEL)

    transport = Fake()
    client = live.ProviderClient(
        store=store,
        quota=live.POLICY,
        prices=live.PRICES,
        api_key="offline-only",
        generation=live.GENERATION,
        retries=live.RETRIES,
        transport=transport,
    )
    assert asyncio.run(live.dispatch(manifest, client)) == "finished"
    assert asyncio.run(live.dispatch(manifest, client)) == "finished"
    assert transport.calls == 2
    report = smoke.report(manifest, live.ledger())
    assert report["provider_attempts"] == report["planned"] == 2
    assert report["quality_target"] == "NOT_EVALUATED"
    assert report["answer_quality"] == "SMOKE_ONLY"
    assert [r["conforming"] for r in report["outcomes"]] == [bool(answers[0])] * 2
    assert report["charged_tokens"] == 174
