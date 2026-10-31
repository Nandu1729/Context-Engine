"""Offline development preflight never constitutes model-quality evidence."""

import importlib.util
import json
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from context_engine.errors import RequiredContextTooLarge
from context_engine.models import BlockKind

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("incident", ROOT / "scripts/incident_preflight.py")
incident = importlib.util.module_from_spec(spec)
spec.loader.exec_module(incident)


def test_complete_matrix_lifecycle_and_repeatability():
    first = incident.run_preflight()
    assert first == incident.run_preflight()
    assert first["status"] == "TEST_ONLY"
    assert first["answer_quality"] == "NOT_EVALUATED"
    assert not first["production_qualified"] and not first["independently_reviewed"]
    assert first["inference_calls"] == 0 and first["python_network_blocked"]
    assert first["preflight_passed"]
    assert first["planned_conditions"] == len(first["rows"]) == 32
    assert all(first["lifecycle_checks"].values())
    assert len(first["lifecycle_checks"]) == 10
    assert {(row["case"], row["input_cap"], row["recovery"]) for row in first["rows"]} == {
        (name, budget, recovery) for name, _, _ in incident.cases()
        for budget in (900, 3000) for recovery in (False, True)
    }
    exported = json.dumps(first)
    for _, question, records in incident.cases():
        assert question not in exported
        for _, content in records:
            assert content not in exported
    assert "RETIRED-IR-598" not in exported
    assert "PRIVATE-OTHER-IR-810" not in exported


def test_input_shape_has_no_truth_or_policy_candidate(monkeypatch):
    original = incident.assemble_context
    calls = []

    def checked(history, question, pins, budget, **kwargs):
        assert kwargs["system"] == incident.SYSTEM
        assert kwargs["options"].summarize is False
        assert len(history) in (1, 2, 3)
        calls.append((question, kwargs["retrieval_config"].recover_capped_window))
        return original(history, question, pins, budget, **kwargs)

    monkeypatch.setattr(incident, "assemble_context", checked)
    assert incident.run_preflight()["preflight_passed"]
    assert len(calls) == 32


def test_failed_rows_preserved_and_error_text_redacted(monkeypatch):
    def fail(*args, **kwargs):
        raise RequiredContextTooLarge("PRIVATE_PAYLOAD")

    monkeypatch.setattr(incident, "assemble_context", fail)
    report = incident.run_preflight()
    assert not report["preflight_passed"]
    assert report["planned_conditions"] == len(report["rows"]) == 32
    assert all(row["status"] == "ERROR" for row in report["rows"])
    assert "PRIVATE_PAYLOAD" not in json.dumps(report)


def test_inconsistent_blocks_cannot_pass(monkeypatch):
    original = incident.assemble_context

    def drop_evidence(*args, **kwargs):
        result = original(*args, **kwargs)
        return replace(result, blocks=tuple(
            replace(block, content="[]") if block.kind in (BlockKind.WINDOW, BlockKind.RETRIEVED)
            else block for block in result.blocks
        ))

    monkeypatch.setattr(incident, "assemble_context", drop_evidence)
    report = incident.run_preflight()
    assert not report["preflight_passed"]
    assert all(not row["checks"]["evidence_blocks_match_wire"] for row in report["rows"])


@pytest.mark.parametrize("duplicate_only", [False, True])
def test_missing_wire_evidence_fails_even_with_complete_blocks(monkeypatch, duplicate_only):
    original = incident.assemble_context

    def drop_evidence(*args, **kwargs):
        result = original(*args, **kwargs)
        messages = []
        for message in result.request.messages:
            if message.content.startswith("[WINDOW DATA]\n"):
                turns = json.loads(message.content.split("\n", 1)[1])
                if not duplicate_only or len(turns) == 3:
                    message = replace(message, content="[WINDOW DATA]\n" + json.dumps(turns[1:]))
            messages.append(message)
        return replace(result, request=replace(result.request, messages=tuple(messages)))

    monkeypatch.setattr(incident, "assemble_context", drop_evidence)
    report = incident.run_preflight()
    assert not report["preflight_passed"]
    rows = [r for r in report["rows"] if not duplicate_only or r["case"] == "duplicate-conflict"]
    assert all(not row["checks"]["all_records_retained"] for row in rows)


def test_lifecycle_failure_cannot_pass(monkeypatch):
    monkeypatch.setattr(
        incident, "deletion_checks", lambda counter: {"deleted_content_absent": False}
    )
    assert not incident.run_preflight()["preflight_passed"]


def test_unexpected_failure_propagates(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(incident, "assemble_context", fail)
    with pytest.raises(RuntimeError, match="unexpected"):
        incident.run_preflight()


def test_network_guard_and_restoration():
    original = socket.create_connection
    with incident.offline_network():
        with pytest.raises(RuntimeError, match="Network disabled"):
            socket.create_connection(("example.invalid", 443))
        with pytest.raises(RuntimeError, match="Network disabled"):
            socket.getaddrinfo("example.invalid", 443)
        with socket.socket() as client:
            with pytest.raises(RuntimeError, match="Network disabled"):
                client.connect(("127.0.0.1", 1))
            with pytest.raises(RuntimeError, match="Network disabled"):
                client.connect_ex(("127.0.0.1", 1))
    assert socket.create_connection is original


def test_cli_refuses_existing_output_before_work(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(incident, "run_preflight", lambda: pytest.fail("must not run"))
    with pytest.raises(SystemExit):
        incident.main(["--output", str(output)])
    assert output.read_text(encoding="utf-8") == "preserve"


def test_cli_exclusive_create_closes_overwrite_race(tmp_path, monkeypatch):
    output = tmp_path / "report.json"

    def raced():
        output.write_text("another writer", encoding="utf-8")
        return {}

    monkeypatch.setattr(incident, "run_preflight", raced)
    with pytest.raises(FileExistsError):
        incident.main(["--output", str(output)])
    assert output.read_text(encoding="utf-8") == "another writer"


@pytest.mark.parametrize("passed,exit_code", [(True, 0), (False, 1)])
def test_cli_exit_and_saved_report(tmp_path, monkeypatch, passed, exit_code):
    report = {"status": "TEST_ONLY", "preflight_passed": passed, "planned_conditions": 32,
              "inference_calls": 0, "answer_quality": "NOT_EVALUATED"}
    monkeypatch.setattr(incident, "run_preflight", lambda: report)
    output = tmp_path / "new" / "report.json"
    assert incident.main(["--output", str(output)]) == exit_code
    assert json.loads(output.read_text(encoding="utf-8")) == report
