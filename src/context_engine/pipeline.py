"""Public one-call context assembly with immutable outputs and final budget admission."""

import hashlib
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime

from . import __version__
from .budget import validate_request
from .config import BudgetConfig, CapConfig, RetrievalConfig
from .context import ContextCarrier, LayerDiagnostic
from .errors import ContractError, LayerStateError, RequiredContextTooLarge
from .layers import CapLayer, PinLayer, RetrieveLayer, SummaryLayer, WindowLayer
from .layers.common import ORDER, history_digest, render_request, require_prepared, window_block
from .layers.retrieve import evidence_block, represented_in_window, window_messages
from .layers.summarize import SummaryPolicy
from .models import (
    BlockKind,
    ChatRequest,
    ContextBlock,
    KeyedPins,
    Message,
    Role,
    SourceRef,
    ToolDefinition,
    Turn,
    aware_time,
    canonical_json,
    freeze_sequence,
)
from .tokens import TiktokenCounter, TokenCounter, TokenEstimate
from .work import Cancellation, raise_if_cancelled, validate_cancellation


@dataclass(frozen=True, slots=True)
class AssemblyOptions:
    """Independent optional stages; mandatory reservation and WINDOW always run."""

    cap: bool = True
    pins: bool = True
    retrieve: bool = True
    summarize: bool = True

    def __post_init__(self):
        if any(type(value) is not bool for value in asdict(self).values()):
            raise ContractError("Assembly options must be booleans")


@dataclass(frozen=True, slots=True)
class BlockUsage:
    kind: BlockKind
    content_tokens: int
    input_delta_tokens: int
    sources: tuple[SourceRef, ...]
    included: bool


@dataclass(frozen=True, slots=True)
class Drop:
    kind: BlockKind
    source_id: str | None
    reason: str = "final_request_over_budget"


@dataclass(frozen=True, slots=True)
class AssemblyDiagnostics:
    input_allowance: int
    estimate: TokenEstimate
    base_request_tokens: int
    blocks: tuple[BlockUsage, ...]
    planned_window_turn_ids: tuple[str, ...]
    kept_turn_ids: tuple[str, ...]
    omitted_turn_ids: tuple[str, ...]
    retrieved_turn_ids: tuple[str, ...]
    retrieved_chunk_ids: tuple[str, ...]
    layer_diagnostics: tuple[LayerDiagnostic, ...]
    drops: tuple[Drop, ...]
    history_fingerprint: str
    input_fingerprint: str
    config_fingerprint: str
    evaluated_at: datetime
    package_version: str = __version__

    @property
    def remaining_tokens(self) -> int:
        return self.input_allowance - self.estimate.estimated_tokens

    def to_dict(self) -> dict:
        return {
            "input_allowance": self.input_allowance,
            "estimate": self.estimate.to_dict(),
            "remaining_tokens": self.remaining_tokens,
            "base_request_tokens": self.base_request_tokens,
            "blocks": [asdict(b) for b in self.blocks],
            "planned_window_turn_ids": list(self.planned_window_turn_ids),
            "kept_turn_ids": list(self.kept_turn_ids),
            "omitted_turn_ids": list(self.omitted_turn_ids),
            "retrieved_turn_ids": list(self.retrieved_turn_ids),
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
            "summary_used": any(b.kind == BlockKind.SUMMARY and b.included for b in self.blocks),
            "layer_diagnostics": [asdict(d) for d in self.layer_diagnostics],
            "drops": [asdict(d) for d in self.drops],
            "history_fingerprint": self.history_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "evaluated_at": self.evaluated_at.isoformat(),
            "package_version": self.package_version,
        }


@dataclass(frozen=True, slots=True)
class AssembledContext:
    request: ChatRequest
    blocks: tuple[ContextBlock, ...]
    diagnostics: AssemblyDiagnostics

    def __post_init__(self) -> None:
        if not isinstance(self.request, ChatRequest) or not isinstance(
            self.diagnostics, AssemblyDiagnostics
        ):
            raise ContractError("Assembly requires validated request and diagnostics")
        freeze_sequence(self, "blocks", ContextBlock)
        if self.diagnostics.remaining_tokens < 0:
            raise ContractError("Cannot return an over-budget assembled context")

    @property
    def messages(self) -> list[dict]:
        """Fresh API-ready message dictionaries; callers cannot mutate the result."""
        return self.request.to_wire()["messages"]

    def to_dict(self, *, include_content: bool = False) -> dict:
        if type(include_content) is not bool:
            raise ContractError("include_content must be an explicit boolean")
        result = {"diagnostics": self.diagnostics.to_dict(), "content_included": include_content}
        if include_content:
            result["request"] = self.request.to_wire()
        return result


def _replace_block(
    blocks: tuple[ContextBlock, ...], replacement: ContextBlock
) -> tuple[ContextBlock, ...]:
    return tuple(
        sorted(
            tuple(b for b in blocks if b.kind != replacement.kind) + (replacement,),
            key=lambda b: ORDER.index(b.kind),
        )
    )


