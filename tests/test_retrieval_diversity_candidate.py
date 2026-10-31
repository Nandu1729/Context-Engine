"""Synthetic candidate tests;no private dataset/provider access."""

from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from context_engine import pipeline
from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.errors import MemoryIntegrityError
from context_engine.layers.common import history_digest
from context_engine.layers.retrieve import ChunkIndex, RetrieveLayer, chunk_turns
from context_engine.models import KeyedPins
from scripts import retrieval_diversity_candidate as candidate
from scripts import retrieval_quality_probe as probe
from scripts.incident_demo import offline_network


def chunks():
    history, _, _ = probe.inputs(probe.cases()[2])
    return chunk_turns(history[:3], RetrievalConfig())


def test_diversity_penalizes_repetition_without_deleting_sources():
    a, b, c = chunks()
    ranked = [(10.0, a, frozenset({"x"})), (9.0, b, frozenset({"x"})), (8.0, c, frozenset({"y"}))]
    assert candidate.select_diverse(ranked, 2, lambda _: True) == (a, c)
    assert candidate.select_diverse(ranked, 3, lambda _: True) == (a, c, b)


def test_rejected_chunk_does_not_penalize_an_accepted_one():
    a, b, c = chunks()
    ranked = [(10.0, a, frozenset({"x"})), (9.0, b, frozenset({"x"})), (8.0, c, frozenset({"y"}))]
    assert candidate.select_diverse(ranked, 1, lambda xs: a not in xs) == (b,)


def test_ties_are_input_order_independent():
    ranked = [(1.0, c, frozenset({"x"})) for c in chunks()]
    assert candidate.select_diverse(ranked, 3, lambda _: True) == candidate.select_diverse(
        list(reversed(ranked)), 3, lambda _: True
    )


def test_empty_and_all_rejected():
    assert candidate.select_diverse([], 4, lambda _: True) == ()
    assert candidate.select_diverse([(1.0, chunks()[0], frozenset())], 4, lambda _: False) == ()


def test_overlap_rule_preserved():
    a = chunks()[0]
    b = replace(a, chunk_id="different-id")
    assert candidate.select_diverse(
        [(2.0, a, frozenset({"a"})), (1.0, b, frozenset({"b"}))], 4, lambda _: True
    ) == (a,)


def test_cancellation_check_runs_during_selection():
    with patch.object(candidate, "raise_if_cancelled", side_effect=RuntimeError("cancelled")):
        with pytest.raises(RuntimeError, match="cancelled"):
            candidate.select_diverse([(1.0, chunks()[0], frozenset({"x"}))], 4, lambda _: True)


def test_substitution_restored_after_failure():
    original = pipeline.RetrieveLayer
    with patch.object(candidate, "assemble_context", side_effect=RuntimeError("failed")):
        with pytest.raises(RuntimeError):
            candidate.candidate_assemble()
    assert pipeline.RetrieveLayer is original is RetrieveLayer


@pytest.mark.parametrize("reserve", [0, 1, 280])
def test_public_candidate_preserves_budget_required_and_sources(reserve):
    history, question, scope = probe.inputs(probe.cases()[0])
    with offline_network():
        result = candidate.candidate_assemble(
            history,
            question,
            KeyedPins(scope),
            BudgetConfig(input_cap=900, retrieval_reserve=reserve, summary_reserve=0),
            system=probe.SYSTEM,
            at=probe.AT,
        )
    assert result.diagnostics.estimate.estimated_tokens <= 900
    assert result.messages[0]["content"] == probe.SYSTEM
    assert result.messages[-1]["content"] == question
    probe.measure(result.messages, history, probe.cases()[0][2])
    assert pipeline.RetrieveLayer is RetrieveLayer


def wires(intervals):
    import json

    return [
        {
            "role": "user",
            "content": "[RETRIEVED DATA]\n"
            + json.dumps(
                [{"turn": "t0", "message": "m0", "start": a, "end": b} for a, b in intervals]
            ),
        }
    ]


