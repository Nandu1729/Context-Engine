"""0.18.0 core defaults match ChatMemory: 40% retrieval share, one chunk per 90 reserve
tokens (at least 4), at most one chunk per turn. Explicit values keep their meaning."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from context_engine import assemble_context
from context_engine.chat_memory import ChatMemory
from context_engine.config import (
    DEFAULT_RETRIEVAL_SHARE,
    TOKENS_PER_CHUNK,
    BudgetConfig,
    RetrievalConfig,
    Settings,
)
from context_engine.errors import ConfigurationError
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

SCOPE = Scope("tenant", "chat")
AT = datetime(2026, 11, 2, tzinfo=UTC)
FILLER = "Entry {}: the weekly schedule was reviewed, and the tomato bed {} was watered."
HISTORY = tuple(
    Turn(f"t{i}", SCOPE, (Message(f"m{i}", Role.USER, FILLER.format(i, i)),), timestamp=AT)
    for i in range(400)
)


def assemble(budget, **kwargs):
    return assemble_context(
        HISTORY,
        "Which tomato bed was watered?",
        KeyedPins(SCOPE),
        budget,
        system="Answer from context.",
        at=AT,
        embedder=None,
        **kwargs,
    )


def test_reserve_is_forty_percent_of_the_allowance():
    assert DEFAULT_RETRIEVAL_SHARE == 0.4 and TOKENS_PER_CHUNK == 90
    assert BudgetConfig().retrieval_reserve is None
    assert BudgetConfig().effective_retrieval_reserve == 1200
    assert BudgetConfig(input_cap=900).effective_retrieval_reserve == 360
    capped = BudgetConfig(input_cap=8000, provider_input_cap=5000)
    assert capped.effective_retrieval_reserve == 2000  # Of the smallest ceiling.
    assert BudgetConfig(retrieval_reserve=280).effective_retrieval_reserve == 280


def test_replacing_the_cap_rescales_an_automatic_reserve():
    smaller = replace(BudgetConfig(), input_cap=900)
    assert smaller.effective_retrieval_reserve == 360
    fixed = replace(BudgetConfig(retrieval_reserve=280), input_cap=900)
    assert fixed.effective_retrieval_reserve == 280


def test_automatic_reserve_still_fits_with_the_summary_reserve():
    assert BudgetConfig(input_cap=140).effective_retrieval_reserve == 56
    with pytest.raises(ConfigurationError):
        BudgetConfig(input_cap=100)  # 40 + 80 summary tokens exceed 100.
    with pytest.raises(ConfigurationError):
        BudgetConfig(retrieval_reserve=None, input_cap=100, summary_reserve=70)


@pytest.mark.parametrize("value", [-1, 1.5, True, "280"])
def test_explicit_reserve_must_be_a_nonnegative_integer(value):
    with pytest.raises(ConfigurationError):
        BudgetConfig(retrieval_reserve=value)


def test_automatic_settings_fingerprint_as_their_resolved_values():
    automatic = assemble(BudgetConfig()).diagnostics
    explicit = assemble(
        BudgetConfig(retrieval_reserve=1200),
        retrieval_config=RetrievalConfig(top_k=13),
        diverse_turns=True,
    ).diagnostics
    assert automatic.config_fingerprint == explicit.config_fingerprint
    assert len(automatic.retrieved_chunk_ids) == 1200 // TOKENS_PER_CHUNK == 13
    assert len(automatic.retrieved_chunk_ids) == len(automatic.retrieved_turn_ids)
    assert RetrievalConfig().effective_top_k(1200) == 13
    assert RetrievalConfig(top_k=2).effective_top_k(1200) == 2


def test_automatic_top_k_has_a_floor_of_four():
    budget = BudgetConfig(input_cap=900, retrieval_reserve=350)  # 350 // 90 = 3.
    assert len(assemble(budget).diagnostics.retrieved_chunk_ids) == 4
    roomier = assemble(budget, retrieval_config=RetrievalConfig(top_k=6)).diagnostics
    assert len(roomier.retrieved_chunk_ids) > 4  # Space was not the limit.


def test_explicit_old_defaults_reproduce_0_17():
    old = assemble(
        BudgetConfig(retrieval_reserve=280),
        retrieval_config=RetrievalConfig(top_k=4),
        diverse_turns=False,
    ).diagnostics
    assert len(old.retrieved_chunk_ids) == 4
    assert old.config_fingerprint != assemble(BudgetConfig()).diagnostics.config_fingerprint


def test_core_defaults_match_chat_memory(tmp_path):
    memory = ChatMemory(tmp_path / "chat.sqlite", embedder=None)
    for i in range(400):
        memory.add("user", FILLER.format(i, i))
    question = "Which tomato bed was watered?"
    mine = memory.assemble(question).diagnostics
    snapshot = memory.store.snapshot(memory.scope)
    core = assemble_context(
        snapshot.history,
        question,
        snapshot.pins,
        BudgetConfig(),
        system=memory.system,
        at=snapshot.at,
        embedder=None,
    ).diagnostics
    assert core.retrieved_chunk_ids == mine.retrieved_chunk_ids
    assert core.kept_turn_ids == mine.kept_turn_ids


def test_environment_settings_default_to_automatic():
    settings = Settings.from_env({})
    assert settings.budget.retrieval_reserve is None and settings.retrieval.top_k is None
    explicit = Settings.from_env({"RETRIEVAL_RESERVE_TOKENS": "280", "RETRIEVAL_TOP_K": "4"})
    assert explicit.budget.retrieval_reserve == 280 and explicit.retrieval.top_k == 4
