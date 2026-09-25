"""Offline C09 preparation is separate from model-quality evidence."""

import copy
import json
import shutil
import socket
from datetime import datetime
from importlib import resources

import pytest

from context_engine.errors import BenchmarkError, RequiredContextTooLarge
from context_engine.evaluation import heldout


@pytest.fixture
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline preparation attempted networking")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_frozen_split_and_truth_coverage():
    cases, truth, protocol, manifest = heldout.load()
    assert len(cases) == len(truth) == 16
    assert len({case["id"] for case in cases}) == 16
    assert set(manifest["files"]) == set(heldout.FILES)
    for split in heldout.SPLITS:
        assert {c["category"] for c in cases if c["split"] == split} == set(heldout.CATEGORIES)
    assert protocol["approval"] == "owner_pending"


@pytest.mark.parametrize("filename", heldout.FILES)
def test_byte_drift_rejected_without_refreeze(tmp_path, filename):
    root = resources.files(heldout).joinpath("data")
    for name in (*heldout.FILES, "manifest.json"):
        shutil.copyfile(str(root.joinpath(name)), tmp_path / name)
    with (tmp_path / filename).open("a") as stream:
        stream.write(" ")
    with pytest.raises(BenchmarkError, match="freeze mismatch"):
        heldout.load(tmp_path)


@pytest.mark.parametrize(
    "bad", ["missing_truth", "duplicate", "split", "authority", "bound", "source", "live"]
)
def test_invalid_fixture_contracts_rejected(bad):
    cases, truth, protocol, _ = heldout.load()
    if bad == "missing_truth":
        truth.pop(cases[0]["id"])
    elif bad == "duplicate":
        cases[1]["id"] = cases[0]["id"]
    elif bad == "split":
        cases[0]["split"] = "evaluation"
    elif bad == "authority":
        cases[0]["messages"][0][0] = "system"
    elif bad == "bound":
        cases[0]["filler_turns"] = 1000000
    elif bad == "source":
        truth[cases[0]["id"]]["sources"] = ["missing"]
    else:
        protocol["status"] = "LIVE"
    with pytest.raises(BenchmarkError):
        heldout.validate(cases, truth, protocol)


def test_preparation_deterministic_complete_offline_and_exclusive(tmp_path, no_network):
    first = heldout.prepare()
    second = heldout.prepare()
    assert first == second
    assert first["planned_slots"] == len(first["rows"]) == 64
    assert sum(first["dispositions"].values()) == 64
    assert first["status"] == "TEST_ONLY" and first["provider_calls"] == 0
    assert first["answer_quality"] == first["provider_calibration"] == "NOT_EVALUATED"
    assert first["content_retention"] == "NOT_SCORED"
    keys = {(r["case"], r["variant"], r["budget"]) for r in first["rows"]}
    assert len(keys) == 64
    for row in first["rows"]:
        if row["status"] == "PREPARED":
            assert row["estimated_tokens"] <= row["budget"]
            assert row["structure"] == "PASS"
    destination = tmp_path / "new-report"
    heldout.export(first, destination)
    original = (destination / "report.json").read_bytes()
    assert json.loads(original) == first
    with pytest.raises(FileExistsError):
        heldout.export(second, destination)
    assert (destination / "report.json").read_bytes() == original


def test_ground_truth_is_not_passed_to_engine(monkeypatch, no_network):
    original_load = heldout.load
    original_assemble = heldout.assemble_context
    canary = "EVALUATOR_ONLY_NOT_SOURCE_DATA"
    observed = []

    def load_with_truth_canary(directory=None):
        cases, truth, protocol, manifest = original_load(directory)
        for value in truth.values():
            value["forbidden"].append(canary)
        return cases, truth, protocol, manifest

    def inspected(*args, **kwargs):
        assert canary not in repr((args, kwargs))
        observed.append(args[2].scope.session_id)
        return original_assemble(*args, **kwargs)

    monkeypatch.setattr(heldout, "load", load_with_truth_canary)
    monkeypatch.setattr(heldout, "assemble_context", inspected)
    result = heldout.prepare(split="development")
    assert len(observed) == result["planned_slots"] == 32
    assert all(row["split"] == "development" for row in result["rows"])
    assert canary not in json.dumps(result)


def test_engine_inputs_preserve_original_tool_and_long_history():
    cases, _, protocol, _ = heldout.load()
    at = datetime.fromisoformat(protocol["evaluated_at"])
    middle = next(c for c in cases if c["id"] == "eval-middle")
    history, pins, question = heldout.engine_inputs(middle, at)
    assert "9187" in history[0].messages[0].content
    assert history[0].messages[0].role.value == "tool"
    assert len(history[0].messages[0].content) > 8000
    assert pins.pins == () and question == middle["question"]
    long_case = next(c for c in cases if c["id"] == "eval-long")
    assert len(heldout.engine_inputs(long_case, at)[0]) == 81


def test_non_fit_preserved_and_unexpected_failure_not_swallowed(monkeypatch, no_network):
    def non_fit(*args, **kwargs):
        raise RequiredContextTooLarge("synthetic")

    monkeypatch.setattr(heldout, "assemble_context", non_fit)
    result = heldout.prepare(split="evaluation")
    assert result["dispositions"] == {"REQUIRED_NON_FIT": 32}
    assert result["planned_slots"] == 32
    assert all(r["estimated_tokens"] is None for r in result["rows"])

    def broken(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(heldout, "assemble_context", broken)
    with pytest.raises(RuntimeError, match="unexpected failure"):
        heldout.prepare(split="evaluation")


def test_invalid_split_and_live_export_rejected(tmp_path):
    with pytest.raises(BenchmarkError):
        heldout.prepare(split="live")
    fake = copy.deepcopy({"status": "LIVE", "provider_calls": 1})
    with pytest.raises(BenchmarkError):
        heldout.export(fake, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()
