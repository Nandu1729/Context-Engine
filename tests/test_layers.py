"""Independent C02 layer tests and source/budget invariants across composition."""

import json
import re
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from context_engine.budget import validate_request
from context_engine.config import (
    BudgetConfig,
    CapConfig,
    RetrievalConfig,
    Settings,
    TokenizerConfig,
)
from context_engine.context import ContextCarrier
from context_engine.demo import layer_demo
from context_engine.errors import (
    CapBudgetError,
    ConfigurationError,
    ContractError,
    LayerStateError,
    RequiredContextTooLarge,
    SummaryLeakageError,
)
from context_engine.evaluation.fixtures import validate_frozen_summary
from context_engine.layers import (
    CapLayer,
    FrozenSummaryPolicy,
    PinLayer,
    RetrieveLayer,
    SummaryLayer,
    SummarySnapshot,
    WindowLayer,
)
from context_engine.layers.common import (
    fits_block,
    history_digest,
    incremental_cost,
    render_request,
    window_block,
)
from context_engine.layers.retrieve import chunk_turns, lexical_tokens, overlaps
from context_engine.models import (
    BlockKind,
    KeyedPins,
    Message,
    Pin,
    Role,
    Scope,
    ToolCall,
    ToolDefinition,
    Turn,
)
from context_engine.tokens import TiktokenCounter

AT = datetime(2026, 9, 7, tzinfo=UTC)
SCOPE = Scope("tenant-a", "session-a")


@pytest.fixture(scope="module")
def counter():
    return TiktokenCounter()


def turn(index, content, *, role=Role.USER):
    return Turn(
        f"t{index}",
        SCOPE,
        (
            Message(
                f"m{index}",
                role,
                content,
                tool_call_id=f"call{index}" if role == Role.TOOL else None,
            ),
        ),
        timestamp=AT,
    )


def carrier(turns=(), *, question="Which partition carried the blame?", pins=()):
    return ContextCarrier(
        SCOPE, turns, turns, KeyedPins(SCOPE, pins), Message("question", Role.USER, question)
    )


def prepared(
    counter, turns=(), *, question="Which partition carried the blame?", budget=None, pins=()
):
    capped = CapLayer(counter).apply(carrier(turns, question=question, pins=pins))
    return PinLayer(
        counter, budget or BudgetConfig(input_cap=900), "Use supplied evidence.", AT
    ).apply(capped)


def block(context, kind):
    return next(item for item in context.blocks if item.kind == kind)


def no_window(counter, turns, *, question="partition", retrieval=280, summary=80):
    # Exact mandatory request + reservations: WINDOW has zero allocation.
    first = prepared(counter, turns, question=question)
    budget = BudgetConfig(
        input_cap=first.plan.required_estimate.estimated_tokens + retrieval + summary,
        retrieval_reserve=retrieval,
        summary_reserve=summary,
    )
    return prepared(counter, turns, question=question, budget=budget)


def test_cap_preserves_originals_turns_unicode_tool_metadata_and_marker(counter):
    text = "HEAD తెలుగు 👩🏽‍💻 " + "old evidence in middle. " * 80 + " 尾部 TAIL"
    original = turn(1, text, role=Role.TOOL)
    context = carrier((original,))
    layer = CapLayer(counter)
    result = layer.apply(context)
    shortened = result.working_turns[0].messages[0]
    assert shortened.content.startswith("HEAD") and shortened.content.endswith("TAIL")
    assert shortened.tool_call_id == original.messages[0].tool_call_id
    assert result.original_turns == context.original_turns
    assert original.messages[0].content.encode() == text.encode()
    assert counter.count_text(shortened.content) <= 35
    match = re.search(r"\n\[\.\.\. (\d+) tokens elided \.\.\.\]\n", shortened.content)
    assert match
    head = shortened.content[: match.start()]
    tail = shortened.content[match.end() :]
    assert int(match[1]) == counter.count_text(text[len(head) : len(text) - len(tail)])
    assert result == layer.apply(context)
    assert len(result.working_turns) == 1
    assert shortened.content.encode("utf-8").decode("utf-8") == shortened.content


