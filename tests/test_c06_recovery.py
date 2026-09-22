"""Offline safeguards for continuing only untouched cases after reviewed failure."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in ("c06_complete", "c06_cached_quota", "c06_recovery"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
r = module


def fixture():
    error = {
        "probe_id": r.REVIEWED,
        "phase": "done",
        "record": {"state": "error"},
        "receipt": {
            "ledger_rows": [
                {
                    "id": r.ATTEMPT,
                    "state": "rejected",
                    "reason": "provider_rejected",
                    "charged_tokens": 0,
                    "cost": 0,
                }
            ]
        },
    }
    good = {"probe_id": "prior", "phase": "done", "record": {"state": "success"}}
    return {"entries": [good, error]}


def test_reviewed_failure_remains_unchanged_and_counted():
    baseline = fixture()
    current = deepcopy(baseline["entries"])
    current.append({"probe_id": "new", "phase": "done", "record": {"state": "success"}})
    before = deepcopy(current)
    done = r.checked_records(baseline, current)
    assert len(done) == 3 and done[r.REVIEWED]["record"]["state"] == "error"
    assert current == before


@pytest.mark.parametrize("state", ["error", "truncated", "filtered", "tool_calls"])
def test_every_new_failure_stops(state):
    baseline = fixture()
    current = deepcopy(baseline["entries"])
    current.append({"probe_id": "new", "phase": "done", "record": {"state": state}})
    with pytest.raises(ValueError):
        r.checked_records(baseline, current)


@pytest.mark.parametrize("change", ["delete", "rewrite", "reset"])
def test_no_historical_rewrite_or_retry(change):
    baseline = fixture()
    current = deepcopy(baseline["entries"])
    if change == "delete":
        current.pop()
    elif change == "rewrite":
        current[-1]["record"]["state"] = "success"
    else:
        current[-1]["phase"] = "pending"
    with pytest.raises(ValueError):
        r.checked_records(baseline, current)


@pytest.mark.parametrize(
    "key,value", [("state", "uncertain"), ("cost", None), ("reason", "rate_limit")]
)
def test_only_confirmed_reviewed_receipt_is_allowed(key, value):
    baseline = fixture()
    baseline["entries"][-1]["receipt"]["ledger_rows"][0][key] = value
    with pytest.raises(ValueError):
        r.checked_records(baseline, deepcopy(baseline["entries"]))


def test_one_case_changes_only_batch_size():
    args = ["benchmark-run", "--max-calls", "744", "--mode", "live"]
    assert r.one_case(args) == ["benchmark-run", "--max-calls", "1", "--mode", "live"]
    assert args[2] == "744"
    with pytest.raises(ValueError):
        r.one_case(["--max-calls", "1000"])


def test_exclusive_metadata_never_overwrites(tmp_path):
    path = tmp_path / "proof.json"
    r.exclusive_json(path, {"status": 400})
    assert json.loads(path.read_text()) == {"status": 400}
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        r.exclusive_json(path, {"status": 200})
    assert json.loads(path.read_text())["status"] == 400


def test_hidden_batch_requires_optin(monkeypatch):
    monkeypatch.setattr(r, "batch", lambda _: pytest.fail("must not dispatch"))
    assert r.main(["--batch", "unused.json"]) == 1


def test_default_only_calls_readonly_status(monkeypatch):
    monkeypatch.setattr(r, "verify", lambda: None)
    monkeypatch.setattr(r, "inspect", lambda: {"status": "ready"})
    monkeypatch.setattr(r, "dispatch", lambda _: pytest.fail("must not dispatch"))
    assert r.main([]) == 0


def test_source_drift_blocks(monkeypatch, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"source_sha256": "wrong"}))
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}")
    monkeypatch.setattr(r, "PLAN", plan)
    monkeypatch.setattr(r, "BASELINE", baseline)
    monkeypatch.setattr(r.cache, "verify_amendment", lambda: None)
    with pytest.raises(ValueError):
        r.verify()
