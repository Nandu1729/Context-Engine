#!/usr/bin/env python3
"""Evidence-backed accounting recovery; never recover or retry the lost answer.

External amendment009 preserves all snapshot223 receipts and frozen package files.
Only the exact reconciled timeout's run-cost admission uses external evidence.
Default read-only; explicit --reconcile settles once; --allow-live runs untouched cases.
"""

import fcntl
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import c06_recovery_008 as history

from context_engine.evaluation import execution
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.harness import _prepare_validated
from context_engine.evaluation.protocol import Manifest
from context_engine.providers.contracts import PriceCard, Usage
from context_engine.providers.store import ACTIVE, RuntimeStore

case = history.case
previous = case.previous
base = case.base
ROOT = case.ROOT
PLAN = ROOT / "output/c06-recovery-amendment-009.json"
BASELINE = ROOT / "output/c06-live-batch-223.json"
EVIDENCE = ROOT / "output/c06-reconciliation-evidence-009.json"
INTENT = ROOT / "output/c06-reconciliation-009.intent.json"
RESULT = ROOT / "output/c06-reconciliation-009.json"
PROBE = "8435cffb799f9a0f76f33b1ad5a96b14d5f946d0a5684292a8be9b75afb6e2c2"
ATTEMPT = "e3a669a8071b43f790729bed841e3b37"
USAGE = Usage(2513, 34)


def timeout_entry(baseline):
    return next(e for e in baseline["entries"] if e["probe_id"] == PROBE)


def checked_records(baseline, current):
    old = {e["probe_id"]: e for e in baseline["entries"] if e["phase"] == "done"}
    done = {e["probe_id"]: e for e in current if e["phase"] == "done"}
    if any(done.get(k) != v for k, v in old.items()):
        raise ValueError("Historical entry changed")
    exact = timeout_entry(baseline)
    receipt = exact["receipt"]
    if (
        exact["phase"] != "done"
        or exact["record"]["state"] != "error"
        or receipt["result"]["error_code"] != "timeout"
        or receipt["result"]["new_cost_microusd"] is not None
        or receipt["result"]["completion"] is not None
        or len(receipt["ledger_rows"]) != 1
        or receipt["ledger_rows"][0]["id"] != ATTEMPT
        or receipt["ledger_rows"][0]["state"] != "uncertain"
    ):
        raise ValueError("Original timeout evidence changed")
    # Review the six confirmed rejections with their original strict guard.
    filtered = [e for e in current if e["probe_id"] != PROBE]
    old_filtered = {
        **baseline,
        "entries": [e for e in baseline["entries"] if e["probe_id"] != PROBE],
    }
    history.checked_records(old_filtered, filtered)
    return done


def verify():
    history.verify()
    plan = json.loads(PLAN.read_text())
    expected = {
        "source_sha256": previous.digest(__file__),
        "baseline_sha256": previous.digest(BASELINE),
        "evidence_sha256": previous.digest(EVIDENCE),
        "previous_plan_sha256": previous.digest(history.PLAN),
        "previous_source_sha256": previous.digest(ROOT / "scripts/c06_recovery_008.py"),
        "admission_plan_sha256": previous.digest(case.PLAN),
        "admission_source_sha256": previous.digest(ROOT / "scripts/c06_recovery_004.py"),
        "execution_id": base.EXECUTION,
        "probe_id": PROBE,
        "attempt_id": ATTEMPT,
        "usage": asdict(USAGE),
    }
    if any(plan.get(k) != v for k, v in expected.items()):
        raise ValueError("Recovery009 provenance changed")
    evidence = json.loads(EVIDENCE.read_text())
    if (
        evidence["attempt_id"] != ATTEMPT
        or evidence["probe_id"] != PROBE
        or evidence["usage"] != asdict(USAGE)
        or evidence["http_status"] != 200
        or evidence["request_local_time"] != "2026-09-22T02:11:49+05:30"
        or evidence["model"] != "openai/gpt-oss-20b"
    ):
        raise ValueError("Provider evidence changed")
    for filename, digest in evidence["image_sha256"].items():
        if (
            previous.digest(ROOT / "output/private/c06-reconciliation-009-evidence" / filename)
            != digest
        ):
            raise ValueError("Evidence image changed")
    baseline = json.loads(BASELINE.read_text())
    if baseline["execution_id"] != base.EXECUTION:
        raise ValueError("Baseline identity changed")
    checked_records(baseline, baseline["entries"])
    return baseline


