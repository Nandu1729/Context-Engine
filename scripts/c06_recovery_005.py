#!/usr/bin/env python3
"""Continue untouched C06 cases after three exact confirmed rejections.

Preserve admission004 and its provenance; add only reviewed-baseline005.
No failed-case retry, result substitution, new-error waiver or quota change.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import c06_recovery_004 as case

previous = case.previous
base = case.base
ROOT = case.ROOT
PLAN = ROOT / "output/c06-recovery-amendment-005.json"
BASELINE = ROOT / "output/c06-live-batch-171.json"
STATUS = ROOT / "output/c06-live-batch-171.http-status.json"
FEATURE_PROBE = "a184aef47d7d5974ab58f612b991c0b96de1b22d56aca9033b7a8d6252f32910"
REVIEWED = {
    **case.reviewed.REVIEWED,
    FEATURE_PROBE: "198a8e07588b4131ae38e8df252bde55",
}


def verify():
    case.verify()
    plan = json.loads(PLAN.read_text())
    expected = {
        "source_sha256": previous.digest(__file__),
        "baseline_sha256": previous.digest(BASELINE),
        "admission_source_sha256": previous.digest(ROOT / "scripts/c06_recovery_004.py"),
        "admission_plan_sha256": previous.digest(case.PLAN),
        "status_sha256": previous.digest(STATUS),
        "execution_id": base.EXECUTION,
        "reviewed": REVIEWED,
    }
    if any(plan.get(k) != v for k, v in expected.items()):
        raise ValueError("Recovery005 provenance changed")
    baseline = json.loads(BASELINE.read_text())
    status = json.loads(STATUS.read_text())
    if (
        baseline["execution_id"] != base.EXECUTION
        or status["execution_id"] != base.EXECUTION
        or status["recovery_amendment_sha256"] != previous.digest(case.PLAN)
        or status["recovery_source_sha256"] != previous.digest(ROOT / "scripts/c06_recovery_004.py")
        or status["snapshot"] != BASELINE.name
        or [r["status"] for r in status["responses"]] != [400]
    ):
        raise ValueError("Reviewed rejection evidence changed")
    checked_records(baseline, baseline["entries"])
    return baseline


def checked_records(baseline, current):
    # Reuse exact record/receipt guards without changing immutable source files.
    with patch.object(case.reviewed, "REVIEWED", REVIEWED):
        return case.reviewed.checked_records(baseline, current)


def main(argv=None):
    original_inspect = previous.inspect
    original_dispatch = previous.dispatch
    original_emit = base.emit

    def inspect():
        result = original_inspect()
        if "reviewed_errors" in result:
            result["reviewed_errors"] = len(REVIEWED)
        return result

    def dispatch(snapshot):
        before = inspect()
        result = original_dispatch(snapshot)
        case.check_progress(before, inspect())
        return result

    def emit(value):
        if value.get("recovery") == "reviewed-002":
            value = {**value, "recovery": "reviewed-005"}
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
    ):
        return previous.main(argv)


if __name__ == "__main__":
    sys.exit(main())
