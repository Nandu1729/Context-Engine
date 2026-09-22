"""External evidence resolves accounting only; immutable missing answer stays failed."""

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
    "c06_recovery_008",
    "c06_recovery_009",
):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
r = module


def baseline():
    return json.loads(r.BASELINE.read_text())


def sandbox(tmp_path, monkeypatch):
    b = baseline()
    ledger = r.RuntimeStore(tmp_path / "account.sqlite")
    original = r.timeout_entry(b)["receipt"]["ledger_rows"][0]
    with ledger.transaction() as db:
        db.execute(
            "INSERT INTO accounts VALUES(?,?,?)",
            (
                original["account"],
                json.dumps(r.base.POLICY),
                original["created"],
            ),
        )
        db.execute(
            f"INSERT INTO attempts({','.join(original)}) VALUES({','.join('?' for _ in original)})",
            tuple(original.values()),
        )
    journal = r.execution.RunJournal(
        tmp_path / "journal.sqlite",
        r.Manifest(json.dumps(b["manifest"])),
        b["profile"],
    )
    with journal.store.transaction() as db:
        for e in b["entries"]:
            db.execute(
                "INSERT INTO benchmark_probes VALUES(?,?,?,?,?)",
                (
                    e["probe_id"],
                    e["phase"],
                    json.dumps(e["record"]),
                    json.dumps(e["receipt"]) if e["receipt"] else None,
                    e["reserved_cost"],
                ),
            )
    monkeypatch.setattr(r.base, "LEDGER", ledger.path)
    monkeypatch.setattr(r.base, "JOURNAL", journal.store.path)
    monkeypatch.setattr(r, "verify", lambda: b)
    monkeypatch.setattr(r, "INTENT", tmp_path / "intent.json")
    monkeypatch.setattr(r, "RESULT", tmp_path / "result.json")
    return b, ledger, journal


def test_all_718_entries_preserved_and_only_seven_errors_reviewed():
    b = baseline()
    original = deepcopy(b)
    assert len(r.checked_records(b, b["entries"])) == 718
    assert b == original


@pytest.mark.parametrize("action", ["delete", "reset", "answer", "receipt"])
def test_timeout_cannot_be_rewritten(action):
    b = baseline()
    current = deepcopy(b["entries"])
    e = next(e for e in current if e["probe_id"] == r.PROBE)
    if action == "delete":
        current.remove(e)
    elif action == "reset":
        e["phase"] = "pending"
    elif action == "answer":
        e["record"]["state"] = "success"
    else:
        e["receipt"]["result"]["new_cost_microusd"] = 0
    with pytest.raises(ValueError):
        r.checked_records(b, current)


@pytest.mark.parametrize("state", ["error", "truncated", "filtered"])
def test_new_failures_not_waived(state):
    b = baseline()
    with pytest.raises(ValueError):
        r.checked_records(
            b,
            b["entries"]
            + [
                {
                    "probe_id": "new",
                    "phase": "done",
                    "record": {"state": state},
                }
            ],
        )


def test_real_reconciliation_is_one_shot_no_replay_no_journal_changes(tmp_path, monkeypatch):
    b, ledger, journal = sandbox(tmp_path, monkeypatch)
    before = journal.snapshot()
    with pytest.raises(ValueError):
        r.settled_cost(b)
    assert r.reconcile() == 0
    assert r.settled_cost(b) == 0
    assert journal.snapshot() == before
    with ledger.transaction() as db:
        row = dict(db.execute("SELECT * FROM attempts").fetchone())
        assert row["charged_tokens"] == 2547
        assert row["completion_hash"] is None
        assert row["state"] == "reconciled"
        assert json.loads(row["usage_json"])["cached_input_tokens"] is None
        assert db.execute("SELECT COUNT(*) FROM replay").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    with pytest.raises(ValueError):
        r.reconcile()


