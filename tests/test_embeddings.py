"""Optional hybrid (keyword + meaning) retrieval, tested offline with a concept embedder."""

import sys
from datetime import UTC, datetime

import numpy as np
import pytest

from context_engine import assemble_context, embeddings
from context_engine.config import BudgetConfig
from context_engine.embeddings import FunctionEmbedder, hybrid_scores
from context_engine.errors import ContractError
from context_engine.memory import MemoryStore
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

SCOPE = Scope("tenant", "chat")
AT = datetime(2026, 10, 31, tzinfo=UTC)
FILLER = "Routine telemetry stayed under review while responders compared notes. " * 3
HISTORY = tuple(
    Turn(f"t{i}", SCOPE, (Message(f"m{i}", Role.USER, f"{FILLER}Entry {i} logged."),), timestamp=AT)
    for i in range(60)
)
FACT = "The merchant involved was merchant-aurora."
HISTORY = (
    HISTORY[:5]
    + (Turn("fact", SCOPE, (Message("mf", Role.USER, f"{FILLER}{FACT}"),), timestamp=AT),)
    + HISTORY[5:]
)
REWORDED = "Which retailer or seller took part?"
CONCEPTS = {"merchant": 0, "retailer": 0, "seller": 0, "telemetry": 1, "responders": 2}


class Concepts:
    """Bag-of-concepts vectors: synonyms share a dimension. Counts calls for cache tests."""

    def __init__(self, name="concepts-v1"):
        self.name, self.document_calls = name, 0

    def _vector(self, text):
        vector = np.full(4, 0.01)
        for word in text.casefold().replace("-", " ").replace(".", " ").split():
            if word.rstrip("?,") in CONCEPTS:
                vector[CONCEPTS[word.rstrip("?,")]] += 1
        return vector

    def embed_documents(self, texts):
        self.document_calls += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)


def assemble(question, **kwargs):
    return assemble_context(
        HISTORY,
        question,
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=900),
        system="Answer from context.",
        at=AT,
        **kwargs,
    )


def test_keyword_retrieval_misses_reworded_question_but_hybrid_finds_it():
    assert "fact" not in assemble(REWORDED).diagnostics.retrieved_turn_ids
    hybrid = assemble(REWORDED, embedder=Concepts())
    assert "fact" in hybrid.diagnostics.retrieved_turn_ids
    assert "merchant-aurora" in str(hybrid.messages)


def test_no_embedder_output_is_unchanged_and_unlabelled():
    plain, explicit = (
        assemble("Which merchant was involved?"),
        assemble("Which merchant was involved?", embedder=None),
    )
    assert plain.to_dict(include_content=True) == explicit.to_dict(include_content=True)
    assert plain.diagnostics.config_fingerprint == explicit.diagnostics.config_fingerprint


def test_semantic_settings_change_the_config_fingerprint():
    plain = assemble(REWORDED).diagnostics.config_fingerprint
    a = assemble(REWORDED, embedder=Concepts("a")).diagnostics.config_fingerprint
    b = assemble(REWORDED, embedder=Concepts("b")).diagnostics.config_fingerprint
    c = assemble(
        REWORDED, embedder=Concepts("a"), semantic_weight=0.5
    ).diagnostics.config_fingerprint
    assert len({plain, a, b, c}) == 4


def test_keyword_questions_still_work_with_hybrid():
    result = assemble("Which merchant was involved?", embedder=Concepts())
    assert "fact" in result.diagnostics.retrieved_turn_ids


def test_document_vectors_are_cached_across_calls():
    embedder = Concepts("cache-check")
    assemble(REWORDED, embedder=embedder)
    first = embedder.document_calls
    assemble("Which seller was it?", embedder=embedder)
    assert first == 1 and embedder.document_calls == 1


def test_hybrid_scores_scale_each_signal():
    fused = hybrid_scores(np.array([0.0, 1.0, 0.5]), np.array([10.0, 0.0, 5.0]), 0.7)
    assert np.allclose(fused, [0.3, 0.7, 0.5])
    assert np.allclose(hybrid_scores(np.ones(3), np.ones(3)), 0)  # Flat signals add nothing.


@pytest.mark.parametrize("weight", [-0.1, 1.5, "0.7", None])
def test_invalid_weight_is_rejected(weight):
    with pytest.raises(ContractError):
        assemble(REWORDED, embedder=Concepts(), semantic_weight=weight)


@pytest.mark.parametrize(
    "vectors",
    [lambda texts: [[float("nan")] * 4 for _ in texts], lambda texts: [[1.0]] * (len(texts) + 1)],
)
def test_bad_embedder_output_is_a_typed_error(vectors):
    with pytest.raises(ContractError):
        assemble(REWORDED, embedder=FunctionEmbedder(f"bad-{id(vectors)}", vectors))


def test_query_dimension_mismatch_is_rejected():
    embedder = FunctionEmbedder("dims", lambda texts: [[1.0, 0.0]] * len(texts), lambda q: [1.0])
    with pytest.raises(ContractError):
        assemble(REWORDED, embedder=embedder)


def test_non_embedder_is_rejected():
    with pytest.raises(ContractError):
        assemble(REWORDED, embedder=object())


def test_memory_store_passes_embedder_through(tmp_path):
    store = MemoryStore(tmp_path / "s" / "memory.sqlite", clock=lambda: AT)
    store.create_scope(SCOPE)
    for turn in HISTORY:
        store.put_turn(
            turn, operation_id=turn.turn_id, expected_revision=store.snapshot(SCOPE).revision
        )
    _, plain = store.assemble(SCOPE, REWORDED, BudgetConfig(input_cap=900), system="s")
    _, hybrid = store.assemble(
        SCOPE, REWORDED, BudgetConfig(input_cap=900), system="s", embedder=Concepts()
    )
    assert "fact" not in plain.diagnostics.retrieved_turn_ids
    assert "fact" in hybrid.diagnostics.retrieved_turn_ids


@pytest.mark.parametrize(
    "cls,module,extra",
    [
        ("Model2VecEmbedder", "model2vec", "semantic"),
        ("FastEmbedEmbedder", "fastembed", "fastembed"),
    ],
)
def test_missing_extra_gives_install_hint(monkeypatch, cls, module, extra):
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ImportError, match=rf"\[{extra}\]"):
        getattr(embeddings, cls)()


def test_default_model_is_pinned():
    assert embeddings.DEFAULT_MODEL == "minishlab/potion-base-8M"
    assert len(embeddings.DEFAULT_REVISION) == 40


def test_strategy_eval_adds_semantic_strategies_only_with_embedder():
    from context_engine.evaluation.corpus import load_bundle
    from context_engine.evaluation.strategies import SEMANTIC, compare_strategies

    report = compare_strategies(
        load_bundle(), (900,), questions="paraphrased", embedder=Concepts("eval")
    )
    names = [r["strategy"] for r in report["results"]]
    assert names[-2:] == list(SEMANTIC) and report["embedder"] == "eval"
    assert all(r["fit"] == 31 for r in report["results"] if r["strategy"] in SEMANTIC)
