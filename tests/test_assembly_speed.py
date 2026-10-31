"""0.12.1 speed paths return exactly what the full computations return."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from context_engine import assemble_context
from context_engine.config import BudgetConfig, TokenizerConfig
from context_engine.layers import common
from context_engine.models import (
    KeyedPins,
    Message,
    Role,
    Scope,
    ToolDefinition,
    Turn,
    canonical_json,
)
from context_engine.tokens import TiktokenCounter, estimated_tokens

SCOPE = Scope("tenant", "chat")
AT = datetime(2026, 10, 31, tzinfo=UTC)
HISTORY = tuple(
    Turn(
        f"t{i}", SCOPE, (Message(f"m{i}", Role.USER, f"Note {i}: crate {i} is in bay B-{i}. " * 3),)
    )
    for i in range(150)
)
TOOL = ToolDefinition(
    "lookup", "Find a crate", '{"type":"object","properties":{"id":{"type":"string"}}}'
)


def assemble(counter, budget=3000):
    return assemble_context(
        HISTORY,
        "Which bay holds crate 77?",
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=budget),
        system="Answer from context.",
        token_counter=counter,
        tools=(TOOL,),
        at=AT,
    )


@pytest.mark.parametrize(
    "config",
    [TokenizerConfig(), TokenizerConfig(calibration_factor=1.07, adapter_overhead_tokens=12)],
)
def test_estimate_tokens_equals_full_count(config):
    counter = TiktokenCounter(config)
    request = assemble(counter, 900).request
    assert counter.estimate_tokens(request) == counter.count_request(request).estimated_tokens
    assert estimated_tokens(counter, request) == counter.count_request(request).estimated_tokens


class PlainCounter:
    """A custom counter with only the protocol methods: no fast path, no memo."""

    def __init__(self):
        self.inner, self.requests = TiktokenCounter(), 0

    def count_text(self, text):
        return self.inner.count_text(text)

    def count_request(self, request):
        self.requests += 1
        return self.inner.count_request(request)


def test_custom_counter_gets_identical_output_without_fast_paths():
    plain = PlainCounter()
    custom, builtin = assemble(plain), assemble(TiktokenCounter())
    assert plain.requests > 0
    assert common._window_key(None, plain) is None
    assert custom.request.to_wire() == builtin.request.to_wire()
    assert (
        custom.to_dict(include_content=True)["diagnostics"]
        == builtin.to_dict(include_content=True)["diagnostics"]
    )


def test_window_memo_matches_a_fresh_scan_and_is_bounded():
    counter = TiktokenCounter()
    common._WINDOW_MEMO.clear()
    memoized = assemble(counter)
    assert 0 < len(common._WINDOW_MEMO) <= common._WINDOW_MEMO_SIZE
    common._WINDOW_MEMO.clear()
    common._history_digest.cache_clear()
    common._turn_json.cache_clear()
    fresh = assemble(counter)
    assert memoized.request.to_wire() == fresh.request.to_wire()
    for i in range(common._WINDOW_MEMO_SIZE + 5):
        assemble_context(
            HISTORY[:20],
            f"question {i}?",
            KeyedPins(SCOPE),
            BudgetConfig(input_cap=900),
            system="s",
            token_counter=counter,
        )
    assert len(common._WINDOW_MEMO) == common._WINDOW_MEMO_SIZE


def test_window_json_join_equals_canonical_list():
    turns = HISTORY[:3] + (
        replace(HISTORY[3], messages=(Message("x", Role.USER, 'quote " é 漢 \n'),)),
    )
    joined = "[" + ",".join(common._turn_json(t) for t in turns) + "]"
    assert joined == canonical_json(
        [{"turn": t.turn_id, "messages": [m.to_wire() for m in t.messages]} for t in turns]
    )


def test_changed_history_is_not_served_from_cache():
    counter = TiktokenCounter()
    before = assemble(counter)
    edited = (
        HISTORY[:77]
        + (
            replace(
                HISTORY[77], messages=(Message("m77", Role.USER, "Crate 77 moved to bay Z-9."),)
            ),
        )
        + HISTORY[78:]
    )
    after = assemble_context(
        edited,
        "Which bay holds crate 77?",
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=3000),
        system="Answer from context.",
        token_counter=counter,
        tools=(TOOL,),
    )
    assert "Z-9" in str(after.messages) and "Z-9" not in str(before.messages)
    assert before.diagnostics.history_fingerprint != after.diagnostics.history_fingerprint
