"""Immutable source and chat contracts. Scope is a label, never authorization."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .errors import ContractError


def text_value(name: str, value: str, *, nonempty: bool = True) -> None:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ContractError("Expected text", field=name)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ContractError("Text contains invalid Unicode", field=name) from None


def integer_value(name: str, value: int, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ContractError("Expected an integer within range", field=name, minimum=minimum)


def aware_time(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractError("Timestamp must have a timezone", field=name)


def canonical_json(value: Any) -> str:
    try:
        result = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        result.encode("utf-8")
        return result
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ContractError("Value must be valid JSON with valid Unicode") from None


def object_json(value: str) -> str:
    text_value("json", value)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, item in pairs:
            if key in result:
                raise ContractError("JSON object keys must be unique")
            result[key] = item
        return result

    try:
        parsed = json.loads(value, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise ContractError("Expected a JSON object") from None
    if not isinstance(parsed, dict):
        raise ContractError("Expected a JSON object")
    return canonical_json(parsed)


def freeze_sequence(instance: Any, name: str, item_type: type) -> tuple:
    raw = getattr(instance, name)
    if not isinstance(raw, (tuple, list)) or any(not isinstance(item, item_type) for item in raw):
        raise ContractError("Invalid sequence contents", field=name)
    frozen = tuple(raw)
    object.__setattr__(instance, name, frozen)
    return frozen


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class BlockKind(StrEnum):
    SYSTEM = "system"
    PINNED = "pinned"
    SUMMARY = "summary"
    WINDOW = "window"
    RETRIEVED = "retrieved"
    QUESTION = "question"


@dataclass(frozen=True, slots=True)
class Scope:
    tenant_id: str
    session_id: str

    def __post_init__(self) -> None:
        text_value("tenant_id", self.tenant_id)
        text_value("session_id", self.session_id)


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments_json: str

    def __post_init__(self) -> None:
        text_value("call_id", self.call_id)
        text_value("name", self.name)
        object_json(self.arguments_json)  # Validate without rewriting original call bytes.

    def to_wire(self) -> dict:
        return {
            "id": self.call_id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments_json},
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters_json: str

    def __post_init__(self) -> None:
        text_value("name", self.name)
        text_value("description", self.description, nonempty=False)
        object.__setattr__(self, "parameters_json", object_json(self.parameters_json))

    def to_wire(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": json.loads(self.parameters_json),
            },
        }


@dataclass(frozen=True, slots=True)
class Message:
    message_id: str
    role: Role
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    def __post_init__(self) -> None:
        text_value("message_id", self.message_id)
        text_value("content", self.content, nonempty=False)
        try:
            object.__setattr__(self, "role", Role(self.role))
        except (ValueError, TypeError):
            raise ContractError("Unsupported message role") from None
        calls = freeze_sequence(self, "tool_calls", ToolCall)
        if len({call.call_id for call in calls}) != len(calls):
            raise ContractError("Duplicate tool call IDs")
        if calls and self.role != Role.ASSISTANT:
            raise ContractError("Only assistant messages can contain tool calls")
        if self.role == Role.TOOL:
            text_value("tool_call_id", self.tool_call_id)
        elif self.tool_call_id is not None:
            raise ContractError("Only tool results can carry tool_call_id")

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_wire(self) -> dict:
        result: dict = {"role": self.role.value, "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [call.to_wire() for call in self.tool_calls]
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass(frozen=True, slots=True)
class Turn:
    turn_id: str
    scope: Scope
    messages: tuple[Message, ...]
    revision: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        text_value("turn_id", self.turn_id)
        if not isinstance(self.scope, Scope):
            raise ContractError("Turn requires a scope")
        messages = freeze_sequence(self, "messages", Message)
        if not messages or len({m.message_id for m in messages}) != len(messages):
            raise ContractError("A turn requires messages with unique IDs")
        integer_value("revision", self.revision, minimum=1)
        aware_time("timestamp", self.timestamp)

    @property
    def content_hash(self) -> str:
        payload = [{"message_id": m.message_id, **m.to_wire()} for m in self.messages]
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceRef:
    scope: Scope
    turn_id: str
    message_id: str
    revision: int
    start: int
    end: int
    message_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ContractError("Source requires a scope")
        text_value("turn_id", self.turn_id)
        text_value("message_id", self.message_id)
        integer_value("revision", self.revision, minimum=1)
        integer_value("start", self.start)
        integer_value("end", self.end)
        if self.end <= self.start:
            raise ContractError("Source range must be nonempty and increasing")
        if (
            not isinstance(self.message_hash, str)
            or len(self.message_hash) != 64
            or any(c not in "0123456789abcdef" for c in self.message_hash)
        ):
            raise ContractError("Source hash must be a lowercase SHA-256 digest")

    def extract(self, turn: Turn) -> str:
        """Offsets are Unicode code points, validated against the original revision."""
        if (turn.scope, turn.turn_id, turn.revision) != (self.scope, self.turn_id, self.revision):
            raise ContractError("Source scope or revision mismatch")
        message = next((m for m in turn.messages if m.message_id == self.message_id), None)
        if (
            message is None
            or message.content_hash != self.message_hash
            or self.end > len(message.content)
        ):
            raise ContractError("Source message, hash or range mismatch")
        return message.content[self.start : self.end]


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    source: SourceRef
    content: str
    chunker_version: str

    def __post_init__(self) -> None:
        text_value("chunk_id", self.chunk_id)
        text_value("content", self.content)
        text_value("chunker_version", self.chunker_version)
        if not isinstance(self.source, SourceRef):
            raise ContractError("Chunk requires a source reference")
        if len(self.content) != self.source.end - self.source.start:
            raise ContractError("Chunk length does not match source range")

    def validate_source(self, turn: Turn) -> None:
        if self.source.extract(turn) != self.content:
            raise ContractError("Chunk content does not match original source")


@dataclass(frozen=True, slots=True)
class Pin:
    scope: Scope
    key: str
    value: str
    origin: str
    revision: int = 1
    effective_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    source: SourceRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ContractError("Pin requires a scope")
        for name in ("key", "value", "origin"):
            text_value(name, getattr(self, name))
        integer_value("revision", self.revision, minimum=1)
        aware_time("effective_at", self.effective_at)
        if self.expires_at is not None:
            aware_time("expires_at", self.expires_at)
            if self.expires_at <= self.effective_at:
                raise ContractError("Pin expiry must follow its effective time")
        if self.source is not None and (
            not isinstance(self.source, SourceRef) or self.source.scope != self.scope
        ):
            raise ContractError("Pin source scope mismatch")

    def is_active(self, at: datetime) -> bool:
        aware_time("at", at)
        return self.effective_at <= at and (self.expires_at is None or at < self.expires_at)


@dataclass(frozen=True, slots=True)
class KeyedPins:
    scope: Scope
    pins: tuple[Pin, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ContractError("Pins require a scope")
        pins = freeze_sequence(self, "pins", Pin)
        if any(pin.scope != self.scope for pin in pins):
            raise ContractError("Pin scope mismatch")
        if len({pin.key for pin in pins}) != len(pins):
            raise ContractError("Pin keys must be unique; supersede old values before assembly")
        object.__setattr__(self, "pins", tuple(sorted(pins, key=lambda pin: pin.key)))

    def upsert(self, pin: Pin, *, expected_revision: int | None = None) -> "KeyedPins":
        """Immutable application-side update; transactional persistence remains C07."""
        if not isinstance(pin, Pin) or pin.scope != self.scope:
            raise ContractError("Pin scope mismatch")
        existing = next((item for item in self.pins if item.key == pin.key), None)
        if expected_revision is not None:
            integer_value("expected_revision", expected_revision, minimum=1)
        if existing is None:
            if expected_revision is not None or pin.revision != 1:
                raise ContractError("New pins must start at revision one")
        elif expected_revision != existing.revision or pin.revision != existing.revision + 1:
            raise ContractError("Pin revision conflict")
        return KeyedPins(self.scope, tuple(p for p in self.pins if p.key != pin.key) + (pin,))


@dataclass(frozen=True, slots=True)
class ContextBlock:
    kind: BlockKind
    content: str
    sources: tuple[SourceRef, ...] = ()
    prefix_stable: bool = False
    text_tokens: int | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "kind", BlockKind(self.kind))
        except (ValueError, TypeError):
            raise ContractError("Unsupported block kind") from None
        text_value("content", self.content, nonempty=False)
        freeze_sequence(self, "sources", SourceRef)
        if type(self.prefix_stable) is not bool:
            raise ContractError("prefix_stable must be a boolean")
        if self.text_tokens is not None:
            integer_value("text_tokens", self.text_tokens)

    @property
    def required(self) -> bool:
        return self.kind in (BlockKind.SYSTEM, BlockKind.PINNED, BlockKind.QUESTION)


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...] = ()

    def __post_init__(self) -> None:
        messages = freeze_sequence(self, "messages", Message)
        tools = freeze_sequence(self, "tools", ToolDefinition)
        if not messages or len({m.message_id for m in messages}) != len(messages):
            raise ContractError("Request requires messages with unique IDs")
        if len({tool.name for tool in tools}) != len(tools):
            raise ContractError("Tool definitions must have unique names")
        pending: set[str] = set()
        seen: set[str] = set()
        for message in messages:
            if message.role == Role.TOOL:
                if message.tool_call_id not in pending:
                    raise ContractError("Tool result has no pending call")
                pending.remove(message.tool_call_id)
            else:
                if pending:
                    raise ContractError("Tool results must complete before subsequent messages")
                for call in message.tool_calls:
                    if call.call_id in seen:
                        raise ContractError("Tool call IDs must be unique across a request")
                    seen.add(call.call_id)
                    pending.add(call.call_id)
        if pending:
            raise ContractError("Request contains incomplete tool calls")

    def to_wire(self) -> dict:
        result = {"messages": [message.to_wire() for message in self.messages]}
        if self.tools:
            result["tools"] = [tool.to_wire() for tool in self.tools]
        return result
