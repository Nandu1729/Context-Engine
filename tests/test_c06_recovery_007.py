"""Offline guards for exact five-rejection continuation, no replay or waiver."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in (
    "c06_complete",
    "c06_cached_quota",
    "c06_recovery",
    "c06_recovery_003",
    "c06_recovery_004",
    "c06_recovery_005",
    "c06_recovery_006",
    "c06_recovery_007",
):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
r = module


def baseline():
    return json.loads((SCRIPTS.parent / "output/c06-live-batch-178.json").read_text())


def test_five_exact_errors_and_all_673_records_preserved():
    b = baseline()
    before = deepcopy(b)
    assert len(r.checked_records(b, b["entries"])) == 673
    assert b == before
    assert len(r.case.reviewed.REVIEWED) == 2


@pytest.mark.parametrize("state", ["error", "truncated", "filtered"])
def test_any_new_failure_still_stops(state):
    b = baseline()
    with pytest.raises(ValueError):
        r.checked_records(
            b, b["entries"] + [{"probe_id": "new", "phase": "done", "record": {"state": state}}]
        )


@pytest.mark.parametrize("action", ["delete", "rewrite", "reset"])
def test_historical_result_cannot_change(action):
    b = baseline()
    current = deepcopy(b["entries"])
    entry = next(e for e in current if e["probe_id"] in r.REVIEWED)
    if action == "delete":
        current.remove(entry)
    elif action == "rewrite":
        entry["record"]["state"] = "success"
    else:
        entry["phase"] = "pending"
    with pytest.raises(ValueError):
        r.checked_records(b, current)


def test_uncertain_receipt_cannot_be_reviewed():
    b = baseline()
    entry = next(e for e in b["entries"] if e["probe_id"] in r.REVIEWED)
    entry["receipt"]["ledger_rows"][0]["state"] = "uncertain"
    with pytest.raises(ValueError):
        r.checked_records(b, deepcopy(b["entries"]))


def test_default_readonly_and_admission_provenance_unchanged(monkeypatch):
    monkeypatch.setattr(r, "verify", lambda: None)
    monkeypatch.setattr(r.previous, "inspect", lambda: {"status": "ready", "reviewed_errors": 1})
    monkeypatch.setattr(r.previous, "dispatch", lambda _: pytest.fail("must not dispatch"))
    old_file, old_plan = r.previous.__file__, r.previous.PLAN
    admission_plan = r.case.PLAN
    assert r.main([]) == 0
    assert (r.previous.__file__, r.previous.PLAN) == (old_file, old_plan)
    assert r.case.PLAN == admission_plan


def test_hidden_batch_requires_live_optin(monkeypatch):
    monkeypatch.setattr(r.previous, "batch", lambda _: pytest.fail("must not dispatch"))
    assert r.main(["--batch", "unused"]) == 1


def test_provenance_and_status_evidence_bound(monkeypatch, tmp_path):
    from context_engine.evaluation import protocol

    # Workspace tests run 0.8.0; real archived-runtime preflight is separate.
    monkeypatch.setattr(protocol, "code_hash", lambda: r.case.cache.ARCHIVED_HASH)
    r.verify()
    plan = json.loads(r.PLAN.read_text())
    plan["status_sha256"] = "0" * 64
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(r, "PLAN", path)
    with pytest.raises(ValueError, match="provenance"):
        r.verify()
