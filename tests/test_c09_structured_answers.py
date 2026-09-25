"""Offline structured payload, full-schema accounting and caller-boundary checks."""

import asyncio
import importlib.util
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from context_engine.answers import AnswerContract
from context_engine.config import BudgetConfig
from context_engine.errors import ContractError, PromptTooLarge
from context_engine.models import ChatRequest, Message, Role, Scope, ToolDefinition, canonical_json
from context_engine.providers.contracts import (
    Completion,
    GenerationConfig,
    PriceCard,
    QuotaPolicy,
    Usage,
)
from context_engine.providers.store import RuntimeStore
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "structured_answers", ROOT / "examples/structured_answers.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
scope = Scope("offline", "structured")
request = ChatRequest((Message("q", Role.USER, "Synthetic question"),))
generation = module.StructuredGeneration(
    model="openai/gpt-oss-20b", contract=AnswerContract("ascii_identifier")
)


class Fake:
    namespace = "offline-structured"

    def __init__(self):
        self.payloads = []

    async def send(self, payload, api_key, timeout):
        self.payloads.append(payload)
        return Completion(
            generation.model, "offline-reply", '{"answer":"node-52"}', "stop", Usage(90, 12, 0, 0)
        )


def make_client(tmp_path):
    fake = Fake()
    client = module.StructuredAnswerClient(
        generation=generation,
        store=RuntimeStore(tmp_path / "account.sqlite"),
        quota=QuotaPolicy("offline-structured", billing_mode="free_tier"),
        prices=PriceCard("offline-free", 0, 0, 0),
        api_key="test-only",
        transport=fake,
    )
    return client, fake


def call(client, budget=None):
    return asyncio.run(
        client.complete(
            request,
            budget or BudgetConfig(input_cap=900),
            scope=scope,
            security_scope="test",
            snapshot_revision="1",
            policy_version="structured-v1",
        )
    )


def test_wire_schema_no_local_metadata_and_no_request_mutation():
    before = request.to_wire()
    payload = generation.to_wire(request)
    schema = payload["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert schema["schema"] == {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    assert "contract" not in payload
    assert payload["stream"] is False and payload["max_completion_tokens"] == 256
    assert request.to_wire() == before
    assert "response_format" not in GenerationConfig().to_wire(request)


def test_schema_counted_and_usage_settled(tmp_path):
    client, fake = make_client(tmp_path)
    estimate = client.counter.count_request(request)
    assert estimate.estimated_tokens > TiktokenCounter().count_request(request).estimated_tokens
    expected = {**request.to_wire(), "response_format": generation.response_format()}
    assert client.counter.serializer.serialize(request) == canonical_json(expected)
    completed = call(client)
    assert generation.contract.parse(completed.completion.content) == "node-52"
    assert fake.payloads == [generation.to_wire(request)]
    with sqlite3.connect(tmp_path / "account.sqlite") as db:
        reserved, charged = db.execute(
            "SELECT reserved_tokens, charged_tokens FROM attempts"
        ).fetchone()
    assert reserved == estimate.estimated_tokens + 256 and charged == 102


def test_schema_overflow_rejected_before_dispatch(tmp_path):
    client, fake = make_client(tmp_path)
    cap = client.counter.count_request(request).estimated_tokens - 1
    budget = BudgetConfig(input_cap=cap, retrieval_reserve=0, summary_reserve=0)
    with pytest.raises(PromptTooLarge):
        call(client, budget)
    assert not fake.payloads


@pytest.mark.parametrize("mutation", ["generation", "counter", "retries"])
def test_mismatched_settings_fail_before_dispatch(tmp_path, mutation):
    client, fake = make_client(tmp_path)
    if mutation == "generation":
        client.generation = replace(generation, contract=AnswerContract("integer"))
    elif mutation == "counter":
        client.counter = TiktokenCounter()
    else:
        client.retries = replace(client.retries, max_attempts=2)
    with pytest.raises(ContractError):
        call(client)
    assert not fake.payloads


def test_tool_schema_rejected():
    tool = ToolDefinition("lookup", "Synthetic tool", '{"type":"object"}')
    with pytest.raises(ContractError):
        generation.to_wire(ChatRequest(request.messages, (tool,)))


@pytest.mark.parametrize("kwargs", [{"tool_choice": "auto"}, {"contract": "bad"}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ContractError):
        module.StructuredGeneration(**kwargs)


def test_local_contract_still_rejects_empty_value():
    with pytest.raises(ContractError):
        generation.contract.parse('{"answer":""}')


def test_wire_schema_is_fresh_per_request():
    payload = generation.to_wire(request)
    payload["response_format"]["json_schema"]["strict"] = False
    assert generation.to_wire(request)["response_format"]["json_schema"]["strict"] is True


def test_schema_changes_payload_identity(tmp_path):
    from context_engine.providers.client import ProviderClient

    client, fake = make_client(tmp_path)
    structured = call(client)
    plain = ProviderClient(
        store=client.store,
        quota=client.quota,
        prices=client.prices,
        api_key="test-only",
        transport=fake,
        generation=GenerationConfig(model=generation.model),
        retries=client.retries,
    )
    unstructured = call(plain)
    assert structured.request_key != unstructured.request_key
    assert len(fake.payloads) == 2
    assert "response_format" in fake.payloads[0]
    assert "response_format" not in fake.payloads[1]