def test_cap_leaves_short_empty_and_control_like_text_intact(counter):
    layer = CapLayer(counter)
    for text in ("", "hello", "<|endoftext|>", "\n   "):
        assert layer.cap_text(text) == text
    with pytest.raises(CapBudgetError):
        CapLayer(counter, CapConfig(1, 1, 1)).cap_text("many tokens " * 20)
    with pytest.raises(LayerStateError):
        layer.apply(prepared(counter))


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=250))
@settings(max_examples=45, deadline=None)
def test_cap_generated_unicode_always_fits_or_returns_a_typed_error(text):
    counter = TiktokenCounter()
    try:
        result = CapLayer(counter).cap_text(text)
    except CapBudgetError:
        return  # Some code points cannot fit with the mandatory marker/endpoints.
    assert counter.count_text(result) <= 35
    assert result.encode("utf-8").decode("utf-8") == result


def test_pin_preserves_system_and_active_facts_and_accounts_tools(counter):
    pin = Pin(SCOPE, "database", "PostgreSQL", "application", effective_at=AT)
    pins = (
        pin,
        replace(pin, key="future", effective_at=AT + timedelta(days=1)),
        replace(pin, key="expired", effective_at=AT - timedelta(days=2), expires_at=AT),
    )
    tool = ToolDefinition("lookup", "Find incidents", '{"type":"object"}')
    system = "Keep this instruction exactly.\n"
    layer = PinLayer(counter, BudgetConfig(), system, AT, (tool,))
    result = layer.apply(carrier(pins=pins))
    assert block(result, BlockKind.SYSTEM).content == system
    assert json.loads(block(result, BlockKind.PINNED).content) == [
        {"key": "database", "value": "PostgreSQL"}
    ]
    assert result.plan.required_estimate.tool_schema_tokens > 0
    assert result.required_request.messages[-1].content == result.question.content
    assert all(m.role == Role.USER for m in result.required_request.messages[1:])
    assert result == layer.apply(carrier(pins=pins))
    oversized = replace(pin, value="secret-data " * 500)
    with pytest.raises(RequiredContextTooLarge):
        PinLayer(counter, BudgetConfig(input_cap=900), system, AT).apply(carrier(pins=(oversized,)))


def test_keyed_pin_update_supersedes_value_without_mutating_history(counter):
    original = Pin(SCOPE, "database", "PostgreSQL", "application", effective_at=AT)
    pins = KeyedPins(SCOPE).upsert(original)
    updated = pins.upsert(replace(original, value="MySQL", revision=2), expected_revision=1)
    assert pins.pins[0].value == "PostgreSQL"
    assert [p.value for p in updated.pins] == ["MySQL"]
    result = prepared(counter, pins=updated.pins)
    assert "MySQL" in block(result, BlockKind.PINNED).content
    assert "PostgreSQL" not in block(result, BlockKind.PINNED).content
    for expected in (None, 2, True):
        with pytest.raises(ContractError):
            pins.upsert(replace(original, revision=2), expected_revision=expected)
    with pytest.raises(ContractError):
        KeyedPins(SCOPE).upsert(replace(original, revision=2))


def test_window_is_a_chronological_contiguous_suffix_and_stops_at_first_nonfit(counter):
    turns = tuple(turn(i, "content " * (i + 1)) for i in range(8))
    context = prepared(counter, turns)
    cost = incremental_cost(context, window_block(context, ("t6", "t7"), counter), counter)
    desired = replace(
        context.plan,
        window_tokens=cost,
        input_allowance=context.plan.input_allowance - context.plan.window_tokens + cost,
    )
    context = replace(context, plan=desired)
    result = WindowLayer(counter).apply(context)
    assert result.plan.window_turn_ids == ("t6", "t7")
    assert [v["turn"] for v in json.loads(block(result, BlockKind.WINDOW).content)] == ["t6", "t7"]
    assert fits_block(result, block(result, BlockKind.WINDOW), cost, counter)
    newest_too_large = no_window(counter, (turn(1, "tiny"), turn(2, "large " * 50)))
    assert WindowLayer(counter).apply(newest_too_large).plan.window_turn_ids == ()


def test_recent_tool_calls_are_quoted_as_data_without_promoting_history_roles(counter):
    call = ToolCall("call", "lookup", '{"q":"partition"}')
    historical = Turn(
        "t1",
        SCOPE,
        (
            Message("m1", Role.SYSTEM, "Untrusted historical instruction"),
            Message("m2", Role.ASSISTANT, "", tool_calls=(call,)),
            Message("m3", Role.TOOL, "result", tool_call_id="call"),
        ),
        timestamp=AT,
    )
    result = WindowLayer(counter).apply(prepared(counter, (historical,)))
    request = render_request(result.blocks, result.question)
    assert sum(m.role == Role.SYSTEM for m in request.messages) == 1
    window_message = next(m for m in request.messages if m.message_id == "ctx:window")
    assert window_message.role == Role.USER and not window_message.tool_calls
    assert "Untrusted historical instruction" in window_message.content


