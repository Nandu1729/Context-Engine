"""Lexical-retrieval stress test: reworded questions with no shared evidence words."""

import json

import pytest

from context_engine.cli import main
from context_engine.errors import BenchmarkError
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.strategies import (
    compare_strategies,
    evidence_sentence,
    load_paraphrases,
    paraphrase_overlaps,
)


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def report(bundle):
    return compare_strategies(bundle, (900, 3000), questions="paraphrased")


def test_every_fact_has_a_paraphrase_with_no_shared_evidence_words(bundle):
    questions = load_paraphrases(bundle)
    assert set(questions) == {f["fact_id"] for f in bundle.facts}
    assert paraphrase_overlaps(bundle, questions) == {}
    for fact in bundle.facts:
        assert questions[fact["fact_id"]] != fact["question"]
        assert fact["expected"].casefold() not in questions[fact["fact_id"]].casefold()


def test_overlap_rule_catches_shared_words_and_word_starts(bundle):
    questions = load_paraphrases(bundle)
    leaky = {
        **questions,
        "merchant": "Which merchant took part?",
        "database": "Where was data stored?",
    }
    found = paraphrase_overlaps(bundle, leaky)
    assert found["merchant"] == ["merchant", "merchant~merchant-aurora"]
    assert found["database"] == ["stored~storing"]
    assert "merchant-aurora" in evidence_sentence(bundle, bundle.fact("merchant"))


# Deterministic retention with paraphrased questions (original questions: see
# tests/test_strategies.py). Lexical BM25 retrieval loses most evidence without
# shared words; WINDOW-only results do not depend on the question.
EXPECTED = {
    (900, "recent_window"): 1,
    (900, "summary_window"): 1,
    (900, "retrieval_window"): 6,
    (900, "combined"): 3,
    (900, "combined_no_recover"): 4,
    (3000, "recent_window"): 4,
    (3000, "summary_window"): 3,
    (3000, "retrieval_window"): 7,
    (3000, "combined"): 3,
    (3000, "combined_no_recover"): 3,
}


@pytest.mark.parametrize("key,expected", EXPECTED.items())
def test_paraphrased_retention_is_pinned(report, key, expected):
    entry = next(r for r in report["results"] if (r["budget"], r["strategy"]) == key)
    assert entry["evidence_at_source"] == expected


def test_report_labels_question_set_and_runs_offline(report):
    assert report["question_set"] == "paraphrased" and report["inference_calls"] == 0
    with pytest.raises(ValueError):
        compare_strategies(load_bundle(), (900,), questions="other")


def test_cli_paraphrased_option(tmp_path, capsys):
    out = tmp_path / "para.json"
    assert (
        main(
            ["strategy-eval", "--budget", "900", "--questions", "paraphrased", "--output", str(out)]
        )
        == 0
    )
    assert json.loads(out.read_text())["question_set"] == "paraphrased"


def test_malformed_paraphrase_file_is_rejected(bundle, monkeypatch):
    import context_engine.evaluation.strategies as strategies

    monkeypatch.setattr(
        strategies, "read_resource", lambda name: '{"schema_version": 1, "questions": {}}'
    )
    with pytest.raises(BenchmarkError):
        strategies.load_paraphrases(bundle)
