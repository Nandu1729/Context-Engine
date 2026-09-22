#!/usr/bin/env python3
"""Continue untouched C06 cases after four exact confirmed rejections.

Preserve admission004 and its provenance; add only reviewed-baseline006.
No failed-case retry, result substitution, new-error waiver or quota change.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import c06_recovery_005 as history

case = history.case

previous = case.previous
base = case.base
ROOT = case.ROOT
PLAN = ROOT / "output/c06-recovery-amendment-006.json"
BASELINE = ROOT / "output/c06-live-batch-177.json"
STATUS = ROOT / "output/c06-live-batch-177.http-status.json"
FEATURE_PROBE = "698887bd5ac557ff8c53521493f3888d15f3e115066e4981885de1d8fbc9040a"
REVIEWED = {
    **history.REVIEWED,
    FEATURE_PROBE: "83c389580f584b469def6de837fa2f06",
}


def verify():
    history.verify()
    plan = json.loads(PLAN.read_text())
    expected = {
        "source_sha256": previous.digest(__file__),
        "baseline_sha256": previous.digest(BASELINE),
        "admission_source_sha256": previous.digest(ROOT / "scripts/c06_recovery_004.py"),
        "admission_plan_sha256": previous.digest(case.PLAN),
        "previous_plan_sha256": previous.digest(history.PLAN),
        "previous_source_sha256": previous.digest(ROOT / "scripts/c06_recovery_005.py"),
        "status_sha256": previous.digest(STATUS),
        "execution_id": base.EXECUTION,
        "reviewed": REVIEWED,
    }
    if any(plan.get(k) != v for k, v in expected.items()):
        raise ValueError("Recovery006 provenance changed")
    baseline = json.loads(BASELINE.read_text())
    status = json.loads(STATUS.read_text())
    if (
        baseline["execution_id"] != base.EXECUTION
        or status["execution_id"] != base.EXECUTION
        or status["recovery_amendment_sha256"] != previous.digest(history.PLAN)
        or status["recovery_source_sha256"] != previous.digest(ROOT / "scripts/c06_recovery_005.py")
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
            value = {**value, "recovery": "reviewed-006"}
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