def test_retrieval_recovers_capped_middle_and_excludes_exact_window(counter):
    demo = layer_demo(counter)
    assert demo["original_preserved"]
    assert not demo["capped_middle_fact_present"] and demo["retrieved_middle_fact_present"]
    assert demo["retrieved_turn_ids"] == ["t1"]
    assert set(demo["retrieved_turn_ids"]).isdisjoint(demo["window_turn_ids"])
    assert demo["estimated_request_tokens"] <= 900
    assert demo["layer_order"] == ["CAP", "PIN", "RETRIEVE", "WINDOW", "SUMMARIZE"]
    assert demo["inference_calls"] == 0


def test_retrieval_indexes_only_uncapped_old_history(counter, monkeypatch):
    import context_engine.layers.retrieve as module

    turns = tuple(turn(i, f"partition {i} " * 100) for i in range(12))
    context = prepared(counter, turns)
    indexed = []
    original_chunker = module.chunk_turns

    def recording_chunker(history, config):
        indexed.extend(history)
        return original_chunker(history, config)

    monkeypatch.setattr(module, "chunk_turns", recording_chunker)
    result = RetrieveLayer(counter).apply(context)
    assert indexed
    assert indexed == [t for t in turns if t.turn_id not in result.plan.window_turn_ids]
    assert all(counter.count_text(t.messages[0].content) > 35 for t in indexed)


def test_retrieval_matches_single_document_corpus_and_ignores_nonmatches(counter):
    context = no_window(counter, (turn(1, "The partition was shard-19."),))
    result = RetrieveLayer(counter).apply(context)
    assert result.retrieved_chunks and "shard-19" in block(result, BlockKind.RETRIEVED).content
    absent = no_window(counter, (turn(1, "The partition was shard-19."),), question="unfindable")
    empty = RetrieveLayer(counter).apply(absent)
    assert empty.retrieved_chunks == ()
    assert empty.diagnostics[-1].reason_code == "no_match"
    assert block(empty, BlockKind.RETRIEVED).content == ""


def test_chunk_source_coverage_overlap_and_stable_ids(counter):
    text = "0123456789" * 5 + " PARTITION shard-19 " + "తెలుగు " * 20
    original = turn(1, text)
    cfg = RetrievalConfig(chunk_characters=60, overlap_characters=25)
    chunks = chunk_turns((original,), cfg)
    assert chunks == chunk_turns((original,), cfg)
    assert chunks[0].source.start == 0 and chunks[-1].source.end == len(text)
    assert any("PARTITION shard-19" in chunk.content for chunk in chunks)
    for chunk in chunks:
        chunk.validate_source(original)
    revised = chunk_turns((replace(original, revision=2),), cfg)
    assert {c.chunk_id for c in chunks}.isdisjoint(c.chunk_id for c in revised)
    result = RetrieveLayer(counter, cfg).apply(no_window(counter, (original,)))
    assert result.retrieved_chunks
    for i, left in enumerate(result.retrieved_chunks):
        for right in result.retrieved_chunks[i + 1 :]:
            assert not overlaps(left, right)
    assert (
        incremental_cost(result, block(result, BlockKind.RETRIEVED), counter)
        <= result.plan.retrieval_tokens
    )


def test_retrieval_ties_are_deterministic_and_top_k_and_floor_are_obeyed(counter):
    turns = tuple(turn(i, "partition shard-19") for i in range(4))
    context = no_window(counter, turns, retrieval=700)
    layer = RetrieveLayer(counter, RetrievalConfig(top_k=2))
    left, right = layer.apply(context), layer.apply(context)
    assert len(left.retrieved_chunks) == 2
    assert left.retrieved_chunks == right.retrieved_chunks
    assert [c.chunk_id for c in left.retrieved_chunks] == sorted(
        c.chunk_id for c in left.retrieved_chunks
    )
    assert (
        RetrieveLayer(counter, RetrievalConfig(minimum_score=1e6)).apply(context).retrieved_chunks
        == ()
    )


@pytest.mark.parametrize("question", ["", "   ", "!!!"])
def test_empty_queries_return_empty_evidence(counter, question):
    result = RetrieveLayer(counter).apply(
        no_window(counter, (turn(1, "partition"),), question=question)
    )
    assert result.retrieved_chunks == ()
    assert result.diagnostics[-1].reason_code == "empty_query"