def test_readonly_inspection_prepares_next_only_in_memory(tmp_path, monkeypatch):
    _, _, journal = sandbox(tmp_path, monkeypatch)
    r.reconcile()
    before = journal.snapshot()
    state = r.inspect()
    assert state["next"] == ["openai/gpt-oss-20b", 3000, "A5", "queue"]
    assert state["remaining"] == 26
    assert state["status"] in ("ready", "wait")
    assert journal.snapshot() == before


def test_claim_uses_settlement_without_mutating_receipt_and_cannot_retry(tmp_path, monkeypatch):
    b, _, journal = sandbox(tmp_path, monkeypatch)
    r.reconcile()
    before = journal.snapshot()
    seen = {e["probe_id"] for e in before}
    slot = next(s for s in journal.manifest.slots if s["probe_id"] not in seen)
    journal.prepare(r._prepare_validated(r.load_bundle(), slot))
    assert r.claim(journal, r.PROBE, 0) == "already_claimed"
    assert r.claim(journal, slot["probe_id"], 1) == "run_budget"
    assert r.claim(journal, slot["probe_id"], 0) is None
    assert r.claim(journal, slot["probe_id"], 0) == "uncertain_dispatch"
    saved = {e["probe_id"]: e for e in journal.snapshot()}
    assert all(saved[e["probe_id"]] == e for e in before)
    assert saved[r.PROBE] == r.timeout_entry(b)


@pytest.mark.parametrize(
    "field,value",
    [
        ("charged_tokens", 0),
        ("cost", 1),
        ("request_count", 0),
        ("model", "other"),
        ("completion_hash", "fake"),
        ("state", "completed"),
        ("settled", None),
    ],
)
def test_settlement_drift_stops(tmp_path, monkeypatch, field, value):
    b, ledger, _ = sandbox(tmp_path, monkeypatch)
    r.reconcile()
    with ledger.transaction() as db:
        db.execute(f"UPDATE attempts SET {field}=? WHERE id=?", (value, r.ATTEMPT))
    with pytest.raises(ValueError):
        r.settled_cost(b)


def test_missing_audit_stops(tmp_path, monkeypatch):
    b, ledger, _ = sandbox(tmp_path, monkeypatch)
    r.reconcile()
    with ledger.transaction() as db:
        db.execute("DELETE FROM events")
    with pytest.raises(ValueError):
        r.settled_cost(b)


def test_new_uncertainty_blocks_after_reconciliation(tmp_path, monkeypatch):
    b, ledger, _ = sandbox(tmp_path, monkeypatch)
    r.reconcile()
    row = deepcopy(r.timeout_entry(b)["receipt"]["ledger_rows"][0])
    row.update(id="another", request_key="another", state="uncertain")
    with ledger.transaction() as db:
        db.execute(
            f"INSERT INTO attempts({','.join(row)}) VALUES({','.join('?' for _ in row)})",
            tuple(row.values()),
        )
    assert r.inspect()["reason"] == "uncertain_or_active_attempt"


def test_default_no_dispatch_and_runtime_patch_restored(monkeypatch):
    monkeypatch.setattr(r, "verify", lambda: None)
    monkeypatch.setattr(r, "inspect", lambda: {"status": "ready"})
    monkeypatch.setattr(r.previous, "dispatch", lambda _: pytest.fail("no dispatch"))
    old = r.execution.RunJournal.claim
    assert r.main([]) == 0
    assert r.execution.RunJournal.claim is old
    assert r.main(["--batch", "unused"]) == 1


def test_provenance_and_evidence_bound(tmp_path, monkeypatch):
    from context_engine.evaluation import protocol

    monkeypatch.setattr(protocol, "code_hash", lambda: r.case.cache.ARCHIVED_HASH)
    r.verify()
    plan = json.loads(r.PLAN.read_text())
    plan["evidence_sha256"] = "0" * 64
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(r, "PLAN", path)
    with pytest.raises(ValueError, match="provenance"):
        r.verify()
