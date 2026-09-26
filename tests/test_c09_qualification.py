"""Offline candidate integration and evidence-boundary tests, not quality results."""

import copy
import hashlib
import importlib.util
import json
import shutil
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.answers import AnswerContract
from context_engine.errors import BenchmarkError
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "qualification", ROOT / "scripts/c09_qualification.py"
)
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)


@pytest.fixture(scope="module", autouse=True)
def candidate_runtime(candidate_harness):
    candidate_harness(qualification)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Offline qualification must not access network")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture(scope="module")
def plan():
    return qualification.prepare()


def recording(plan, *, populated=False):
    _, truth, _ = qualification.load()
    return {
        "provenance": "TEST_ONLY",
        "preparation_hash": qualification.fingerprint(plan),
        "responses": [
            {
                **{k: row[k] for k in ("case", "budget", "variant", "request_hash")},
                "status": "response",
                "answer": json.dumps({"answer": truth[row["case"]]["answer"]}),
            }
            for row in plan["rows"]
            if populated and row["status"] == "PREPARED"
        ],
    }


def test_replay_and_all_denominators(plan):
    assert qualification.prepare() == plan
    assert plan["planned_slots"] == len(plan["rows"]) == 32
    assert plan["provider_calls"] == 0
    assert plan["answer_quality"] == "NOT_EVALUATED"
    report = qualification.score_test(plan, recording(plan))
    assert all(g["planned"] == 8 and g["missing"] == 8 for g in report["groups"])
    assert report["answer_quality"] == "NOT_EVALUATED"


def test_perfect_fake_answers_never_become_live_evidence(plan):
    report = qualification.score_test(plan, recording(plan, populated=True))
    assert all(g["correct"] == g["conforming"] == 8 for g in report["groups"])
    assert all(g["correct_abstention"] == 2 for g in report["groups"])
    assert report["status"] == "TEST_ONLY"
    assert report["answer_quality"] == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "defect",
    [
        "live",
        "plan_hash",
        "request_hash",
        "duplicate",
        "unknown",
        "bool_budget",
        "extra",
        "error_body",
        "oversize",
        "status",
    ],
)
def test_invalid_recordings_fail_closed(plan, defect):
    data = recording(plan, populated=True)
    row = data["responses"][0]
    if defect == "live":
        data["provenance"] = "LIVE"
    elif defect == "plan_hash":
        data["preparation_hash"] = "wrong"
    elif defect == "request_hash":
        row["request_hash"] = "wrong"
    elif defect == "duplicate":
        data["responses"] = [row, copy.deepcopy(row)]
    elif defect == "unknown":
        row["case"] = "not-planned"
    elif defect == "bool_budget":
        row["budget"] = True
    elif defect == "extra":
        row["new_field"] = 1
    elif defect == "error_body":
        row["status"] = "error"
    elif defect == "oversize":
        row["answer"] = "a" * 16385
    else:
        row["status"] = "success"
    with pytest.raises(BenchmarkError):
        qualification.score_test(plan, data)


def test_modified_preparation_rejected(plan):
    changed = copy.deepcopy(plan)
    changed["rows"][0]["retained"] = "forged"
    with pytest.raises(BenchmarkError):
        qualification.score_test(changed, recording(changed))


@pytest.mark.parametrize(
    "body,conforming",
    [
        ('{"answer":"east-birch-7"} explanation', False),
        ('{"answer":"east-birch-7","answer":"east-birch-7"}', False),
        ('{"answer":"east‑birch‑7"}', False),
        ('{"answer":"EAST-BIRCH-7"}', True),
        ('{"answer":"UNKNOWN"}', True),
    ],
)
def test_no_prose_unicode_or_case_repair(plan, body, conforming):
    data = recording(plan, populated=True)
    data["responses"][0]["answer"] = body
    row = qualification.score_test(plan, data)["rows"][0]
    assert row["correct"] is False
    assert row["conforming"] is conforming
    assert row["wrong_abstention"] == (body == '{"answer":"UNKNOWN"}')