def _finalize(
    context: ContextCarrier,
    counter: TokenCounter,
    budget: BudgetConfig,
    *,
    recover_capped_window: bool = False,
):
    """Bounded, deterministic optional removal; required payload stays byte-identical."""
    require_prepared(context, counter)
    if context.plan.input_allowance != budget.input_allowance or not context.window_planned:
        raise LayerStateError("Finalization requires a matching completed selection plan")
    blocks = context.blocks
    ids = context.plan.window_turn_ids
    chunks = context.retrieved_chunks
    turns = {turn.turn_id: turn for turn in context.original_turns}
    visible = window_messages(context)
    for chunk in chunks:
        if chunk.source.turn_id not in turns:
            raise LayerStateError("Retrieved source conflicts with the history/window plan")
        chunk.validate_source(turns[chunk.source.turn_id])
        if chunk.source.turn_id in ids and (
            not recover_capped_window or represented_in_window(chunk, visible)
        ):
            raise LayerStateError("Retrieved source duplicates or violates the WINDOW policy")
    # Content/provenance must describe the same selected chunks and recent turns.
    for kind, expected in (
        (BlockKind.RETRIEVED, evidence_block(chunks, counter)),
        (BlockKind.WINDOW, window_block(context, ids, counter)),
    ):
        actual = next((b for b in blocks if b.kind == kind), None)
        if (
            actual is None
            or actual.content != expected.content
            or actual.sources != expected.sources
        ):
            raise LayerStateError("Selected content and provenance do not agree")
    drops: list[Drop] = []
    # One initial count, one summary removal, one per window turn, one per chunk.
    for _ in range(2 + len(ids) + len(chunks)):
        raise_if_cancelled(context.cancellation)
        request = render_request(blocks, context.question, context.required_request.tools)
        estimate = counter.count_request(request)
        if estimate.estimated_tokens <= budget.input_allowance:
            validated = validate_request(request=request, config=budget, counter=counter)
            if validated != estimate:
                raise LayerStateError("Token counter changed for the identical final request")
            sources = tuple(
                SourceRef(
                    t.scope, t.turn_id, m.message_id, t.revision, 0, len(m.content), m.content_hash
                )
                for t in context.original_turns
                if t.turn_id in ids
                for m in t.messages
                if m.content
            )
            final_window = replace(window_block(context, ids, counter), sources=sources)
            blocks = _replace_block(blocks, final_window)
            blocks = _replace_block(
                blocks,
                ContextBlock(
                    BlockKind.QUESTION,
                    context.question.content,
                    text_tokens=counter.count_text(context.question.content),
                ),
            )
            return (
                request,
                tuple(sorted(blocks, key=lambda b: ORDER.index(b.kind))),
                validated,
                ids,
                chunks,
                tuple(drops),
            )
        summary = next((b for b in blocks if b.kind == BlockKind.SUMMARY), None)
        if summary is not None and summary.content:
            blocks = _replace_block(blocks, ContextBlock(BlockKind.SUMMARY, "", text_tokens=0))
            drops.append(Drop(BlockKind.SUMMARY, None))
        elif ids:
            dropped, ids = ids[0], ids[1:]
            blocks = _replace_block(blocks, window_block(context, ids, counter))
            drops.append(Drop(BlockKind.WINDOW, dropped))
        elif chunks:
            dropped, chunks = chunks[-1], chunks[:-1]
            blocks = _replace_block(blocks, evidence_block(chunks, counter))
            drops.append(Drop(BlockKind.RETRIEVED, dropped.chunk_id))
        else:
            raise RequiredContextTooLarge(
                "Required context exceeds the final input allowance",
                required_tokens=estimate.estimated_tokens,
                input_allowance=budget.input_allowance,
                overflow_tokens=estimate.estimated_tokens - budget.input_allowance,
            )
    raise LayerStateError("Finalization exceeded its bounded removal steps")


def _block_accounting(blocks, question, tools, counter, estimate):
    empty_question = replace(question, content="")
    running: tuple[ContextBlock, ...] = ()
    previous = counter.count_request(render_request((), empty_question, tools)).estimated_tokens
    base = previous
    result = []
    by_kind = {b.kind: b for b in blocks}
    for kind in ORDER:
        item = by_kind.get(kind, ContextBlock(kind, "", text_tokens=0))
        current_question = question if kind == BlockKind.QUESTION else empty_question
        if kind != BlockKind.QUESTION:
            running += (item,)
        current = counter.count_request(
            render_request(running, current_question, tools)
        ).estimated_tokens
        content = question.content if kind == BlockKind.QUESTION else item.content
        result.append(
            BlockUsage(
                kind,
                counter.count_text(content),
                current - previous,
                item.sources,
                kind == BlockKind.QUESTION or bool(content),
            )
        )
        previous = current
    if previous != estimate.estimated_tokens:
        raise LayerStateError("Per-block accounting disagrees with the final request estimate")
    return base, tuple(result)


