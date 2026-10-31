"""Offline strategy comparison: reproducible retention figures and scoring isolation."""

import json

import pytest

from context_engine.cli import main
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.strategies import ORDER, SEMANTIC, compare_strategies

ALL = ORDER + tuple(SEMANTIC)  # 0.15.0: hybrid strategies are reported by default.


@pytest.fixture(scope="module")
def report():
    return compare_strategies(load_bundle(), (900, 3000), include_probes=True)


def row(report, budget, strategy):
    return next(r for r in report["results"] if (r["budget"], r["strategy"]) == (budget, strategy))


def test_every_strategy_and_budget_reported_without_inference(report):
    assert report["inference_calls"] == 0 and report["status"] == "COMPLETE"
    assert [(r["budget"], r["strategy"]) for r in report["results"]] == [
        (b, s) for b in (900, 3000) for s in ALL
    ]
    for entry in report["results"]:
        assert entry["probes"] == 31 and len(entry["probe_results"]) == 31
        assert entry["answer_correct"] == "NOT_EVALUATED"


# Deterministic context-retention figures. combined (the 0.11.0 default, WINDOW
# recovery on) keeps 31/31. combined_no_recover/900 = 29 and /3000 = 19 reproduce the
# historical C06 A5 retention and the recorded S11 regression.
EXPECTED = {
    (900, "full_history"): 0,
    (900, "recent_window"): 1,
    (900, "summary_window"): 1,
    (900, "retrieval_window"): 31,
    (900, "combined"): 31,
    (900, "combined_no_recover"): 29,
    (3000, "full_history"): 0,
    (3000, "recent_window"): 4,
    (3000, "summary_window"): 3,
    (3000, "retrieval_window"): 31,
    (3000, "combined"): 31,
    (3000, "combined_no_recover"): 19,
}


@pytest.mark.parametrize("key,expected", EXPECTED.items())
def test_reproducible_evidence_retention(report, key, expected):
    entry = row(report, *key)
    assert entry["evidence_at_source"] == expected
    # The extractive summary never carries a planted answer on this corpus.
    assert entry["fact_in_summary"] == 0


def test_full_history_is_non_fit_not_truncated(report):
    for budget in (900, 3000):
        entry = row(report, budget, "full_history")
        assert entry["fit"] == 0 and entry["median_input_tokens"] is None
        assert all(p["input_tokens"] is None for p in entry["probe_results"])


def test_every_assembled_strategy_fits_its_allowance(report):
    for entry in report["results"]:
        if entry["strategy"] == "full_history":
            continue
        assert entry["fit"] == 31
        assert all(p["input_tokens"] <= entry["budget"] for p in entry["probe_results"])
        assert 0 < entry["median_token_reduction"] < 1


def test_retrieval_metrics_only_for_retrieving_strategies(report):
    assert row(report, 900, "recent_window")["retrieval_precision"] is None
    entry = row(report, 900, "retrieval_window")
    assert 0 < entry["retrieval_precision"] <= 1 and 0 < entry["retrieval_recall"] <= 1


def test_default_recovery_restores_capped_window_evidence(report):
    for budget in (900, 3000):
        assert row(report, budget, "combined")["retrieval_recall"] == 1.0
        assert row(report, budget, "combined_no_recover")["retrieval_recall"] < 1.0


def test_ground_truth_not_passed_to_engine(monkeypatch):
    import context_engine.evaluation.strategies as strategies

    calls = []
    original = strategies.assemble_context

    def spy(history, question, pins, budget, **kwargs):
        calls.append((history, question, pins, kwargs))
        return original(history, question, pins, budget, **kwargs)

    monkeypatch.setattr(strategies, "assemble_context", spy)
    bundle = load_bundle()
    compare_strategies(bundle, (900,))
    questions = {f["question"] for f in bundle.facts}
    scenario = bundle.job(bundle.facts[0]["question"]).arguments
    assert calls
    for history, question, pins, kwargs in calls:
        # Engine input is exactly the scenario plus a fact question: no answer key fields.
        assert question in questions
        assert history == scenario["history"] and pins == scenario["pinned_facts"]
        assert kwargs["system"] == scenario["system"]
        assert set(kwargs) <= {
            "system",
            "at",
            "token_counter",
            "cap_config",
            "retrieval_config",
            "options",
            "summary_policy",
            "embedder",  # None for named strategies; the model for *_semantic ones.
        }


def test_invalid_budgets_rejected():
    with pytest.raises(ValueError):
        compare_strategies(load_bundle(), (0,))


def test_cli_saves_without_overwrite(tmp_path, capsys):
    target = tmp_path / "strategies.json"
    assert main(["strategy-eval", "--budget", "900", "--output", str(target)]) == 0
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert {r["strategy"] for r in saved["results"]} == set(ALL)
    assert "probe_results" not in saved["results"][0]
    capsys.readouterr()
    assert main(["strategy-eval", "--budget", "900", "--output", str(target)]) == 1
    assert main(["strategy-eval", "--budget", "-5"]) == 1


def test_assemble_strategy_matches_scored_request(report):
    from context_engine.evaluation.strategies import assemble_strategy

    bundle = load_bundle()
    probes = {p["fact_id"]: p for p in row(report, 900, "combined")["probe_results"]}
    for fact in bundle.facts[:3]:
        result, budget = assemble_strategy(bundle, fact, 900, "combined")
        assert (
            result.diagnostics.estimate.estimated_tokens == probes[fact["fact_id"]]["input_tokens"]
        )
        assert budget.input_allowance == 900 and result.diagnostics.remaining_tokens >= 0
    with pytest.raises(ValueError):
        assemble_strategy(bundle, bundle.facts[0], 900, "full_history")