def test_missing_errors_and_attack_are_not_removed(plan):
    data = recording(plan, populated=True)
    data["responses"][0].update(status="error", answer=None)
    data["responses"].pop(1)
    hostile = next(row for row in data["responses"] if row["case"] == "q2-hostile")
    hostile["answer"] = "malformed HACKED_Q2 prose"
    report = qualification.score_test(plan, data)
    assert sum(g["planned"] for g in report["groups"]) == 32
    assert sum(g["error"] for g in report["groups"]) == 1
    assert sum(g["missing"] for g in report["groups"]) == 1
    assert sum(g["forbidden"] for g in report["groups"]) == 1


@pytest.mark.parametrize("target", [*qualification.FILES, "runtime", "missing"])
def test_freeze_drift_rejected(tmp_path, monkeypatch, target):
    for name in (*qualification.FILES, "experiments/c09-qualification-002/manifest.json"):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    # Start from the valid candidate manifest so each mutation is the cause of rejection.
    shutil.copy2(
        qualification.DIRECTORY / "manifest.json",
        tmp_path / "experiments/c09-qualification-002/manifest.json",
    )
    monkeypatch.setattr(qualification, "ROOT", tmp_path)
    monkeypatch.setattr(qualification, "DIRECTORY", tmp_path / "experiments/c09-qualification-002")
    if target == "runtime":
        monkeypatch.setattr(qualification, "runtime_identity", lambda: {})
    elif target == "missing":
        (tmp_path / qualification.FILES[2]).unlink()
    else:
        path = tmp_path / target
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(BenchmarkError):
        qualification.load()


def test_contract_budgeted_and_truth_not_injected(monkeypatch):
    scenarios, _, _ = qualification.load()
    case = dict(scenarios[0], expected_answer="SECRET_TRUTH_ONLY")
    original = qualification.engine_inputs

    def inspected(scenario, at):
        assert set(scenario) == {"id", "question", "messages", "middle_padding", "filler_turns"}
        assert "SECRET_TRUTH_ONLY" not in json.dumps(scenario)
        return original(scenario, at)

    monkeypatch.setattr(qualification, "engine_inputs", inspected)
    result = qualification.assemble(case, 900, "PRIMARY", TiktokenCounter())
    assert (
        result.messages[0]["content"]
        == qualification.POLICY + AnswerContract(case["kind"]).instructions()
    )
    assert "SECRET_TRUTH_ONLY" not in json.dumps(result.request.to_wire())
    assert result.diagnostics.estimate.estimated_tokens <= 900


def test_nonfit_kept_in_denominator(monkeypatch):
    from context_engine.errors import RequiredContextTooLarge

    def nonfit(*args, **kwargs):
        raise RequiredContextTooLarge("synthetic required overflow")

    monkeypatch.setattr(qualification, "assemble", nonfit)
    plan = qualification.prepare()
    report = qualification.score_test(plan, recording(plan))
    assert len(report["rows"]) == 32
    assert all(g["required_non_fit"] == 8 for g in report["groups"])
    assert sum(g["correct"] for g in report["groups"]) == 0


def test_empty_optional_blocks_are_absent_evidence():
    scenarios, truth, _ = qualification.load()
    result = SimpleNamespace(
        blocks=[SimpleNamespace(content="", kind=SimpleNamespace(value="retrieved"))]
    )
    assert qualification.retained(scenarios[0], truth[scenarios[0]["id"]], result) is False


def test_candidate_payloads_match_baseline_but_runtime_identity_differs(plan):
    saved = json.loads((ROOT / "output/c09-qualification-002/preparation.json").read_text())
    assert saved["manifest_hash"] != plan["manifest_hash"]
    # Exact historical full-plan reproduction is checked under the archived wheel.
    assert {k: v for k, v in saved.items() if k != "manifest_hash"} == {
        k: v for k, v in plan.items() if k != "manifest_hash"
    }


def test_preflight_revision_preserved():
    archive = ROOT / "archives/c09-qualification-002-preflight"
    manifest = json.loads((archive / "manifest.json").read_text())
    assert manifest["id"] == "c09-qualification-002"
    assert (
        hashlib.sha256((archive / "c09_qualification.py").read_bytes()).hexdigest()
        == manifest["files"]["scripts/c09_qualification.py"]
    )
    for name in qualification.FILES[1:]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == manifest["files"][name]
