import copy
import importlib.util
import json
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "policy_qualification", ROOT / "scripts/c09_policy_qualification.py"
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("Offline preparation attempted network access")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


def test_deterministic_complete_matrix_and_retention():
    plan = q.prepare(frozen=False)
    assert plan == q.prepare(frozen=False)
    assert plan["planned_slots"] == len(plan["rows"]) == 32
    assert plan["answer_quality"] == "NOT_EVALUATED" and plan["provider_calls"] == 0
    assert not plan["independently_reviewed"]
    assert all(
        r["all_records_retained"] and r["estimated_tokens"] <= r["budget"] for r in plan["rows"]
    )


def test_truth_or_unrecognized_fields_cannot_enter_input():
    case = json.loads((q.DIRECTORY / "cases.json").read_text())["cases"][0]
    altered = {**copy.deepcopy(case), "truth": "LEAK-MARKER", "system": "LEAK-MARKER"}
    for variant in ("BASELINE", "CANDIDATE"):
        before = q.assemble(case, 900, variant)
        after = q.assemble(altered, 900, variant)
        assert before.request == after.request
        assert "LEAK-MARKER" not in json.dumps(after.request.to_wire())


def test_both_policies_use_identical_schema_and_source_data():
    case = json.loads((q.DIRECTORY / "cases.json").read_text())["cases"][0]
    first, second = [q.assemble(case, 900, v) for v in ("BASELINE", "CANDIDATE")]
    a, b = [q.GENERATION.to_wire(r.request) for r in (first, second)]
    assert a["response_format"] == b["response_format"]
    assert a["messages"][0] != b["messages"][0]
    assert a["messages"][1:] == b["messages"][1:]
    assert q.fingerprint(a) != q.fingerprint(b)


def test_balanced_truth_and_order_controls():
    truth = json.loads((q.DIRECTORY / "truth.json").read_text())
    assert sum(v == "UNKNOWN" for v in truth.values()) == 4
    assert truth["p3-conflict"] == truth["p3-conflict-reversed"]
    assert truth["p3-update"] == truth["p3-update-reversed"] != "UNKNOWN"


def test_freeze_drift_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "DIRECTORY", tmp_path)
    (tmp_path / "manifest.json").write_text('{"id":"wrong"}')
    with pytest.raises(ValueError, match="Frozen"):
        q.prepare()


def test_no_overwrite(tmp_path):
    path = tmp_path / "saved.json"
    q.save(path, {"preserve": True})
    with pytest.raises(FileExistsError):
        q.save(path, {"preserve": False})
    assert json.loads(path.read_text()) == {"preserve": True}


@pytest.mark.parametrize(
    "budget,variant", [(True, "BASELINE"), (900, "unknown"), (50, "CANDIDATE")]
)
def test_unregistered_condition_rejected(budget, variant):
    with pytest.raises(ValueError):
        q.assemble({}, budget, variant)
