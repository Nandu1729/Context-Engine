#!/usr/bin/env python3
"""C06 case-bound admission: identical ablation payloads are independent cases.

External amendment004; preserve immutable predecessors and all prior results.
No completed-case replay; no new failure waiver; no zero-progress busy loop.
"""

import json
import re
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import c06_recovery_003 as reviewed

from context_engine.errors import ContractError, ProviderError, QuotaError
from context_engine.models import canonical_json
from context_engine.providers.store import ACTIVE, Admission, RuntimeStore

previous = reviewed.previous
cache = previous.cache
base = previous.base
ROOT = base.ROOT
PLAN = ROOT / "output/c06-recovery-amendment-004.json"
BASELINE = ROOT / "output/c06-live-batch-155.json"


def verify():
    reviewed.verify()
    plan = json.loads(PLAN.read_text())
    if (
        plan["source_sha256"] != previous.digest(__file__)
        or plan["baseline_sha256"] != previous.digest(BASELINE)
        or plan["reviewed_source_sha256"] != previous.digest(ROOT / "scripts/c06_recovery_003.py")
        or plan["execution_id"] != base.EXECUTION
    ):
        raise ValueError("Admission004 provenance changed")
    return json.loads(BASELINE.read_text())


def claimed_probe(key, model, reservation):
    from context_engine.evaluation.corpus import load_bundle
    from context_engine.evaluation.execution import expected_request_key

    with base.readonly(base.JOURNAL) as con:
        rows = list(con.execute("SELECT id,record FROM benchmark_probes WHERE phase='dispatching'"))
        identity = json.loads(con.execute("SELECT payload FROM benchmark_identity").fetchone()[0])
    if len(rows) != 1:
        raise QuotaError("Exactly one claimed benchmark case required")
    row = json.loads(rows[0]["record"])
    baseline = verify()
    if identity["profile"] != baseline["profile"] or identity["manifest"] != baseline["manifest"]:
        raise ContractError("Claim identity changed")
    bundle = load_bundle()
    protocol = baseline["manifest"]["protocol"]
    expected = expected_request_key(
        row, baseline["profile"], base.EXECUTION, bundle.get("scenario")["scope"], protocol
    )
    if (
        rows[0]["id"] != row["probe_id"]
        or row["state"] != "prepared"
        or row["model"] != model
        or key != expected
        or reservation
        != row["estimate"]["estimated_tokens"] + protocol["generation"]["max_completion_tokens"]
    ):
        raise ContractError("Admission does not match claimed case")
    return row["probe_id"]


class CaseQuotaStore(RuntimeStore):
    def admit(
        self,
        *,
        policy,
        key,
        model,
        reserved_tokens,
        reserved_cost,
        prices,
        replay,
        now,
        send_allowed=True,
    ):
        if asdict(policy) != base.POLICY or replay.enabled:
            raise ContractError("Only unchanged free-tier/no-replay scope is supported")
        policy.validate_prices(prices)
        if type(reserved_tokens) is not int or not 0 < reserved_tokens <= policy.tpm:
            raise ContractError("Invalid token reservation")
        if type(reserved_cost) is not int or reserved_cost != 0:
            raise ContractError("Paid spending is disabled")
        if not send_allowed:
            raise ProviderError("Credentials required")
        with self.transaction() as db:
            account, now = self._account(db, policy, now)
            rows = [
                dict(r) for r in db.execute("SELECT * FROM attempts WHERE account=?", (account,))
            ]
            for row in rows:
                self._validate_row(row)
            if any(r["state"] in ACTIVE for r in rows):
                raise QuotaError("Active or uncertain usage must be resolved")
            probe = claimed_probe(key, model, reserved_tokens)
            marker = "c06-case:" + probe
            # A fulfilled dispatch cannot be replayed even if journal finalization crashed.
            if db.execute(
                """SELECT 1 FROM events e JOIN attempts a ON a.id=e.source_attempt
                   WHERE e.account=? AND e.evidence_ref=?
                   AND a.state IN ('completed','reconciled') LIMIT 1""",
                (account, marker),
            ).fetchone():
                raise QuotaError("This case already has a fulfilled dispatch")
            if cache.pacing(rows, reserved_tokens, now)["status"] != "ready":
                raise QuotaError("Local account quota exhausted")
            attempt = uuid.uuid4().hex
            db.execute(
                """INSERT INTO attempts(id,account,request_key,model,created,state,
                   reserved_tokens,reserved_cost,price_json)
                   VALUES(?,?,?,?,?,'reserved',?,?,?)""",
                (
                    attempt,
                    account,
                    key,
                    model,
                    now,
                    reserved_tokens,
                    reserved_cost,
                    canonical_json(asdict(prices)),
                ),
            )
            for kind, reference in (
                ("c06_case_admission_v1", marker),
                ("c06_admission_amendment004", "sha256:" + previous.digest(PLAN)),
            ):
                db.execute(
                    """INSERT INTO events(
                       id,account,request_key,created,kind,source_attempt,evidence_ref)
                       VALUES(?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, account, key, now, kind, attempt, reference),
                )
            return Admission(attempt_id=attempt)


def next_snapshot():
    # A interrupted export may have sidecars but no snapshot; never reuse its number.
    numbers = [
        int(match[1])
        for path in (ROOT / "output").glob("c06-live-batch-*")
        if (match := re.match(r"c06-live-batch-(\d+)(?:\.|$)", path.name))
    ]
    if not numbers:
        raise ValueError("Existing run required")
    return ROOT / "output" / f"c06-live-batch-{max(numbers) + 1:03d}.json"


def check_progress(before, after):
    if after.get("terminal") == before.get("terminal") and after.get("status") == "ready":
        raise ValueError("Zero-progress local rejection needs review, not another batch")


def main(argv=None):
    original_inspect = previous.inspect
    original_dispatch = previous.dispatch
    original_emit = base.emit

    def inspect():
        result = original_inspect()
        if "reviewed_errors" in result:
            result["reviewed_errors"] = len(reviewed.REVIEWED)
        return result

    def dispatch(snapshot):
        before = inspect()
        result = original_dispatch(snapshot)
        check_progress(before, inspect())
        return result

    def emit(value):
        if value.get("recovery") == "reviewed-002":
            value = {**value, "recovery": "case-bound-004"}
        original_emit(value)

    with (
        patch.object(previous, "verify", verify),
        patch.object(previous, "checked_records", reviewed.checked_records),
        patch.object(previous, "inspect", inspect),
        patch.object(previous, "dispatch", dispatch),
        patch.object(previous, "PLAN", PLAN),
        patch.object(previous, "__file__", str(Path(__file__).resolve())),
        patch.object(cache, "CachedQuotaStore", CaseQuotaStore),
        patch.object(base, "next_snapshot", next_snapshot),
        patch.object(base, "emit", emit),
    ):
        return previous.main(argv)


if __name__ == "__main__":
    sys.exit(main())
