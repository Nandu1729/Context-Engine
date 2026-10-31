"""Shared rendering/accounting primitives used by layers and the public pipeline."""

import hashlib
from collections import OrderedDict
from dataclasses import asdict, replace
from functools import lru_cache

from ..context import ContextCarrier, LayerDiagnostic
from ..errors import LayerStateError
from ..models import (
    BlockKind,
    ChatRequest,
    ContextBlock,
    Message,
    Role,
    ToolDefinition,
    Turn,
    canonical_json,
)
from ..tokens import CanonicalChatSerializer, TiktokenCounter, TokenCounter, estimated_tokens
from ..work import raise_if_cancelled

ORDER = tuple(BlockKind)
OPTIONAL = (BlockKind.SUMMARY, BlockKind.WINDOW, BlockKind.RETRIEVED)


def history_digest(turns: tuple[Turn, ...]) -> str:
    # Turns are immutable values, so equal histories share one cached digest.
    return _history_digest(tuple(turns))


@lru_cache(maxsize=256)
def _history_digest(turns: tuple[Turn, ...]) -> str:
    values = [
        (asdict(t.scope), t.turn_id, t.revision, t.timestamp.isoformat(), t.content_hash)
        for t in turns
    ]
    return hashlib.sha256(canonical_json(values).encode()).hexdigest()


def input_digest(context: ContextCarrier) -> str:
    pins = []
    for pin in context.pins.pins:
        value = asdict(pin)
        value["effective_at"] = pin.effective_at.isoformat()
        value["expires_at"] = pin.expires_at.isoformat() if pin.expires_at else None
        pins.append(value)
    values = {
        "scope": asdict(context.scope),
        "original": history_digest(context.original_turns),
        "working": history_digest(context.working_turns),
        "pins": pins,
        "question": context.question.to_wire(),
        "question_id": context.question.message_id,
    }
    return hashlib.sha256(canonical_json(values).encode()).hexdigest()


def render_request(
    blocks: tuple[ContextBlock, ...], question: Message, tools: tuple[ToolDefinition, ...] = ()
) -> ChatRequest:
    """Quote all historical/evidence blocks as user data, including historical tool calls."""
    by_kind = {block.kind: block for block in blocks}
    messages = []
    for kind in ORDER:
        if kind == BlockKind.QUESTION:
            messages.append(Message("ctx:question", Role.USER, question.content))
            continue
        block = by_kind.get(kind)
        if block is None or not block.content:
            continue
        role = Role.SYSTEM if kind == BlockKind.SYSTEM else Role.USER
        content = (
            block.content
            if kind == BlockKind.SYSTEM
            else f"[{kind.value.upper()} DATA]\n{block.content}"
        )
        messages.append(Message(f"ctx:{kind.value}", role, content))
    return ChatRequest(tuple(messages), tools)


def required_blocks(context: ContextCarrier) -> tuple[ContextBlock, ...]:
    return tuple(b for b in context.blocks if b.kind not in OPTIONAL)


def require_prepared(context: ContextCarrier, counter: TokenCounter) -> None:
    if context.plan is None or context.required_request is None:
        raise LayerStateError("PIN must reserve mandatory context first")
    if context.prepared_fingerprint != input_digest(context):
        raise LayerStateError("History, question or pins changed after budget planning; rerun PIN")
    request = render_request(
        required_blocks(context), context.question, context.required_request.tools
    )
    if (
        request != context.required_request
        or counter.count_request(request) != context.plan.required_estimate
    ):
        raise LayerStateError("Mandatory blocks or counting profile changed after planning")


def set_block(
    context: ContextCarrier, block: ContextBlock, diagnostic: LayerDiagnostic
) -> ContextCarrier:
    blocks = tuple(b for b in context.blocks if b.kind != block.kind) + (block,)
    return replace(
        context,
        blocks=tuple(sorted(blocks, key=lambda b: ORDER.index(b.kind))),
        diagnostics=context.diagnostics + (diagnostic,),
    )


