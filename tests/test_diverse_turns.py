"""Opt-in `diverse_turns`: at most one retrieved chunk per turn (0.16.0)."""

from datetime import UTC, datetime

import pytest

from context_engine import assemble_context
from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.errors import ContractError
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

SCOPE = Scope("tenant", "chat")
AT = datetime(2026, 10, 31, tzinfo=UTC)
LONG = " ".join(f"The garden plan lists tomato bed {i} near the fence." for i in range(40))
FILLER = "Filler entry {}: the weekly schedule was reviewed and nothing else changed at all."
HISTORY = (
    Turn("long", SCOPE, (Message("m-long", Role.USER, LONG),), timestamp=AT),
    Turn(
        "short",
        SCOPE,
        (Message("m-short", Role.USER, "The tomato seeds came from Lisbon."),),
        timestamp=AT,
    ),
    *(
        Turn(f"f{i}", SCOPE, (Message(f"m{i}", Role.USER, FILLER.format(i)),), timestamp=AT)
        for i in range(60)
    ),
)


def assemble(**kwargs):
    return assemble_context(
        HISTORY,
        "Where is the tomato bed and where did the tomato seeds come from?",
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=1500, retrieval_reserve=600),
        system="Answer from context.",
        at=AT,
        retrieval_config=RetrievalConfig(top_k=8),
        embedder=None,
        **kwargs,
    )


def test_default_can_spend_retrieval_on_one_long_turn():
    diagnostics = assemble().diagnostics
    assert len(diagnostics.retrieved_chunk_ids) > len(diagnostics.retrieved_turn_ids)


def test_diverse_turns_takes_one_chunk_per_turn():
    diagnostics = assemble(diverse_turns=True).diagnostics
    assert len(diagnostics.retrieved_chunk_ids) == len(diagnostics.retrieved_turn_ids)
    assert {"long", "short"} <= set(diagnostics.retrieved_turn_ids)


def test_diverse_turns_is_fingerprinted_and_off_by_default():
    assert (
        assemble().diagnostics.config_fingerprint
        == assemble(diverse_turns=False).diagnostics.config_fingerprint
    )
    assert (
        assemble().diagnostics.config_fingerprint
        != assemble(diverse_turns=True).diagnostics.config_fingerprint
    )


@pytest.mark.parametrize("value", [1, "yes", None])
def test_diverse_turns_must_be_boolean(value):
    with pytest.raises(ContractError):
        assemble(diverse_turns=value)
