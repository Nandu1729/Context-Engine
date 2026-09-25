"""Offline response-boundary diagnosis and opt-in application integration."""

import asyncio
import importlib.util
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from context_engine.answers import AnswerContract
from context_engine.config import BudgetConfig
from context_engine.models import ChatRequest, Message, Role, Scope
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    Completion,
    GenerationConfig,
    ModelResult,
    PriceCard,
    QuotaPolicy,
    RetryConfig,
    TransportFailure,
    Usage,
)
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import parse_completion

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "answer_boundary", ROOT / "examples/validated_answer.py"
)
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)
MODEL = "openai/gpt-oss-20b"
CONTRACT = AnswerContract("ascii_identifier")


def payload(content):
    return json.dumps(
        {
            "id": "offline-example",
            "object": "chat.completion",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning": "PRIVATE_REASONING_NOT_AN_ANSWER",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 47,
                "total_tokens": 87,
                "completion_tokens_details": {"reasoning_tokens": 31},
            },
        }
    ).encode()


def result(content, status="success"):
    return ModelResult(
        status,
        "offline-request",
        ("offline-attempt",),
        Completion(MODEL, "offline-response", content, "stop", Usage(40, 47, 0, 31)),
        new_cost_microusd=0,
    )


@pytest.mark.parametrize("content", ["", "  ", '{"answer":"node-52"}'])
def test_transport_preserves_content_verbatim(content):
    parsed = parse_completion(payload(content), MODEL)
    assert parsed.content == content
    assert parsed.usage.total_tokens == 87
    assert "PRIVATE_REASONING" not in parsed.content


def test_stop_with_null_is_not_silently_converted_to_empty():
    with pytest.raises(TransportFailure) as error:
        parse_completion(payload(None), MODEL)
    assert error.value.code == "invalid_response"
    assert error.value.usage.total_tokens == 87


@pytest.mark.parametrize(
    "content,reason",
    [
        ("", "empty_answer"),
        (" \n\t", "empty_answer"),
        ('{"answer":"node‑52"}', "invalid_answer"),
        ('{"answer":"node-52"} PRIVATE_EXTRA', "invalid_answer"),
        ('{"answer":""}', "invalid_answer"),
    ],
)
def test_unusable_answer_rejected_without_mutating_result(content, reason):
    original = result(content)
    before = original.to_dict(include_content=True)
    with pytest.raises(boundary.UnusableAnswer) as error:
        boundary.validate_answer(original, CONTRACT)
    assert error.value.details["reason"] == reason
    assert "PRIVATE_EXTRA" not in str(error.value.to_dict())
    assert original.to_dict(include_content=True) == before


@pytest.mark.parametrize("status", ["success", "replay"])
@pytest.mark.parametrize("answer", ["node-52", "UNKNOWN"])
def test_valid_answer_or_abstention_preserved(status, answer):
    original = result(json.dumps({"answer": answer}), status)
    assert boundary.validate_answer(original, CONTRACT) == answer


@pytest.mark.parametrize("status", ["error", "truncated", "filtered", "tool_calls"])
def test_non_success_never_promoted(status):
    with pytest.raises(boundary.UnusableAnswer) as error:
        boundary.validate_answer(result('{"answer":"node-52"}', status), CONTRACT)
    assert error.value.details["reason"] == "provider_not_completed"


def test_inconsistent_success_without_completion_rejected():
    with pytest.raises(boundary.UnusableAnswer):
        boundary.validate_answer(replace(result(""), completion=None), CONTRACT)


def test_saved_five_empty_receipts_rejected_without_regrading():
    report = json.loads((ROOT / "output/c09-qualification-live-002/report.json").read_text())
    empty = [r for r in report["receipts"].values() if r["result"]["completion"]["content"] == ""]
    assert len(empty) == 5
    for receipt in empty:
        recorded = receipt["result"]
        original = ModelResult(
            recorded["status"],
            recorded["request_key"],
            tuple(recorded["attempt_ids"]),
            Completion.from_dict(recorded["completion"]),
            new_cost_microusd=recorded["new_cost_microusd"],
        )
        assert original.status == "success"
        assert original.completion.finish_reason == "stop"
        assert original.completion.usage.output_tokens < 256
        with pytest.raises(boundary.UnusableAnswer) as error:
            boundary.validate_answer(original, CONTRACT)
        assert error.value.details["reason"] == "empty_answer"
    assert report["quality_target"] == "FAIL"


def test_client_settles_empty_stop_once_then_caller_rejects(tmp_path):
    class Transport:
        namespace = "offline-empty-answer"
        calls = 0

        async def send(self, body, api_key, timeout):
            self.calls += 1
            return parse_completion(payload(""), MODEL)

    transport = Transport()
    path = tmp_path / "test-ledger.sqlite"
    client = ProviderClient(
        store=RuntimeStore(path),
        quota=QuotaPolicy("offline-only", billing_mode="free_tier"),
        prices=PriceCard("offline-free", 0, 0, 0),
        api_key="test-only",
        transport=transport,
        generation=GenerationConfig(model=MODEL),
        retries=RetryConfig(max_attempts=3),
    )
    request = ChatRequest((Message("q", Role.USER, "Synthetic question"),))
    completed = asyncio.run(
        client.complete(
            request,
            BudgetConfig(input_cap=900),
            scope=Scope("offline", "empty"),
            security_scope="test",
            snapshot_revision="1",
            policy_version="1",
        )
    )
    assert completed.status == "success"  # Historical adapter means protocol completion.
    assert len(completed.attempt_ids) == transport.calls == 1
    with sqlite3.connect(path) as db:
        before = db.execute("SELECT state, charged_tokens, cost FROM attempts").fetchall()
    with pytest.raises(boundary.UnusableAnswer):
        boundary.validate_answer(completed, CONTRACT)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT state, charged_tokens, cost FROM attempts").fetchall() == before
    assert before == [("completed", 87, 0)]
    assert transport.calls == 1  # Caller validation never dispatches/retries.