@lru_cache(maxsize=4096)
def _turn_json(turn) -> str:
    return canonical_json({"turn": turn.turn_id, "messages": [m.to_wire() for m in turn.messages]})


def window_block(
    context: ContextCarrier, ids: tuple[str, ...], counter: TokenCounter, *, count: bool = True
) -> ContextBlock:
    """`count=False` skips the block's own token count (planning-only candidates)."""
    selected = [t for t in context.working_turns if t.turn_id in ids]
    # Identical to canonical_json of the list: compact separators, per-item sorted keys.
    content = "[" + ",".join(_turn_json(t) for t in selected) + "]" if selected else ""
    return ContextBlock(
        BlockKind.WINDOW, content, text_tokens=counter.count_text(content) if count else None
    )


def incremental_cost(context: ContextCarrier, block: ContextBlock, counter: TokenCounter) -> int:
    request = render_request(
        required_blocks(context) + (block,), context.question, context.required_request.tools
    )
    return max(
        0,
        estimated_tokens(counter, request) - context.plan.required_estimate.estimated_tokens,
    )


def fits_block(
    context: ContextCarrier, block: ContextBlock, allowance: int, counter: TokenCounter
) -> bool:
    if incremental_cost(context, block, counter) > allowance:
        return False
    blocks = tuple(b for b in context.blocks if b.kind != block.kind) + (block,)
    # RETRIEVE runs first but must leave the exact planned WINDOW viable.
    if context.window_planned and block.kind != BlockKind.WINDOW:
        blocks = tuple(b for b in blocks if b.kind != BlockKind.WINDOW) + (
            window_block(context, context.plan.window_turn_ids, counter, count=False),
        )
    request = render_request(blocks, context.question, context.required_request.tools)
    return estimated_tokens(counter, request) <= context.plan.input_allowance


_WINDOW_MEMO: OrderedDict = OrderedDict()
_WINDOW_MEMO_SIZE = 64


def _window_key(context: ContextCarrier, counter: TokenCounter):
    """Every input the WINDOW scan reads; None (no memo) for custom counters/serializers."""
    if (
        type(counter) is not TiktokenCounter
        or type(counter.serializer) is not CanonicalChatSerializer
    ):
        return None
    return (
        counter.config,
        tuple(context.working_turns),
        required_blocks(context),
        context.question,
        context.required_request.tools,
        context.plan.window_tokens,
        context.plan.required_estimate.estimated_tokens,
    )


def _scan_window(context: ContextCarrier, counter: TokenCounter) -> tuple[str, ...]:
    selected: tuple[str, ...] = ()
    for turn in reversed(context.working_turns):
        raise_if_cancelled(context.cancellation)
        candidate = (turn.turn_id,) + selected
        if (
            incremental_cost(
                context, window_block(context, candidate, counter, count=False), counter
            )
            > context.plan.window_tokens
        ):
            break
        selected = candidate
    return selected


def plan_window(context: ContextCarrier, counter: TokenCounter) -> ContextCarrier:
    require_prepared(context, counter)
    # RETRIEVE, WINDOW and SUMMARIZE each re-plan the same inputs; the scan is pure.
    key = _window_key(context, counter)
    if key is None or key not in _WINDOW_MEMO:
        selected = _scan_window(context, counter)
        if key is not None:
            _WINDOW_MEMO[key] = selected
            if len(_WINDOW_MEMO) > _WINDOW_MEMO_SIZE:
                _WINDOW_MEMO.popitem(last=False)
    else:
        raise_if_cancelled(context.cancellation)
        _WINDOW_MEMO.move_to_end(key)
        selected = _WINDOW_MEMO[key]
    if context.window_planned:
        if selected != context.plan.window_turn_ids:
            raise LayerStateError("Stored WINDOW membership differs from shared planner")
        return context
    return replace(
        context, plan=replace(context.plan, window_turn_ids=selected), window_planned=True
    )
