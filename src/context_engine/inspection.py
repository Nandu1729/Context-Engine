"""Bounded JSON input and content-opt-in offline inspection. No provider calls."""

import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from .config import (
    MAX_INSPECTION_BYTES,
    MAX_INSPECTION_TURNS,
    BudgetConfig,
    CapConfig,
    RetrievalConfig,
    Settings,
    TokenizerConfig,
)
from .errors import InspectionError
from .layers.summarize import FrozenSummaryPolicy, SummarySnapshot
from .models import KeyedPins, Message, Pin, Scope, ToolCall, ToolDefinition, Turn, canonical_json
from .pipeline import assemble_context
from .tokens import TiktokenCounter


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise InspectionError("Input object contains missing or unsupported fields")
    return value


def _items(value):
    if not isinstance(value, list):
        raise InspectionError("Expected a JSON array")
    return value


def _time(value):
    if not isinstance(value, str):
        raise InspectionError("Expected an ISO timestamp with timezone")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise InspectionError("Invalid ISO timestamp") from None


def _config(cls, value, default):
    _object(value, cls.__dataclass_fields__)
    return replace(default, **value)


@dataclass(frozen=True)
class InspectionJob:
    arguments: dict
    tokenizer: TokenizerConfig
    synthetic: bool = False

    def run(self, *, input_cap: int | None = None):
        arguments = dict(self.arguments)
        if input_cap is not None:
            arguments["budget"] = replace(arguments["budget"], input_cap=input_cap)
        return assemble_context(**arguments, token_counter=TiktokenCounter(self.tokenizer))