def current_records(con):
    return [
        {
            "probe_id": row["id"],
            "phase": row["phase"],
            "record": json.loads(row["record"]),
            "receipt": json.loads(row["receipt"]) if row["receipt"] else None,
            "reserved_cost": row["reserved_cost"],
        }
        for row in con.execute("SELECT * FROM benchmark_probes")
    ]


def evidence_ref():
    return "sha256:" + previous.digest(EVIDENCE)


def validate_settlement(original, row, events):
    mutable = {"state", "settled", "charged_tokens", "cost", "usage_json", "reason"}
    if any(row.get(k) != v for k, v in original.items() if k not in mutable):
        raise ValueError("Attempt identity changed")
    if (
        row["state"] != "reconciled"
        or row["charged_tokens"] != USAGE.total_tokens
        or row["cost"] != 0
        or row["settled"] is None
        or row["settled"] < row["created"]
        or json.loads(row["usage_json"]) != asdict(USAGE)
        or row["reason"] != "external_reconciliation"
        or PriceCard(**json.loads(row["price_json"])).observed_cost(USAGE) != 0
    ):
        raise ValueError("Reconciliation accounting changed")
    if len(events) != 1 or any(
        events[0].get(k) != v
        for k, v in {
            "kind": "reconciliation",
            "source_attempt": ATTEMPT,
            "evidence_ref": evidence_ref(),
            "account": original["account"],
            "request_key": original["request_key"],
            "new_cost": 0,
        }.items()
    ):
        raise ValueError("Reconciliation audit changed")
    return row["cost"]


def settled_cost(baseline):
    original = timeout_entry(baseline)["receipt"]["ledger_rows"][0]
    with base.readonly(base.LEDGER) as con:
        row = con.execute("SELECT * FROM attempts WHERE id=?", (ATTEMPT,)).fetchone()
        events = [
            dict(e)
            for e in con.execute(
                "SELECT * FROM events WHERE kind='reconciliation' AND source_attempt=?", (ATTEMPT,)
            )
        ]
        if con.execute("SELECT 1 FROM replay WHERE source_attempt=?", (ATTEMPT,)).fetchone():
            raise ValueError("Lost answer must not become replay")
    if row is None:
        raise ValueError("Attempt missing")
    return validate_settlement(original, dict(row), events)


def inspect():
    baseline = verify()
    settled_cost(baseline)
    state = case.cache.ORIGINAL_INSPECT()  # policy/clock and dispatch checks
    if state.get("reason") != "terminal_error_or_truncation":
        return state
    with base.readonly(base.JOURNAL) as con:
        entries = current_records(con)
        identity = json.loads(con.execute("SELECT payload FROM benchmark_identity").fetchone()[0])
    if identity["profile"] != baseline["profile"] or identity["manifest"] != baseline["manifest"]:
        raise ValueError("Execution identity changed")
    done = checked_records(baseline, entries)
    info = {"terminal": len(done), "remaining": 744 - len(done), "reviewed_errors": 7}
    pending = [e for e in entries if e["phase"] != "done"]
    if len(pending) > 1 or any(e["phase"] != "pending" for e in pending):
        raise ValueError("Unexpected dispatch state")
    if len(done) == 744:
        row = None
        reservation = 1
    else:
        slot = next(
            s for s in Manifest(json.dumps(baseline["manifest"])).slots if s["probe_id"] not in done
        )
        if pending and pending[0]["probe_id"] != slot["probe_id"]:
            raise ValueError("Unexpected pending case")
        row = pending[0]["record"] if pending else _prepare_validated(load_bundle(), slot)
        reservation = (
            row["estimate"]["estimated_tokens"]
            + baseline["manifest"]["protocol"]["generation"]["max_completion_tokens"]
        )
    with base.readonly(base.LEDGER) as con:
        account = con.execute("SELECT last_clock FROM accounts").fetchone()[0]
        attempts = [dict(r) for r in con.execute("SELECT * FROM attempts")]
    paced = case.cache.pacing(attempts, reservation, max(time.time(), account))
    if row is None:
        if any(r["state"] in ACTIVE or r["cost"] is None for r in attempts):
            raise ValueError("Unresolved usage at completion")
        return {**info, "status": "complete"}
    return {**info, "next": [row["model"], row["budget"], row["variant"], row["fact_id"]], **paced}


