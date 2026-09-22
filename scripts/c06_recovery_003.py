#!/usr/bin/env python3
"""Reviewed continuation after the two preserved C06 rejections; no retries.

Reuse immutable recovery002's single-case loop, lock and HTTP status observation.
Only the baseline/reviewed-error set and provenance change. New failures halt.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import c06_recovery as previous

ROOT = previous.base.ROOT
PLAN = ROOT / "output/c06-recovery-amendment-003.json"
BASELINE = ROOT / "output/c06-live-batch-144.json"
PARENT = ROOT / "scripts/c06_recovery.py"
DIAGNOSTIC = ROOT / "output/c06-rejection-diagnostic-001.json"
REGION_PROBE = "105628762a1cc7433bb972ef532e2fd0deba3d04c378133843b65f154537370f"
FEATURE_PROBE = "aabbf859b652b68adf0ac46f72948f5b5897dfaca0c758060aacd300fa5ddcbd"
REVIEWED = {
    REGION_PROBE: "df9f1fc095f44983845fc071db89ea44",
    FEATURE_PROBE: "5ae2f0761efd45f88f17fb05c32ab083",
}


def verify():
    previous.cache.verify_amendment()
    plan = json.loads(PLAN.read_text())
    expected = {
        "source_sha256": previous.digest(__file__),
        "parent_source_sha256": previous.digest(PARENT),
        "baseline_sha256": previous.digest(BASELINE),
        "diagnostic_sha256": previous.digest(DIAGNOSTIC),
        "execution_id": previous.base.EXECUTION,
        "reviewed": REVIEWED,
    }
    if any(plan.get(k) != v for k, v in expected.items()):
        raise ValueError("Recovery003 provenance changed")
    baseline = json.loads(BASELINE.read_text())
    if baseline["execution_id"] != previous.base.EXECUTION:
        raise ValueError("Baseline identity changed")
    return baseline


def checked_records(baseline, current):
    old = {e["probe_id"]: e for e in baseline["entries"] if e["phase"] == "done"}
    done = {e["probe_id"]: e for e in current if e["phase"] == "done"}
    if any(done.get(k) != v for k, v in old.items()):
        raise ValueError("Historical entry changed")
    errors = {k: e for k, e in done.items() if e["record"]["state"] not in ("success", "non_fit")}
    if set(errors) != set(REVIEWED):
        raise ValueError("New or missing failure requires review")
    for key, entry in errors.items():
        rows = entry["receipt"]["ledger_rows"]
        required = {
            "id": REVIEWED[key],
            "state": "rejected",
            "reason": "provider_rejected",
            "charged_tokens": 0,
            "cost": 0,
        }
        if len(rows) != 1 or any(rows[0].get(k) != v for k, v in required.items()):
            raise ValueError("Reviewed receipt changed")
    return done


def main(argv=None):
    original_inspect = previous.inspect
    original_emit = previous.base.emit

    def inspect():
        result = original_inspect()
        if "reviewed_errors" in result:
            result["reviewed_errors"] = len(REVIEWED)
        return result

    def emit(value):
        if value.get("recovery") == "reviewed-002":
            value = {**value, "recovery": "reviewed-003"}
        original_emit(value)

    # No disk rewrite of the immutable parent. Child dispatch re-enters this file;
    # its sidecars bind amendment003 plus the parent's hash, not amendment002.
    with (
        patch.object(previous, "verify", verify),
        patch.object(previous, "checked_records", checked_records),
        patch.object(previous, "inspect", inspect),
        patch.object(previous, "PLAN", PLAN),
        patch.object(previous, "__file__", str(Path(__file__).resolve())),
        patch.object(previous.base, "emit", emit),
    ):
        return previous.main(argv)


if __name__ == "__main__":
    sys.exit(main())
