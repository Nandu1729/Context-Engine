"""Bounded canonical codecs for persisted public contracts; never unpickle storage."""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime

from ..errors import ContextEngineError, MemoryIntegrityError
from ..layers.summarize import SummarySnapshot
from ..models import Chunk, Message, Pin, Scope, SourceRef, ToolCall, Turn, canonical_json


def plain(value):
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def encode(value):
    return canonical_json(plain(value))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def decode(raw, maximum=1_000_000):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("duplicate")
            result[k] = v
        return result

    try:
        if not isinstance(raw, str) or len(raw.encode()) > maximum:
            raise ValueError("size")
        result = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(result, dict):
            raise ValueError("object")
        return result
    except (ValueError, TypeError, RecursionError):
        raise MemoryIntegrityError("Invalid persisted memory payload") from None


def source(value):
    return SourceRef(**{**value, "scope": Scope(**value["scope"])})


def unpack(kind, raw):
    try:
        value = decode(raw)
        if kind == "turn":
            value["messages"] = tuple(
                Message(**{**m, "tool_calls": tuple(ToolCall(**c) for c in m["tool_calls"])})
                for m in value["messages"]
            )
            value["scope"] = Scope(**value["scope"])
            value["timestamp"] = datetime.fromisoformat(value["timestamp"])
            return Turn(**value)
        if kind == "pin":
            value["scope"] = Scope(**value["scope"])
            for name in ("effective_at", "expires_at"):
                if value[name] is not None:
                    value[name] = datetime.fromisoformat(value[name])
            if value["source"] is not None:
                value["source"] = source(value["source"])
            return Pin(**value)
        if kind == "summary":
            value["scope"] = Scope(**value["scope"])
            value["sources"] = tuple(source(s) for s in value["sources"])
            for name in ("created_at", "expires_at"):
                if value[name] is not None:
                    value[name] = datetime.fromisoformat(value[name])
            return SummarySnapshot(**value)
        if kind == "chunk":
            return Chunk(**{**value, "source": source(value["source"])})
        raise ValueError("kind")
    except (ContextEngineError, TypeError, ValueError, KeyError):
        raise MemoryIntegrityError("Persisted contract failed validation") from None