def parse_job(payload: dict, settings: Settings) -> InspectionJob:
    _object(
        payload,
        {
            "schema_version",
            "scope",
            "system",
            "question",
            "at",
            "history",
            "pins",
            "tools",
            "budget",
            "cap",
            "retrieval",
            "tokenizer",
            "summary",
        },
        {"schema_version", "scope", "system", "question", "at", "history"},
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise InspectionError("Unsupported inspection schema version")
    scope = Scope(
        **_object(payload["scope"], {"tenant_id", "session_id"}, {"tenant_id", "session_id"})
    )
    at = _time(payload["at"])
    history = []
    raw_history = _items(payload["history"])
    if len(raw_history) > MAX_INSPECTION_TURNS:
        raise InspectionError(
            "Inspection history exceeds the turn limit", maximum=MAX_INSPECTION_TURNS
        )
    for item in raw_history:
        item = _object(
            item, {"turn_id", "revision", "timestamp", "messages"}, {"turn_id", "messages"}
        )
        messages = []
        for message in _items(item["messages"]):
            message = dict(
                _object(
                    message,
                    {"message_id", "role", "content", "tool_call_id", "tool_calls"},
                    {"message_id", "role", "content"},
                )
            )
            calls = []
            for call in _items(message.pop("tool_calls", [])):
                calls.append(
                    ToolCall(
                        **_object(
                            call,
                            {"call_id", "name", "arguments_json"},
                            {"call_id", "name", "arguments_json"},
                        )
                    )
                )
            messages.append(Message(**message, tool_calls=tuple(calls)))
        history.append(
            Turn(
                item["turn_id"],
                scope,
                tuple(messages),
                item.get("revision", 1),
                _time(item["timestamp"]) if "timestamp" in item else at,
            )
        )
    pins = []
    for pin in _items(payload.get("pins", [])):
        pin = dict(
            _object(
                pin,
                {"key", "value", "origin", "revision", "effective_at", "expires_at"},
                {"key", "value", "origin"},
            )
        )
        effective = _time(pin.pop("effective_at")) if "effective_at" in pin else at
        expires = _time(pin.pop("expires_at")) if pin.get("expires_at") is not None else None
        pin.pop("expires_at", None)
        pins.append(Pin(scope=scope, **pin, effective_at=effective, expires_at=expires))
    tools = []
    for tool in _items(payload.get("tools", [])):
        tool = _object(tool, {"name", "description", "parameters"}, {"name", "parameters"})
        tools.append(
            ToolDefinition(
                tool["name"], tool.get("description", ""), canonical_json(tool["parameters"])
            )
        )
    policy = None
    if payload.get("summary") is not None:
        raw = _object(
            payload["summary"],
            {"content", "covered_turn_ids", "policy_version", "created_at", "expires_at"},
            {"content", "covered_turn_ids", "policy_version", "created_at"},
        )
        ids = _items(raw["covered_turn_ids"])
        if any(not isinstance(identifier, str) for identifier in ids) or len(set(ids)) != len(ids):
            raise InspectionError("Summary turn IDs must be unique strings")
        turns = {t.turn_id: t for t in history}
        if set(ids) - turns.keys():
            raise InspectionError("Summary refers to missing history")
        policy = FrozenSummaryPolicy(
            SummarySnapshot.from_history(
                scope=scope,
                content=raw["content"],
                history=tuple(turns[i] for i in ids),
                policy_version=raw["policy_version"],
                created_at=_time(raw["created_at"]),
                expires_at=_time(raw["expires_at"]) if raw.get("expires_at") is not None else None,
            )
        )
    question = payload["question"]
    if not isinstance(question, str):
        raise InspectionError("Question must be a string")
    return InspectionJob(
        {
            "history": tuple(history),
            "question": question,
            "pinned_facts": KeyedPins(scope, tuple(pins)),
            "system": payload["system"],
            "at": at,
            "tools": tuple(tools),
            "summary_policy": policy,
            "budget": _config(BudgetConfig, payload.get("budget", {}), settings.budget),
            "cap_config": _config(CapConfig, payload.get("cap", {}), settings.cap),
            "retrieval_config": _config(
                RetrievalConfig, payload.get("retrieval", {}), settings.retrieval
            ),
        },
        _config(TokenizerConfig, payload.get("tokenizer", {}), settings.tokenizer),
    )


def load_job(path: Path, settings: Settings) -> InspectionJob:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InspectionError("Duplicate JSON keys are not allowed")
            result[key] = value
        return result

    def reject_constant(_):
        raise InspectionError("JSON numeric constants must be finite")

    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_INSPECTION_BYTES + 1)
        if len(raw) > MAX_INSPECTION_BYTES:
            raise InspectionError(
                "Inspection file exceeds the byte limit", maximum=MAX_INSPECTION_BYTES
            )
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant
        )
    except OSError:
        raise InspectionError("Cannot read inspection input") from None
    except (UnicodeError, ValueError, RecursionError):
        raise InspectionError("Inspection input must be valid UTF-8 JSON") from None
    try:
        return parse_job(payload, settings)
    except (TypeError, KeyError, OverflowError, RecursionError):
        raise InspectionError("Invalid inspection input structure") from None


def demo_job(settings: Settings) -> InspectionJob:
    from .demo import demo_context

    class DemoPolicy:
        def get_summary(self, history, scope, at):
            return SummarySnapshot.from_history(
                scope=scope,
                content="Earlier discussion concerned an incident and routine telemetry.",
                history=history,
                policy_version="synthetic-demo-v1",
                created_at=at,
            )

    context, budget, at = demo_context()
    return InspectionJob(
        {
            "history": context.original_turns,
            "question": context.question,
            "pinned_facts": context.pins,
            "budget": budget,
            "at": at,
            "system": "Use the supplied evidence to answer.",
            "summary_policy": DemoPolicy(),
        },
        settings.tokenizer,
        synthetic=True,
    )


def save_inspection(path: Path, result: dict) -> None:
    """Explicit export never overwrites an existing file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError:
        raise InspectionError("Output already exists; choose a new path") from None
    except (OSError, ValueError):
        raise InspectionError("Cannot write inspection output") from None