def assemble_context(
    history: tuple[Turn, ...] | list[Turn],
    question: Message | str,
    pinned_facts: KeyedPins,
    budget: BudgetConfig,
    *,
    system: str,
    at: datetime | None = None,
    token_counter: TokenCounter | None = None,
    cap_config: CapConfig | None = None,
    retrieval_config: RetrievalConfig | None = None,
    summary_policy: SummaryPolicy | None = None,
    tools: tuple[ToolDefinition, ...] | list[ToolDefinition] = (),
    options: AssemblyOptions | None = None,
    chunk_index=None,
    cancellation: Cancellation | None = None,
) -> AssembledContext:
    """Assemble authorized history into an estimated-token-safe request, or raise a typed error.

    Scope is derived from KeyedPins, including for empty history. Authorization is
    the caller's responsibility. Supply `at` for reproducible pin/summary expiry.
    Every call, including calls after tools, should use this boundary.
    """
    validate_cancellation(cancellation)
    raise_if_cancelled(cancellation)
    if not isinstance(pinned_facts, KeyedPins) or not isinstance(budget, BudgetConfig):
        raise ContractError("Expected KeyedPins and BudgetConfig")
    options = AssemblyOptions() if options is None else options
    if not isinstance(options, AssemblyOptions):
        raise ContractError("Expected validated assembly options")
    if not options.pins:
        pinned_facts = KeyedPins(pinned_facts.scope)
    budget = replace(
        budget,
        retrieval_reserve=budget.retrieval_reserve if options.retrieve else 0,
        summary_reserve=budget.summary_reserve if options.summarize else 0,
    )
    if not isinstance(history, (list, tuple)) or any(not isinstance(t, Turn) for t in history):
        raise ContractError("History must be a sequence of validated turns")
    if not isinstance(tools, (list, tuple)) or any(
        not isinstance(t, ToolDefinition) for t in tools
    ):
        raise ContractError("Tools must be a sequence of validated definitions")
    at = datetime.now(UTC) if at is None else at
    aware_time("at", at)
    cap_config = CapConfig() if cap_config is None else cap_config
    retrieval_config = RetrievalConfig() if retrieval_config is None else retrieval_config
    if not isinstance(cap_config, CapConfig) or not isinstance(retrieval_config, RetrievalConfig):
        raise ContractError("Expected validated layer configuration")
    if isinstance(question, str):
        used = {m.message_id for t in history for m in t.messages}
        identifier = "current-question"
        while identifier in used:
            identifier += ":next"
        question = Message(identifier, Role.USER, question)
    context = ContextCarrier(
        pinned_facts.scope, history, history, pinned_facts, question, cancellation=cancellation
    )
    counter = TiktokenCounter() if token_counter is None else token_counter
    if options.cap:
        context = CapLayer(counter, cap_config).apply(context)
    else:
        context = replace(context, diagnostics=(LayerDiagnostic("CAP", "layer_disabled"),))
    for layer in (
        PinLayer(counter, budget, system, at, tuple(tools)),
        RetrieveLayer(counter, retrieval_config, chunk_index),
        WindowLayer(counter),
        SummaryLayer(counter, summary_policy if options.summarize else None, at),
    ):
        raise_if_cancelled(cancellation)
        context = layer.apply(context)
    raise_if_cancelled(cancellation)
    request, blocks, estimate, kept, chunks, drops = _finalize(
        context, counter, budget, recover_capped_window=retrieval_config.recover_capped_window
    )
    base, accounting = _block_accounting(blocks, question, tuple(tools), counter, estimate)
    config_data = {
        "budget": asdict(budget),
        "cap": asdict(cap_config),
        "retrieval": asdict(retrieval_config),
        "options": asdict(options),
        "counting": {
            "tokenizer": estimate.tokenizer_name,
            "version": estimate.tokenizer_version,
            "serializer": estimate.serializer_name,
            "factor": estimate.calibration_factor,
            "overhead": estimate.adapter_overhead_tokens,
        },
    }
    diagnostics = AssemblyDiagnostics(
        budget.input_allowance,
        estimate,
        base,
        accounting,
        context.plan.window_turn_ids,
        kept,
        tuple(t.turn_id for t in context.original_turns if t.turn_id not in kept),
        tuple(dict.fromkeys(c.source.turn_id for c in chunks)),
        tuple(c.chunk_id for c in chunks),
        context.diagnostics,
        drops,
        history_digest(context.original_turns),
        context.prepared_fingerprint,
        hashlib.sha256(canonical_json(config_data).encode()).hexdigest(),
        at,
    )
    raise_if_cancelled(cancellation)
    return AssembledContext(request, blocks, diagnostics)
