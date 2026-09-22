"""Synthetic C02 layer walkthrough. No provider or answer generation."""

from datetime import UTC, datetime

from .budget import validate_request
from .config import BudgetConfig, CapConfig, RetrievalConfig
from .context import ContextCarrier
from .layers import CapLayer, PinLayer, RetrieveLayer, SummaryLayer, SummarySnapshot, WindowLayer
from .layers.common import render_request
from .layers.summarize import FrozenSummaryPolicy
from .models import BlockKind, KeyedPins, Message, Pin, Role, Scope, Turn
from .tokens import TokenCounter


def demo_context():
    at = datetime(2026, 9, 7, tzinfo=UTC)
    scope = Scope("demo", "incident")
    old = Turn(
        "t1",
        scope,
        (
            Message(
                "m1",
                Role.TOOL,
                "BEGIN "
                + "routine telemetry. " * 60
                + "The partition carrying the blame was shard-19. "
                + "routine telemetry. " * 60
                + " END",
                tool_call_id="historical-call",
            ),
        ),
        timestamp=at,
    )
    recent = tuple(
        Turn(
            f"t{i}",
            scope,
            (
                Message(
                    f"m{i}", Role.USER, f"Recent update {i}: " + "routine checks continue. " * 40
                ),
            ),
            timestamp=at,
        )
        for i in range(2, 13)
    )
    turns = (old,) + recent
    pins = KeyedPins(
        scope, (Pin(scope, "environment", "production", "application", effective_at=at),)
    )
    context = ContextCarrier(
        scope,
        turns,
        turns,
        pins,
        Message("question", Role.USER, "Which partition carried the blame?"),
    )
    budget = BudgetConfig(input_cap=900, retrieval_reserve=280, summary_reserve=80)
    return context, budget, at


def layer_demo(counter: TokenCounter) -> dict:
    context, budget, at = demo_context()
    turns = context.original_turns
    old = turns[0]
    scope = context.scope
    capped = CapLayer(counter, CapConfig()).apply(context)
    prepared = PinLayer(counter, budget, "Use the supplied evidence to answer.", at).apply(capped)
    retrieved = RetrieveLayer(counter, RetrievalConfig()).apply(prepared)
    windowed = WindowLayer(counter).apply(retrieved)
    omitted = tuple(t for t in turns if t.turn_id not in windowed.plan.window_turn_ids)
    snapshot = SummarySnapshot.from_history(
        scope=scope,
        content="Earlier discussion concerned an incident and routine telemetry.",
        history=omitted,
        policy_version="demo-v1",
        created_at=at,
    )
    completed = SummaryLayer(counter, FrozenSummaryPolicy(snapshot), at).apply(windowed)
    request = render_request(completed.blocks, completed.question, completed.required_request.tools)
    estimate = validate_request(request=request, config=budget, counter=counter)
    evidence = next(b for b in completed.blocks if b.kind == BlockKind.RETRIEVED)
    return {
        "inference_calls": 0,
        "input_allowance": budget.input_allowance,
        "original_message_tokens": counter.count_text(old.messages[0].content),
        "capped_message_tokens": counter.count_text(capped.working_turns[0].messages[0].content),
        "original_preserved": completed.original_turns == context.original_turns,
        "capped_middle_fact_present": "shard-19" in capped.working_turns[0].messages[0].content,
        "retrieved_middle_fact_present": "shard-19" in evidence.content,
        "retrieved_turn_ids": sorted({c.source.turn_id for c in completed.retrieved_chunks}),
        "window_turn_ids": list(completed.plan.window_turn_ids),
        "summary_used": any(b.kind == BlockKind.SUMMARY and b.content for b in completed.blocks),
        "estimated_request_tokens": estimate.estimated_tokens,
        "layer_order": [d.layer for d in completed.diagnostics],
        "retrieved_evidence": evidence.content,
    }