def test_empty_and_punctuation_history_and_zero_reserves_are_safe(counter):
    for turns in ((), (turn(1, ""),), (turn(1, "!!!"),)):
        result = RetrieveLayer(counter).apply(no_window(counter, turns))
        assert result.retrieved_chunks == ()
    result = RetrieveLayer(counter).apply(no_window(counter, (turn(1, "partition"),), retrieval=0))
    assert result.diagnostics[-1].reason_code == "zero_reserve"
    assert result.retrieved_chunks == ()


def test_search_normalization_applies_identically_to_query_and_document(counter):
    assert lexical_tokens("ＳＨＡＲＤ-19") == lexical_tokens("shard-19")
    for text, question in (("ПАРТИЦИЯ shard-19", "партиция"), ("తెలుగు partition", "తెలుగు")):
        result = RetrieveLayer(counter).apply(
            no_window(counter, (turn(1, text),), question=question)
        )
        assert result.retrieved_chunks


def test_shared_plan_and_snapshot_changes_fail_closed(counter):
    turns = tuple(turn(i, "partition " * 30) for i in range(10))
    prepared_context = prepared(counter, turns)
    retrieved = RetrieveLayer(counter).apply(prepared_context)
    assert (
        WindowLayer(counter).apply(retrieved).plan.window_turn_ids == retrieved.plan.window_turn_ids
    )
    for changed in (
        replace(retrieved, question=replace(retrieved.question, content="changed question")),
        replace(
            retrieved, pins=KeyedPins(SCOPE, (Pin(SCOPE, "key", "value", "app", effective_at=AT),))
        ),
        replace(retrieved, plan=replace(retrieved.plan, window_turn_ids=())),
    ):
        with pytest.raises(LayerStateError):
            WindowLayer(counter).apply(changed)
    with pytest.raises(LayerStateError):
        WindowLayer(TiktokenCounter(TokenizerConfig(calibration_factor=2))).apply(retrieved)
    with pytest.raises(LayerStateError):
        RetrieveLayer(counter).apply(carrier(turns))
    reparsed = PinLayer(counter, BudgetConfig(input_cap=900), "Use supplied evidence.", AT).apply(
        retrieved
    )
    assert not reparsed.window_planned and not reparsed.retrieved_chunks
    assert all(b.kind not in (BlockKind.RETRIEVED, BlockKind.WINDOW) for b in reparsed.blocks)


def test_summary_reuses_exact_omitted_history_and_preserves_provenance(counter):
    turns = (turn(1, "old incident logs"), turn(2, "old incident updates"))
    context = WindowLayer(counter).apply(no_window(counter, turns))
    snapshot = SummarySnapshot.from_history(
        scope=SCOPE,
        content="An incident was investigated.",
        history=turns,
        policy_version="test-v1",
        created_at=AT,
        expires_at=AT + timedelta(hours=1),
    )
    policy = FrozenSummaryPolicy(snapshot)
    assert policy.get_summary(turns, SCOPE, AT) is snapshot
    result = SummaryLayer(counter, policy, AT).apply(context)
    assert result.diagnostics[-1].reason_code == "summary_reused"
    summary = block(result, BlockKind.SUMMARY)
    assert summary.content == snapshot.content
    assert {ref.turn_id for ref in summary.sources} == {"t1", "t2"}
    assert summary.prefix_stable
    assert fits_block(result, summary, context.plan.summary_tokens, counter)
    for source in summary.sources:
        source.extract(next(t for t in turns if t.turn_id == source.turn_id))
    with pytest.raises(FrozenInstanceError):
        snapshot.content = "changed"


def test_summary_rejects_stale_revision_deletion_scope_and_expiry(counter):
    turns = (turn(1, "incident"),)
    snapshot = SummarySnapshot.from_history(
        scope=SCOPE,
        content="An incident occurred.",
        history=turns,
        policy_version="v1",
        created_at=AT,
        expires_at=AT + timedelta(hours=1),
    )
    for history, scope, at in (
        ((), SCOPE, AT),
        ((replace(turns[0], revision=2),), SCOPE, AT),
        (turns, Scope("other", "s"), AT),
        (turns, SCOPE, AT + timedelta(hours=1)),
        (turns, SCOPE, AT - timedelta(seconds=1)),
    ):
        assert not snapshot.matches(history, scope, at)
    stale = replace(snapshot, history_fingerprint="stale")
    result = SummaryLayer(counter, FrozenSummaryPolicy(stale), AT).apply(no_window(counter, turns))
    assert not block(result, BlockKind.SUMMARY).content
    assert result.diagnostics[-1].reason_code == "summary_unavailable_or_stale"


