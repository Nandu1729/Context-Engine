"""Typed, immutable carrier snapshots and composable layer contract."""

from dataclasses import dataclass
from typing import Protocol

from .budget import BudgetPlan
from .errors import ContractError
from .models import (
    ChatRequest,
    Chunk,
    ContextBlock,
    KeyedPins,
    Message,
    Role,
    Scope,
    Turn,
    freeze_sequence,
    integer_value,
    text_value,
)
from .work import Cancellation, validate_cancellation


@dataclass(frozen=True, slots=True)
class LayerDiagnostic:
    layer: str
    reason_code: str
    changed_turn_ids: tuple[str, ...] = ()
    input_text_tokens: int = 0
    output_text_tokens: int = 0

    def __post_init__(self) -> None:
        text_value("layer", self.layer)
        text_value("reason_code", self.reason_code)
        ids = freeze_sequence(self, "changed_turn_ids", str)
        if len(set(ids)) != len(ids) or any(not value.strip() for value in ids):
            raise ContractError("Diagnostic turn IDs must be unique and nonempty")
        integer_value("input_text_tokens", self.input_text_tokens)
        integer_value("output_text_tokens", self.output_text_tokens)


@dataclass(frozen=True, slots=True)
class ContextCarrier:
    scope: Scope
    original_turns: tuple[Turn, ...]
    working_turns: tuple[Turn, ...]
    pins: KeyedPins
    question: Message
    plan: BudgetPlan | None = None
    blocks: tuple[ContextBlock, ...] = ()
    diagnostics: tuple[LayerDiagnostic, ...] = ()
    required_request: ChatRequest | None = None
    prepared_fingerprint: str | None = None
    window_planned: bool = False
    retrieved_chunks: tuple[Chunk, ...] = ()
    cancellation: Cancellation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ContractError("Carrier requires a scope")
        originals = freeze_sequence(self, "original_turns", Turn)
        working = freeze_sequence(self, "working_turns", Turn)
        blocks = freeze_sequence(self, "blocks", ContextBlock)
        diagnostics = freeze_sequence(self, "diagnostics", LayerDiagnostic)
        chunks = freeze_sequence(self, "retrieved_chunks", Chunk)
        if any(chunk.source.scope != self.scope for chunk in chunks):
            raise ContractError("Retrieved chunk scope mismatch")
        if self.required_request is not None and not isinstance(self.required_request, ChatRequest):
            raise ContractError("Carrier requires a validated mandatory request")
        if self.prepared_fingerprint is not None:
            text_value("prepared_fingerprint", self.prepared_fingerprint)
        if type(self.window_planned) is not bool:
            raise ContractError("window_planned must be boolean")
        if any(turn.scope != self.scope for turn in (*originals, *working)):
            raise ContractError("Carrier history scope mismatch")
        if not isinstance(self.pins, KeyedPins) or self.pins.scope != self.scope:
            raise ContractError("Carrier pin scope mismatch")
        if not isinstance(self.question, Message) or self.question.role != Role.USER:
            raise ContractError("Current question must be a user message")
        if self.plan is not None and not isinstance(self.plan, BudgetPlan):
            raise ContractError("Carrier requires a validated budget plan")
        if len({block.kind for block in blocks}) != len(blocks):
            raise ContractError("Carrier block kinds must be unique")
        if any(source.scope != self.scope for block in blocks for source in block.sources):
            raise ContractError("Carrier block source scope mismatch")
        original_ids = [turn.turn_id for turn in originals]
        working_ids = [turn.turn_id for turn in working]
        if len(set(original_ids)) != len(original_ids):
            raise ContractError("Original turn IDs must be unique")
        if working_ids != original_ids:
            raise ContractError("Working copies must preserve original turn order and IDs")
        original_messages = [m.message_id for turn in originals for m in turn.messages]
        if len(set(original_messages)) != len(original_messages):
            raise ContractError("History message IDs must be unique")
        if self.question.message_id in original_messages:
            raise ContractError("Current question must not already occur in history")
        for original, copy in zip(originals, working, strict=True):
            if original.revision != copy.revision or original.timestamp != copy.timestamp:
                raise ContractError("Working copies must preserve source revision and timestamp")
            if [
                (m.message_id, m.role, m.tool_call_id, m.tool_calls) for m in original.messages
            ] != [(m.message_id, m.role, m.tool_call_id, m.tool_calls) for m in copy.messages]:
                raise ContractError(
                    "Working copies must preserve message identity and tool metadata"
                )
        if self.plan is not None and not set(self.plan.window_turn_ids).issubset(original_ids):
            raise ContractError("Planned window contains unknown turns")
        if any(not set(item.changed_turn_ids).issubset(original_ids) for item in diagnostics):
            raise ContractError("Layer diagnostic references unknown turns")
        validate_cancellation(self.cancellation)


class Layer(Protocol):
    """Implementations return a new snapshot and never mutate source history."""

    def apply(self, context: ContextCarrier) -> ContextCarrier: ...
