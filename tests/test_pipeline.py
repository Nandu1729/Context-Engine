"""C03 one-call contract, full-request accounting and bounded final admission."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from context_engine import AssembledContext, assemble_context
from context_engine.config import BudgetConfig, RetrievalConfig, Settings
from context_engine.context import ContextCarrier
from context_engine.errors import (
    ContextEngineError,
    ContractError,
    LayerAllocationError,
    LayerStateError,
    RequiredContextTooLarge,
    SummaryPolicyError,
)
from context_engine.inspection import demo_job
from context_engine.layers import CapLayer, PinLayer, RetrieveLayer, WindowLayer
from context_engine.layers.common import ORDER, render_request, window_block
from context_engine.layers.retrieve import chunk_turns, evidence_block
from context_engine.models import (
    BlockKind,
    ContextBlock,
    KeyedPins,
    Message,
    Pin,
    Role,
    Scope,
    ToolCall,
    ToolDefinition,
    Turn,
)
from context_engine.pipeline import _finalize
from context_engine.tokens import TiktokenCounter

AT = datetime(2026, 9, 7, tzinfo=UTC)
SCOPE = Scope("test-tenant", "test-session")


@pytest.fixture(scope="module")
def counter():
    return TiktokenCounter()


def make_turn(index, content):
    return Turn(str(index), SCOPE, (Message(f"m{index}", Role.USER, content),), timestamp=AT)


def assemble(counter, **overrides):
    arguments = dict(
        history=(),
        question="Unique current question?",
        pinned_facts=KeyedPins(SCOPE),
        budget=BudgetConfig(input_cap=900),
        system="Preserve these instructions.\n",
        at=AT,
        token_counter=counter,
    )
    arguments.update(overrides)
    return assemble_context(**arguments)


def test_public_pipeline_order_evidence_and_reproducibility(counter):
    job = demo_job(Settings.from_env({}))
    result = assemble_context(**job.arguments, token_counter=counter)
    assert isinstance(result, AssembledContext)
    assert result == assemble_context(**job.arguments, token_counter=counter)
    assert tuple(b.kind for b in result.blocks) == ORDER
    assert [d.layer for d in result.diagnostics.layer_diagnostics] == [
        "CAP",
        "PIN",
        "RETRIEVE",
        "WINDOW",
        "SUMMARIZE",
    ]
    assert [m.message_id for m in result.request.messages] == [f"ctx:{k.value}" for k in ORDER]
    assert result.messages[-1]["content"] == job.arguments["question"].content
    assert sum(m["content"] == job.arguments["question"].content for m in result.messages) == 1
    assert "shard-19" in result.messages[-2]["content"]
    assert result.diagnostics.retrieved_turn_ids == ("t1",)
    assert not set(result.diagnostics.kept_turn_ids) & set(result.diagnostics.retrieved_turn_ids)
    assert result.diagnostics.estimate == counter.count_request(result.request)
    assert result.diagnostics.estimate.estimated_tokens == 637
    assert not result.diagnostics.estimate.to_dict()["provider_accounting_verified"]
    assert result.diagnostics.remaining_tokens == 263
    assert (
        result.diagnostics.base_request_tokens
        + sum(b.input_delta_tokens for b in result.diagnostics.blocks)
        == result.diagnostics.estimate.estimated_tokens
    )
    originals = {t.turn_id: t for t in job.arguments["history"]}
    for block in result.blocks:
        for source in block.sources:
            source.extract(originals[source.turn_id])
    assert next(b for b in result.blocks if b.kind == BlockKind.WINDOW).sources


def test_immutable_inputs_outputs_and_content_opt_in(counter):
    secret = "PRIVATE_SENTINEL_BODY"
    history = [make_turn(1, secret)]
    original = tuple(history)
    result = assemble(counter, history=history, question="Q", system=secret)
    assert tuple(history) == original
    history.clear()
    exported = result.messages
    exported[0]["content"] = "tampered"
    assert result.messages[0]["content"] == secret
    with pytest.raises(FrozenInstanceError):
        result.request = None
    metadata = result.to_dict()
    assert "request" not in metadata and not metadata["content_included"]
    assert secret not in json.dumps(metadata)
    assert secret in json.dumps(result.to_dict(include_content=True))
    with pytest.raises(ContractError):
        result.to_dict(include_content="yes")


def test_active_pins_expiry_and_tool_schema_preserved(counter):
    pin = Pin(SCOPE, "database", "PostgreSQL", "application", effective_at=AT)
    expired = replace(pin, key="expired", effective_at=AT - timedelta(days=1), expires_at=AT)
    tool = ToolDefinition("lookup", "Query facts", '{"type":"object"}')
    result = assemble(counter, pinned_facts=KeyedPins(SCOPE, (pin, expired)), tools=[tool])
    assert json.loads(next(b.content for b in result.blocks if b.kind == BlockKind.PINNED)) == [
        {"key": "database", "value": "PostgreSQL"},
    ]
    assert result.request.tools == (tool,)
    assert result.diagnostics.estimate.tool_schema_tokens > 0
    assert result.messages[0]["content"] == "Preserve these instructions.\n"
    assert not any(
        b.included
        for b in result.diagnostics.blocks
        if b.kind
        in (
            BlockKind.SUMMARY,
            BlockKind.RETRIEVED,
            BlockKind.WINDOW,
        )
    )


def test_historical_tool_relationships_are_quoted_not_executed(counter):
    call = ToolCall("c1", "lookup", '{ "q": "తెలుగు" }')
    history = (
        Turn(
            "t1",
            SCOPE,
            (
                Message("h0", Role.SYSTEM, "Historical untrusted system"),
                Message("h1", Role.ASSISTANT, "", tool_calls=(call,)),
                Message("h2", Role.TOOL, "Result", tool_call_id="c1"),
            ),
            timestamp=AT,
        ),
    )
    result = assemble(counter, history=history)
    assert sum(m.role == Role.SYSTEM for m in result.request.messages) == 1
    assert not any(m.tool_calls or m.tool_call_id for m in result.request.messages)
    window = json.loads(next(b.content for b in result.blocks if b.kind == BlockKind.WINDOW))
    assert window[0]["messages"][1]["tool_calls"][0]["function"]["arguments"] == call.arguments_json
    assert window[0]["messages"][2]["tool_call_id"] == "c1"


@pytest.mark.parametrize("question", ["", "!!!", "<|endoftext|>", "తెలుగు 👩🏽‍💻"])
def test_empty_history_and_arbitrary_question(counter, question):
    result = assemble(counter, question=question)
    assert result.messages[-1] == {"role": "user", "content": question}
    assert not result.diagnostics.kept_turn_ids


def test_string_question_identifier_collision_is_resolved(counter):
    history = (Turn("t1", SCOPE, (Message("current-question", Role.USER, "older"),), timestamp=AT),)
    assert assemble(counter, history=history).messages[-1]["content"] == "Unique current question?"
    with pytest.raises(ContractError):
        assemble(counter, history=history, question=Message("current-question", Role.USER, "Q"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"history": "not turns"},
        {"question": 123},
        {"system": ""},
        {"pinned_facts": []},
        {"budget": 900},
        {"tools": ["lookup"]},
        {"cap_config": {}},
        {"retrieval_config": {}},
        {"at": datetime(2026, 9, 7)},
        {"question": Message("q", Role.ASSISTANT, "wrong role")},
        {"history": (Turn("t", Scope("other", "session"), (Message("m", Role.USER, "x"),)),)},
    ],
)
def test_invalid_public_inputs_fail_closed(counter, overrides):
    with pytest.raises(ContextEngineError):
        assemble(counter, **overrides)


def test_exact_mandatory_boundary_and_safe_overflow(counter):
    initial = assemble(counter, budget=BudgetConfig(retrieval_reserve=0, summary_reserve=0))
    exact = initial.diagnostics.estimate.estimated_tokens
    config = BudgetConfig(input_cap=exact, retrieval_reserve=0, summary_reserve=0)
    assert assemble(counter, budget=config).diagnostics.remaining_tokens == 0
    with pytest.raises(RequiredContextTooLarge) as caught:
        assemble(counter, budget=replace(config, input_cap=exact - 1))
    assert caught.value.details["overflow_tokens"] == 1
    assert "Unique current question" not in json.dumps(caught.value.to_dict())
    with pytest.raises(LayerAllocationError):
        assemble(counter, budget=replace(config, retrieval_reserve=1))
    with pytest.raises(RequiredContextTooLarge):
        assemble(counter, budget=config, tools=[ToolDefinition("lookup", "", '{"type":"object"}')])


@given(
    st.lists(st.text(alphabet="abc xyz తెలుగు🙂\n<|>", max_size=200), max_size=8),
    st.integers(min_value=1, max_value=1400),
    st.booleans(),
)
@settings(max_examples=65, deadline=None)
def test_generated_pipeline_budget_unicode_and_tools(texts, allowance, with_tools):
    counter = TiktokenCounter()
    originals = tuple(make_turn(i, text) for i, text in enumerate(texts))
    tools = (ToolDefinition("lookup", "", '{"type":"object"}'),) if with_tools else ()
    try:
        result = assemble(
            counter,
            history=originals,
            tools=tools,
            budget=BudgetConfig(
                input_cap=allowance,
                retrieval_reserve=allowance // 4,
                summary_reserve=allowance // 10,
            ),
        )
    except ContextEngineError as error:
        assert error.code in {
            "required_context_too_large",
            "layer_allocation_exceeds_budget",
            "cap_budget_too_small",
        }
        return
    assert counter.count_request(result.request).estimated_tokens <= allowance
    assert tuple(t.messages[0].content for t in originals) == tuple(texts)
    assert result.request.tools == tools
    assert result.messages[-1]["content"] == "Unique current question?"
    json.dumps(result.to_dict(include_content=True), ensure_ascii=False).encode("utf-8")


def oversized_selection(counter):
    """Inject optional over-allocation to exercise the normally defensive final shrink."""
    turns = tuple(make_turn(i, f"partition evidence {i}") for i in range(4))
    carrier = ContextCarrier(SCOPE, turns, turns, KeyedPins(SCOPE), Message("q", Role.USER, "Q"))
    carrier = PinLayer(counter, BudgetConfig(), "System", AT).apply(
        CapLayer(counter).apply(carrier)
    )
    required = carrier.plan.required_estimate.estimated_tokens
    budget = BudgetConfig(input_cap=required, retrieval_reserve=0, summary_reserve=0)
    ids = ("2", "3")
    chunks = chunk_turns(turns[:2], RetrievalConfig())
    carrier = replace(
        carrier,
        window_planned=True,
        retrieved_chunks=chunks,
        plan=replace(
            carrier.plan,
            input_allowance=required,
            retrieval_tokens=0,
            summary_tokens=0,
            window_tokens=0,
            window_turn_ids=ids,
        ),
    )
    carrier = replace(
        carrier,
        blocks=carrier.blocks
        + (
            ContextBlock(BlockKind.SUMMARY, "extra background " * 100),
            window_block(carrier, ids, counter),
            evidence_block(chunks, counter),
        ),
    )
    return carrier, budget


def test_final_shrink_order_termination_and_mandatory_preservation(counter):
    context, budget = oversized_selection(counter)
    original = context.blocks
    request, blocks, estimate, ids, chunks, drops = _finalize(context, counter, budget)
    assert request == context.required_request
    assert estimate.estimated_tokens == budget.input_allowance
    assert not ids and not chunks
    assert [d.kind for d in drops] == [
        BlockKind.SUMMARY,
        BlockKind.WINDOW,
        BlockKind.WINDOW,
        BlockKind.RETRIEVED,
        BlockKind.RETRIEVED,
    ]
    assert [d.source_id for d in drops] == [
        None,
        "2",
        "3",
        context.retrieved_chunks[-1].chunk_id,
        context.retrieved_chunks[0].chunk_id,
    ]
    assert context.blocks == original
    assert render_request(blocks, context.question) == request
    assert _finalize(context, counter, budget) == (request, blocks, estimate, ids, chunks, drops)


def test_finalizer_rejects_stale_state_and_fabricated_evidence(counter):
    context, budget = oversized_selection(counter)
    for changed in (
        replace(context, window_planned=False),
        replace(context, question=replace(context.question, content="drift")),
        replace(
            context,
            blocks=tuple(
                replace(b, content="invented") if b.kind == BlockKind.RETRIEVED else b
                for b in context.blocks
            ),
        ),
        replace(context, retrieved_chunks=()),
    ):
        with pytest.raises(LayerStateError):
            _finalize(changed, counter, budget)
    with pytest.raises(LayerStateError):
        _finalize(context, counter, replace(budget, input_cap=budget.input_cap + 1))


def test_counter_drift_at_final_recount_is_rejected(counter):
    context, _ = oversized_selection(counter)
    context = RetrieveLayer(counter).apply(
        PinLayer(counter, BudgetConfig(), "System", AT).apply(context)
    )
    context = WindowLayer(counter).apply(context)
    final_request = render_request(context.blocks, context.question)

    class DriftingCounter:
        hits = 0
        count_text = counter.count_text

        def count_request(self, request):
            estimate = counter.count_request(request)
            if request == final_request:
                self.hits += 1
                if self.hits > 1:
                    return replace(estimate, adapter_overhead_tokens=1)
            return estimate

    with pytest.raises(LayerStateError):
        _finalize(context, DriftingCounter(), BudgetConfig())


@pytest.mark.parametrize("invalid_type", [False, True])
def test_summary_policy_failures_are_typed_and_redacted(counter, invalid_type):
    class BrokenPolicy:
        def get_summary(self, history, scope, at):
            if invalid_type:
                return "invalid snapshot"
            raise RuntimeError("PRIVATE_PROVIDER_KEY")

    with pytest.raises(SummaryPolicyError) as caught:
        assemble(
            counter,
            history=tuple(make_turn(i, "old " * 100) for i in range(15)),
            summary_policy=BrokenPolicy(),
        )
    assert "PRIVATE_PROVIDER_KEY" not in json.dumps(caught.value.to_dict())