def test_summary_disabled_empty_history_empty_fixture_and_overbudget(counter):
    turns = (turn(1, "incident"),)
    snapshot = SummarySnapshot.from_history(
        scope=SCOPE, content="summary " * 200, history=turns, policy_version="v1", created_at=AT
    )
    result = SummaryLayer(counter, FrozenSummaryPolicy(snapshot), AT).apply(
        no_window(counter, turns)
    )
    assert result.diagnostics[-1].reason_code == "summary_over_budget"
    assert not block(result, BlockKind.SUMMARY).content
    assert (
        SummaryLayer(counter, None, AT).apply(no_window(counter, turns)).diagnostics[-1].reason_code
        == "summary_disabled"
    )
    assert (
        SummaryLayer(counter, FrozenSummaryPolicy(snapshot), AT)
        .apply(prepared(counter))
        .diagnostics[-1]
        .reason_code
        == "no_old_history"
    )
    empty = replace(snapshot, content="")
    assert (
        SummaryLayer(counter, FrozenSummaryPolicy(empty), AT)
        .apply(no_window(counter, turns))
        .diagnostics[-1]
        .reason_code
        == "empty_summary"
    )


@pytest.mark.parametrize("content", ["shard-19", "SHARD 19", "ＳＨＡＲＤ-19", "shard\u200b-19"])
def test_benchmark_summary_leakage_rejected_before_layer_use(content):
    snapshot = SummarySnapshot.from_history(
        scope=SCOPE, content=content, history=(), policy_version="fixture-v1", created_at=AT
    )
    with pytest.raises(SummaryLeakageError) as caught:
        validate_frozen_summary(snapshot, ("shard-19",))
    assert "shard-19" not in json.dumps(caught.value.to_dict())
    clean = replace(snapshot, content="An incident was discussed.")
    assert validate_frozen_summary(clean, ("shard-19",)).snapshot is clean
    for aliases in ((), ("",), ("---",)):
        with pytest.raises(ContractError):
            validate_frozen_summary(clean, aliases)


@pytest.mark.parametrize(
    "config",
    [
        {"chunk_characters": 0},
        {"overlap_characters": -1},
        {"overlap_characters": 360},
        {"top_k": False},
        {"minimum_score": float("nan")},
        {"k1": 0},
        {"b": 2},
    ],
)
def test_retrieval_config_validation(config):
    with pytest.raises(ConfigurationError):
        RetrievalConfig(**config)


def test_layer_configuration_environment_overrides_are_validated():
    settings = Settings.from_env(
        {
            "CAP_MAX_TOKENS": "48",
            "RETRIEVAL_TOP_K": "2",
            "BM25_K1": "1.2",
            "RETRIEVAL_CHUNK_CHARACTERS": "200",
        }
    )
    assert settings.cap.max_tokens == 48
    assert settings.retrieval.top_k == 2 and settings.retrieval.k1 == 1.2
    assert settings.retrieval.chunk_characters == 200
    for env in ({"CAP_HEAD_TOKENS": "-1"}, {"BM25_K1": "nan"}, {"BM25_B": "invalid"}):
        with pytest.raises(ConfigurationError):
            Settings.from_env(env)
    with pytest.raises(ConfigurationError):
        RetrievalConfig(k1=10**500)


@given(st.integers(min_value=500, max_value=1400), st.integers(min_value=0, max_value=12))
@settings(max_examples=30, deadline=None)
def test_composed_layers_keep_budget_and_originals_for_generated_histories(budget, count):
    counter = TiktokenCounter()
    originals = tuple(turn(i, f"partition evidence {i}. " * 10) for i in range(count))
    config = BudgetConfig(input_cap=budget, retrieval_reserve=180, summary_reserve=50)
    context = prepared(counter, originals, budget=config)
    before = history_digest(originals)
    retrieved = RetrieveLayer(
        counter, RetrievalConfig(chunk_characters=100, overlap_characters=20)
    ).apply(context)
    result = SummaryLayer(counter, None, AT).apply(WindowLayer(counter).apply(retrieved))
    assert history_digest(result.original_turns) == before
    assert set(c.source.turn_id for c in result.retrieved_chunks).isdisjoint(
        result.plan.window_turn_ids
    )
    request = render_request(result.blocks, result.question, result.required_request.tools)
    assert (
        validate_request(request=request, config=config, counter=counter).estimated_tokens <= budget
    )