def claim(journal, identifier, reserved_cost):
    baseline = verify()
    cost_override = settled_cost(baseline)
    if journal.execution_id != base.EXECUTION or journal.profile != baseline["profile"]:
        raise ValueError("Claim scope changed")
    with journal.store.transaction() as db:
        entries = current_records(db)
        if any(e["phase"] == "dispatching" for e in entries):
            return "uncertain_dispatch"
        checked_records(baseline, entries)
        charged = 0
        for entry in entries:
            receipt = entry["receipt"]
            cost = receipt["result"]["new_cost_microusd"] if receipt else 0
            if cost is None:
                if entry["probe_id"] != PROBE or entry != timeout_entry(baseline):
                    return "uncertain_usage"
                cost = cost_override
            charged += cost
        if type(reserved_cost) is not int or reserved_cost < 0:
            raise ValueError("Invalid reservation")
        if charged + reserved_cost > journal.profile["max_run_cost_microusd"]:
            return "run_budget"
        if (
            db.execute(
                "UPDATE benchmark_probes SET phase='dispatching',reserved_cost=? "
                "WHERE id=? AND phase='pending'",
                (reserved_cost, identifier),
            ).rowcount
            != 1
        ):
            return "already_claimed"
    return None


def reconcile():
    baseline = verify()
    original = timeout_entry(baseline)["receipt"]["ledger_rows"][0]
    with base.readonly(base.JOURNAL) as con:
        entries = current_records(con)
    checked_records(baseline, entries)
    if any(e["phase"] != "done" for e in entries) or len(entries) != 718:
        raise ValueError("Reconcile only at exact stopped baseline")
    with base.readonly(base.LEDGER) as con:
        row = con.execute("SELECT * FROM attempts WHERE id=?", (ATTEMPT,)).fetchone()
        active = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM attempts WHERE state IN ('reserved','inflight','uncertain')"
            )
        ]
        accounts = list(con.execute("SELECT * FROM accounts"))
        if len(accounts) != 1 or json.loads(accounts[0]["policy"]) != base.POLICY:
            raise ValueError("Policy changed")
    if row is None or dict(row) != original or active != [original]:
        raise ValueError("Reconciliation is one-shot at exact uncertain attempt")
    previous.exclusive_json(
        INTENT,
        {
            "attempt_id": ATTEMPT,
            "probe_id": PROBE,
            "execution_id": base.EXECUTION,
            "amendment_sha256": previous.digest(PLAN),
            "evidence_ref": evidence_ref(),
            "original_row": original,
            "usage": asdict(USAGE),
            "created": time.time(),
        },
    )
    RuntimeStore(base.LEDGER).resolve_uncertain(
        ATTEMPT,
        evidence_ref=evidence_ref(),
        now=time.time(),
        usage=USAGE,
    )
    settled_cost(baseline)
    previous.exclusive_json(
        RESULT,
        {
            "attempt_id": ATTEMPT,
            "evidence_ref": evidence_ref(),
            "usage": asdict(USAGE),
            "configured_cost_microusd": 0,
            "benchmark_answer_recovered": False,
            "journal_receipt_changed": False,
            "amendment_sha256": previous.digest(PLAN),
        },
    )
    base.emit({"status": "reconciled", "tokens": USAGE.total_tokens, "answer_recovered": False})
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--reconcile"]:
        try:
            fd = os.open(
                ROOT / "output/private/c06-completion.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return reconcile()
        except Exception:
            base.emit({"status": "stop", "reason": "reconciliation_review_required"})
            return 1
    original_dispatch, original_emit = previous.dispatch, base.emit

    def dispatch(snapshot):
        before = inspect()
        result = original_dispatch(snapshot)
        case.check_progress(before, inspect())
        return result

    def emit(value):
        if value.get("recovery") == "reviewed-002":
            value = {**value, "recovery": "reconciled-009"}
        original_emit(value)

    with (
        patch.object(previous, "verify", verify),
        patch.object(previous, "checked_records", checked_records),
        patch.object(previous, "inspect", inspect),
        patch.object(previous, "dispatch", dispatch),
        patch.object(previous, "PLAN", PLAN),
        patch.object(previous, "__file__", str(Path(__file__).resolve())),
        patch.object(case.cache, "CachedQuotaStore", case.CaseQuotaStore),
        patch.object(base, "next_snapshot", case.next_snapshot),
        patch.object(base, "emit", emit),
        patch.object(execution.RunJournal, "claim", claim),
    ):
        return previous.main(argv)


if __name__ == "__main__":
    sys.exit(main())
