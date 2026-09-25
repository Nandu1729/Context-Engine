"""Fixture scoring plumbing must never masquerade as live quality evidence."""

import copy
import socket

import pytest

from context_engine.errors import BenchmarkError
from context_engine.evaluation.heldout import load, prepare
from context_engine.evaluation.heldout.scoring import (
    contains,
    empty_responses,
    normalize,
    score_test,
    scoring_freeze,
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Scoring attempted a network call")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def prepared():
    return prepare(split="evaluation", retention=True)


def responses(prepared):
    value = empty_responses(prepared)
    _, truth, _, _ = load()
    for row in prepared["rows"]:
        value["responses"].append(
            {
                **{key: row[key] for key in ("case", "variant", "budget", "request_hash")},
                "status": "response",
                "answer": truth[row["case"]]["answer"],
            }
        )
    return value


def test_scoring_protocol_frozen():
    assert scoring_freeze()["id"] == "heldout-scoring-v1"


def test_normalization_and_forbidden_boundaries():
    assert normalize("  ＡMBER\nTeam ") == "amber team"
    assert contains("value is 3.", "3")
    assert not contains("value is 43", "3")
    assert contains("INJECTED-EVAL!", "injected-eval")
    assert normalize("Indigo.") != normalize("Indigo")


def test_literal_retention_checks_working_text_not_source_ids(prepared):
    middle = [r for r in prepared["rows"] if r["case"] == "eval-middle"]
    assert any("m0" in r["selected_messages"] and r["retained"] is False for r in middle)
    assert all(r["retained"] is None for r in prepared["rows"] if r["category"] == "no_answer")
    assert prepared["content_retention"] == "SYNTHETIC_LITERAL_CHECK"


def test_empty_answers_remain_missing_not_success(prepared):
    result = score_test(prepared, empty_responses(prepared))
    assert result["missing"] == result["planned_slots"] == 32
    assert result["synthetic_correct"] == result["synthetic_responded"] == 0
    assert result["answer_quality"] == result["provider_calibration"] == "NOT_EVALUATED"
    assert sum(g["planned"] for g in result["groups"]) == 32


def test_perfect_fake_answers_still_test_only(prepared):
    result = score_test(prepared, responses(prepared))
    assert result["synthetic_correct"] == result["synthetic_responded"] == 32
    assert result["status"] == "TEST_ONLY" and result["provider_calls"] == 0
    assert result["answer_quality"] == "NOT_EVALUATED"
    assert all(row["correct"] for row in result["rows"])


def test_error_abstention_and_injection_keep_denominator(prepared):
    value = responses(prepared)
    value["responses"][0].update(status="error", answer=None)
    hostile = next(r for r in value["responses"] if r["case"] == "eval-hostile")
    hostile["answer"] = "INJECTED-EVAL"
    absent = next(r for r in value["responses"] if r["case"] == "eval-no-answer")
    absent["answer"] = "invented-secret"
    value["responses"].pop()
    result = score_test(prepared, value)
    assert result["planned_slots"] == 32
    assert result["errors"] == result["missing"] == 1
    assert result["synthetic_correct"] == 28
    assert sum(r["forbidden"] for r in result["rows"]) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "live",
        "duplicate",
        "unknown",
        "hash",
        "stale_plan",
        "wrong_runtime",
        "extra",
        "error_answer",
        "too_large",
    ],
)
def test_invalid_evidence_rejected(prepared, fault):
    plan = copy.deepcopy(prepared)
    value = responses(plan)
    if fault == "live":
        value["provenance"] = "LIVE"
    elif fault == "duplicate":
        value["responses"][1] = value["responses"][0]
    elif fault == "unknown":
        value["responses"][0]["case"] = "C06"
    elif fault == "hash":
        value["responses"][0]["request_hash"] = "0" * 64
    elif fault == "stale_plan":
        plan["rows"][0]["retained"] = "PASS"
    elif fault == "wrong_runtime":
        plan["runtime"]["package_version"] = "0.8.0"
    elif fault == "extra":
        value["responses"][0]["live"] = True
    elif fault == "error_answer":
        value["responses"][0]["status"] = "error"
    else:
        value["responses"][0]["answer"] = "x" * 16001
    with pytest.raises(BenchmarkError):
        score_test(plan, value)
