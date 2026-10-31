"""Offline adapter tests: provider payload shapes and OpenAI-history conversion."""

import json
import sys
import types
from dataclasses import dataclass

import pytest

from context_engine import assemble_context
from context_engine.adapters import (
    anthropic_messages,
    langchain_messages,
    openai_chat,
    turns_from_openai,
)
from context_engine.config import BudgetConfig
from context_engine.errors import ContractError
from context_engine.models import ChatRequest, KeyedPins, Message, Role, Scope, ToolDefinition

SCOPE = Scope("tenant", "chat")
HISTORY = [
    {"role": "user", "content": "Ship order 7 from dock D-7."},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "ship", "arguments": "{}"}}
        ],
    },
    {"role": "tool", "tool_call_id": "c1", "content": "queued"},
    {"role": "assistant", "content": [{"type": "text", "text": "Order 7 is queued."}]},
    {"role": "user", "content": "Thanks."},
]
TOOL = ToolDefinition("ship", "Ship an order", '{"type":"object","properties":{}}')


@pytest.fixture(scope="module")
def result():
    turns = turns_from_openai(HISTORY * 40, SCOPE)
    return assemble_context(
        turns,
        "Which dock did order 7 use?",
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=900),
        system="Answer from the context.",
        tools=(TOOL,),
    )


def test_turns_from_openai_groups_by_user_message_with_stable_ids():
    turns = turns_from_openai(HISTORY, SCOPE, id_prefix="x-")
    assert [t.turn_id for t in turns] == ["x-t0", "x-t1"]
    assert [m.role for m in turns[0].messages] == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
    ]
    assert turns[0].messages[1].tool_calls[0].name == "ship"
    assert turns[0].messages[2].tool_call_id == "c1"
    assert turns[0].messages[3].content == "Order 7 is queued."
    again = turns_from_openai(HISTORY, SCOPE, id_prefix="x-")
    assert [t.content_hash for t in again] == [t.content_hash for t in turns]


@pytest.mark.parametrize(
    "bad",
    [
        [{"role": "system", "content": "be nice"}],
        [{"role": "bot", "content": "?"}],
        [{"role": "user", "content": [{"type": "image_url", "image_url": {}}]}],
        [{"role": "assistant", "content": "", "tool_calls": [{"id": "c"}]}],
        ["not a mapping"],
    ],
)
def test_turns_from_openai_rejects_unsupported_input(bad):
    with pytest.raises(ContractError):
        turns_from_openai(bad, SCOPE)


def test_openai_payload_is_the_budgeted_wire_request(result):
    payload = openai_chat(result)
    assert payload == result.request.to_wire()
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][-1] == {"role": "user", "content": "Which dock did order 7 use?"}
    assert payload["tools"][0]["function"]["name"] == "ship"
    assert "D-7" in json.dumps(payload)  # Retrieved evidence survives the adapter.


def test_anthropic_payload_moves_system_and_merges_user_blocks(result):
    payload = anthropic_messages(result)
    assert payload["system"] == "Answer from the context."
    assert [m["role"] for m in payload["messages"]] == ["user"]
    blocks = payload["messages"][0]["content"]
    user_messages = [m for m in result.messages if m["role"] == "user"]
    assert [b["text"] for b in blocks] == [m["content"] for m in user_messages]
    assert payload["tools"] == [
        {
            "name": "ship",
            "description": "Ship an order",
            "input_schema": json.loads(TOOL.parameters_json),
        }
    ]


def test_adapters_accept_a_request_and_reject_other_shapes(result):
    assert openai_chat(result.request) == openai_chat(result)
    with pytest.raises(ContractError):
        openai_chat({"messages": []})
    assistant = ChatRequest((Message("a", Role.USER, "q"), Message("b", Role.ASSISTANT, "x")))
    with pytest.raises(ContractError):
        anthropic_messages(assistant)


def test_langchain_adapter_maps_roles_with_lazy_import(result, monkeypatch):
    @dataclass
    class SystemMessage:
        content: str

    @dataclass
    class HumanMessage:
        content: str

    messages = types.ModuleType("langchain_core.messages")
    messages.SystemMessage, messages.HumanMessage = SystemMessage, HumanMessage
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.messages", messages)
    converted = langchain_messages(result)
    assert (
        isinstance(converted[0], SystemMessage)
        and converted[0].content == "Answer from the context."
    )
    assert all(isinstance(m, HumanMessage) for m in converted[1:])
    assert [m.content for m in converted] == [m["content"] for m in result.messages]


def test_langchain_adapter_explains_missing_extra(result, monkeypatch):
    monkeypatch.setitem(sys.modules, "langchain_core", None)
    monkeypatch.setitem(sys.modules, "langchain_core.messages", None)
    with pytest.raises(ImportError, match=r"\[langchain\]"):
        langchain_messages(result)
