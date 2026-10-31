"""Provider and framework message adapters. Optional; no provider SDK is imported.

Assembly output is one system message, user data blocks and the user question, plus
optional tool schemas. These helpers reshape it for common clients:

    client.chat.completions.create(model=..., **openai_chat(result))
    client.messages.create(model=..., max_tokens=..., **anthropic_messages(result))
    chat_model.invoke(langchain_messages(result))   # needs the [langchain] extra

`turns_from_openai` goes the other way: it converts an existing OpenAI-style chat
history into `Turn`s for `assemble_context` or `MemoryStore`.
"""

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime

from .errors import ContractError
from .models import ChatRequest, Message, Role, Scope, ToolCall, Turn


def _request(result) -> ChatRequest:
    request = getattr(result, "request", result)
    if not isinstance(request, ChatRequest):
        raise ContractError("Expected an AssembledContext or ChatRequest")
    return request


def openai_chat(result) -> dict:
    """`messages` (and `tools`, when present) for OpenAI-compatible chat APIs."""
    return _request(result).to_wire()


def anthropic_messages(result) -> dict:
    """`system`, `messages` (and `tools`) for the Anthropic Messages API.

    The system prompt becomes the top-level `system` field; consecutive user data
    blocks are merged into one user turn of text blocks, as the API expects.
    """
    request = _request(result)
    system, messages = [], []
    for message in request.messages:
        if message.role == Role.SYSTEM:
            system.append(message.content)
        elif message.role == Role.USER and not message.tool_calls:
            block = {"type": "text", "text": message.content}
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"].append(block)
            else:
                messages.append({"role": "user", "content": [block]})
        else:
            raise ContractError("Anthropic adapter supports assembled system/user messages only")
    payload: dict = {"system": "\n\n".join(system), "messages": messages}
    if request.tools:
        payload["tools"] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": json.loads(tool.parameters_json),
            }
            for tool in request.tools
        ]
    return payload


def langchain_messages(result) -> list:
    """LangChain `SystemMessage`/`HumanMessage` objects; needs `langchain-core`."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError:
        raise ImportError(
            "langchain_messages needs langchain-core: "
            "pip install 'context-engineering-core[langchain]'"
        ) from None
    converted = []
    for message in _request(result).messages:
        if message.role == Role.SYSTEM:
            converted.append(SystemMessage(content=message.content))
        elif message.role == Role.USER and not message.tool_calls:
            converted.append(HumanMessage(content=message.content))
        else:
            raise ContractError("LangChain adapter supports assembled system/user messages only")
    return converted


def _text(content, index: int) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(
        isinstance(part, Mapping) and part.get("type") == "text" for part in content
    ):
        return "".join(str(part.get("text", "")) for part in content)
    raise ContractError("Only text message content is supported", field=f"messages[{index}]")


def turns_from_openai(
    messages: Iterable[Mapping],
    scope: Scope,
    *,
    id_prefix: str = "",
    timestamp: datetime | None = None,
) -> tuple[Turn, ...]:
    """Group an OpenAI-style history into turns: each user message starts a new turn.

    IDs come from positions (`{id_prefix}t{n}` / `{id_prefix}m{i}`), so converting
    the same history twice yields the same IDs and provenance. Pass the system prompt
    to `assemble_context(system=...)` instead of including it here.
    """
    if not isinstance(scope, Scope):
        raise ContractError("turns_from_openai requires a Scope")
    at = timestamp or datetime.now(UTC)
    groups: list[list[Message]] = []
    for index, item in enumerate(messages):
        if not isinstance(item, Mapping):
            raise ContractError("Each message must be a mapping", field=f"messages[{index}]")
        role = item.get("role")
        if role == "system" or role == "developer":
            raise ContractError(
                "Pass system instructions via system=, not history", field=f"messages[{index}]"
            )
        if role not in ("user", "assistant", "tool"):
            raise ContractError("Unsupported message role", field=f"messages[{index}]")
        try:
            calls = tuple(
                ToolCall(call["id"], call["function"]["name"], call["function"]["arguments"])
                for call in item.get("tool_calls") or ()
            )
        except (KeyError, TypeError):
            raise ContractError("Malformed tool call", field=f"messages[{index}]") from None
        message = Message(
            f"{id_prefix}m{index}",
            Role(role),
            _text(item.get("content"), index),
            tool_call_id=item.get("tool_call_id"),
            tool_calls=calls,
        )
        if role == "user" or not groups:
            groups.append([])
        groups[-1].append(message)
    return tuple(
        Turn(f"{id_prefix}t{number}", scope, tuple(group), timestamp=at)
        for number, group in enumerate(groups)
    )


__all__ = ["anthropic_messages", "langchain_messages", "openai_chat", "turns_from_openai"]
