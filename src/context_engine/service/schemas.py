"""Strict version-1 wire input contracts; tenant, system policy and pin origin are server-owned."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolCallInput(WireModel):
    call_id: Identifier
    name: Identifier
    arguments_json: Annotated[str, Field(max_length=16000)]


class MessageInput(WireModel):
    id: Identifier
    role: Literal["user", "assistant", "tool"]
    content: Annotated[str, Field(max_length=64000)]
    tool_call_id: Identifier | None = None
    tool_calls: Annotated[list[ToolCallInput], Field(max_length=16)] = Field(default_factory=list)


class TurnInput(WireModel):
    id: Identifier
    operation_id: Identifier
    expected_revision: Annotated[int, Field(ge=0)]
    revision: Annotated[int, Field(ge=1)] = 1
    timestamp: Annotated[AwareDatetime, Field(strict=False)]
    expires_at: Annotated[AwareDatetime | None, Field(strict=False)] = None
    messages: Annotated[list[MessageInput], Field(min_length=1, max_length=32)]


class SourceInput(WireModel):
    turn_id: Identifier
    message_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=1)]
    message_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class PinInput(WireModel):
    value: Annotated[str, Field(min_length=1, max_length=16000)]
    expected_revision: Annotated[int, Field(ge=0)]
    revision: Annotated[int, Field(ge=1)] = 1
    effective_at: Annotated[AwareDatetime, Field(strict=False)]
    expires_at: Annotated[AwareDatetime | None, Field(strict=False)] = None
    source: SourceInput | None = None


class ContextInput(WireModel):
    question: Annotated[str, Field(min_length=1, max_length=16000)]
    expected_revision: Annotated[int, Field(ge=0)]
    input_cap: Annotated[int, Field(ge=1, le=32000)] = 900
