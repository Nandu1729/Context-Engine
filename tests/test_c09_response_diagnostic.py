"""No-network diagnostic metadata, bounds and parser transparency checks."""

import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "diagnostic", ROOT / "scripts/c09_response_diagnostic.py"
)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


@pytest.mark.parametrize("content", ["", " ", '{"answer":"node-3"}'])
def test_shape_excludes_content_reasoning_and_arbitrary_fields(content):
    raw = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": content,
                        "reasoning": "SECRET_THOUGHT",
                        "refusal": "SECRET_REFUSAL",
                        "SECRET_FIELD": "SECRET_VALUE",
                    },
                }
            ],
            "api_key": "SECRET_KEY",
        }
    ).encode()
    shape = diagnostic.response_shape(raw)
    assert "SECRET" not in json.dumps(shape)
    assert shape["content"]["characters"] == len(content)
    assert shape["content"]["blank"] == (not content.strip())


@pytest.mark.parametrize("raw", [b"broken SECRET", b"[]", b'{"choices":[]}'])
def test_invalid_shape_is_content_free(raw):
    shape = diagnostic.response_shape(raw)
    assert shape["unrecognized_shape"]
    assert "SECRET" not in json.dumps(shape)


def test_identity_limits_slots_and_preserves_payload(monkeypatch):
    monkeypatch.setattr(diagnostic.live, "configuration", lambda: None)
    original = diagnostic.parent.qualification.prepare()
    identity = diagnostic.identity()
    assert identity["approval"] == "D082" and identity["max_calls"] == 2
    selected = identity["preparation"]["rows"]
    assert [(r["case"], r["variant"], r["budget"]) for r in selected] == [
        ("q2-long", "PRIMARY", 900),
        ("q2-conflict", "CONTROL", 900),
    ]
    assert all(r in original["rows"] for r in selected)
    assert identity["preparation"]["planned_slots"] == 2


def test_observer_is_transparent_and_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic.live, "RUN", tmp_path)
    monkeypatch.setattr(diagnostic, "SHAPES", tmp_path)
    diagnostic.live.save(tmp_path / "claim-00.json", {"slot": 0})
    raw = json.dumps(
        {
            "id": "test",
            "object": "chat.completion",
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "", "reasoning": "SECRET_THOUGHT"},
                }
            ],
            "usage": {"prompt_tokens": 40, "completion_tokens": 47, "total_tokens": 87},
        }
    ).encode()
    expected = diagnostic.native_parse(raw, "openai/gpt-oss-20b")
    assert diagnostic.observed_parse(raw, "openai/gpt-oss-20b") == expected
    saved = (tmp_path / "shape-00.json").read_text()
    assert "SECRET_THOUGHT" not in saved
    assert json.loads(saved)["content"]["characters"] == 0
    with pytest.raises(FileExistsError):
        diagnostic.observed_parse(raw, "openai/gpt-oss-20b")


def test_two_attempt_cap_and_no_resend(tmp_path, monkeypatch):
    live = diagnostic.live
    monkeypatch.setattr(live, "configuration", lambda: None)
    monkeypatch.setattr(live, "LEDGER", tmp_path / "ledger.sqlite")
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    monkeypatch.setattr(diagnostic, "SHAPES", tmp_path / "shapes")
    live.RUN.mkdir()
    diagnostic.SHAPES.mkdir()
    store = live.RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    manifest = diagnostic.identity()
    manifest.update(baseline={}, provenance="TEST_ONLY")
    live.save(live.RUN / "manifest.json", manifest)

    class Fake:
        namespace = live.GroqTransport().namespace
        calls = 0

        async def send(self, payload, api_key, timeout):
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
                            "message": {"role": "assistant", "content": ""},
                        }
                    ],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 47, "total_tokens": 87},
                }
            ).encode()
            return diagnostic.observed_parse(raw, live.MODEL)

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
    report = diagnostic.report(manifest, live.ledger())
    assert report["provider_attempts"] == report["planned"] == 2
    assert len(report["response_shapes"]) == 2
    assert report["quality_target"] == "NOT_EVALUATED"