@pytest.mark.parametrize(
    "new,expected",
    [
        ([(0, 3), (3, 10)], []),
        ([(0, 3), (5, 10)], [(3, 5)]),
        ([], [(0, 10)]),
        ([(2, 8)], [(0, 2), (8, 10)]),
    ],
)
def test_displaced_span_detection(new, expected):
    lost = candidate.lost_spans(wires([(0, 10)]), wires(new))
    assert [(s["start"], s["end"]) for s in lost] == expected


def test_cli_refuses_existing_output_before_running(tmp_path, monkeypatch):
    output = tmp_path / "prior.json"
    output.write_text("unchanged")
    monkeypatch.setattr(candidate, "run", lambda: pytest.fail("must not run"))
    with pytest.raises(SystemExit):
        candidate.main(["--output", str(output)])
    assert output.read_text() == "unchanged"


@pytest.mark.parametrize("damage", [None, "stale", "deleted"])
def test_index_parity_and_stale_source_rejection(damage):
    history, question, scope = probe.inputs(probe.cases()[0])
    config = RetrievalConfig()
    index = ChunkIndex(
        history_digest(history), candidate.digest(asdict(config)), chunk_turns(history, config)
    )
    args = (history, question, KeyedPins(scope), BudgetConfig(input_cap=900, summary_reserve=0))
    with offline_network():
        if damage:
            if damage == "stale":
                index = replace(index, history_fingerprint="stale")
            else:
                changed = history[1:]
                index = replace(index, history_fingerprint=history_digest(changed))
                args = (changed, *args[1:])
            with pytest.raises(MemoryIntegrityError):
                candidate.candidate_assemble(
                    *args, chunk_index=index, system=probe.SYSTEM, at=probe.AT
                )
        else:
            fresh = candidate.candidate_assemble(*args, system=probe.SYSTEM, at=probe.AT)
            cached = candidate.candidate_assemble(
                *args, chunk_index=index, system=probe.SYSTEM, at=probe.AT
            )
            assert fresh.request.to_wire() == cached.request.to_wire()
    assert pipeline.RetrieveLayer is RetrieveLayer


def test_frozen_candidate_rejects_new_runtime():
    with pytest.raises(ValueError, match="Baseline runtime changed"):
        candidate.run()


def test_saved_synthetic_candidate_reproduces_on_archived_runtime(tmp_path):
    """D106 evidence is frozen on 0.9.6; reproduce it with that preserved wheel."""
    import json
    import subprocess
    import sys

    from tests.test_runtime_transition import historical_dependencies

    wheel = candidate.ROOT / "archives/c11-summaries-0100"
    wheel = wheel / "context_engineering_core-0.9.6-py3-none-any.whl"
    program = """
import json, sys
sys.path[:0] = [*json.loads(sys.argv[3]), sys.argv[1], sys.argv[2]]
import context_engine
assert context_engine.__version__ == "0.9.6", context_engine.__file__
from scripts import retrieval_diversity_candidate as candidate
print(json.dumps(candidate.run()))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            program,
            str(wheel),
            str(candidate.ROOT),
            json.dumps(historical_dependencies()),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    report = json.loads(result.stdout)
    saved = json.loads((candidate.ROOT / "output/retrieval-diversity-001.json").read_text())
    assert report == saved
    assert report["baseline_events_preserved"]
    assert report["paraphrase_events_recovered"]
    assert report["source_span_loss_conditions"] > 0
    assert report["default_adopted"] is False


@pytest.mark.parametrize("damage", ["gate", "identity"])
def test_development_runner_rejects_before_private_data_access(tmp_path, monkeypatch, damage):
    import json

    from scripts import retrieval_diversity_review as review

    fake = {"continuation_gate": "PASS", "identity": candidate.identity()}
    fake["continuation_gate" if damage == "gate" else "identity"] = "bad"
    (tmp_path / "output").mkdir()
    (tmp_path / "output/retrieval-diversity-001.json").write_text(json.dumps(fake))
    monkeypatch.setattr(review, "ROOT", tmp_path)
    monkeypatch.setattr(review, "PRIOR", tmp_path / "nonexistent-private-data")
    destination = tmp_path / "new-output"
    with pytest.raises(ValueError, match="gate or identity"):
        review.run(destination)
    assert not destination.exists()
