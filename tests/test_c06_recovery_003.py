"""Offline exact-baseline guards for reviewed continuation003."""

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in ("c06_complete", "c06_cached_quota", "c06_recovery", "c06_recovery_003"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
r = module


def baseline():
    return {
        "entries": [
            {
                "probe_id": key,
                "phase": "done",
                "record": {"state": "error"},
                "receipt": {
                    "ledger_rows": [
                        {
                            "id": attempt,
                            "state": "rejected",
                            "reason": "provider_rejected",
                            "charged_tokens": 0,
                            "cost": 0,
                        }
                    ]
                },
            }
            for key, attempt in r.REVIEWED.items()
        ]
    }


def test_both_errors_preserved_without_mutation():
    b = baseline()
    current = deepcopy(b["entries"])
    current.append({"probe_id": "new", "phase": "done", "record": {"state": "success"}})
    before = deepcopy(current)
    assert len(r.checked_records(b, current)) == 3
    assert current == before


@pytest.mark.parametrize("state", ["error", "truncated", "filtered"])
def test_any_new_failure_stops(state):
    b = baseline()
    with pytest.raises(ValueError):
        r.checked_records(
            b, b["entries"] + [{"probe_id": "new", "phase": "done", "record": {"state": state}}]
        )


@pytest.mark.parametrize("action", ["delete", "rewrite", "reset"])
def test_old_results_cannot_be_replaced(action):
    b = baseline()
    current = deepcopy(b["entries"])
    if action == "delete":
        current.pop()
    elif action == "rewrite":
        current[0]["record"]["state"] = "success"
    else:
        current[0]["phase"] = "pending"
    with pytest.raises(ValueError):
        r.checked_records(b, current)


def test_uncertain_receipt_cannot_be_reviewed_as_rejected():
    b = baseline()
    b["entries"][0]["receipt"]["ledger_rows"][0]["state"] = "uncertain"
    with pytest.raises(ValueError):
        r.checked_records(b, deepcopy(b["entries"]))


def test_default_readonly_and_patches_restored(monkeypatch):
    monkeypatch.setattr(r, "verify", lambda: None)
    monkeypatch.setattr(r.previous, "inspect", lambda: {"status": "ready", "reviewed_errors": 1})
    monkeypatch.setattr(r.previous, "dispatch", lambda _: pytest.fail("must not dispatch"))
    old_file = r.previous.__file__
    old_plan = r.previous.PLAN
    assert r.main([]) == 0
    assert r.previous.__file__ == old_file and r.previous.PLAN == old_plan


def test_hidden_batch_requires_optin(monkeypatch):
    monkeypatch.setattr(r.previous, "batch", lambda _: pytest.fail("must not dispatch"))
    assert r.main(["--batch", "unused"]) == 1
