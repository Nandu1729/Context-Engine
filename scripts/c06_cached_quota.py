#!/usr/bin/env python3
"""Audited C06 admission amendment: exclude only receipt-confirmed cached input.

The archived engine, requests, prices, account policy and full-usage receipts stay
unchanged. This operational store override is NOT covered by the engine freeze;
its hash is recorded in amendment001, per-batch sidecars and ledger audit events.
Unknown cache usage gets no credit. No accounting rows are rewritten or erased.
Run with the archived Python; default is read-only status, --allow-live opts in.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import c06_complete as base

from context_engine.errors import ContractError, ProviderError, QuotaError, StorageError
from context_engine.models import canonical_json
from context_engine.providers.contracts import Usage
from context_engine.providers.store import ACTIVE, Admission, RuntimeStore

AMENDMENT = base.ROOT / "output/c06-quota-amendment-001.json"
ARCHIVED_HASH = "efeaa9f2459e067ac21f93a960ec0cc537c0d266e42c25a98aa67e1ae81da6a6"
ORIGINAL_PACING = base.pacing
ORIGINAL_INSPECT = base.inspect


def source_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def cached_credit(row):
    """Validated settled usage only; do not guess absent cache metadata."""
    if row["state"] != "completed" or row.get("usage_json") is None:
        return 0
    usage = Usage(**json.loads(row["usage_json"]))
    if usage.total_tokens != row["charged_tokens"]:
        raise StorageError("Receipt total differs from recorded token usage")
    return usage.cached_input_tokens or 0


def pacing(rows, reservation, now):
    original = ORIGINAL_PACING(rows, reservation, now)
    if original.get("reason") not in (None, "daily_quota"):
        return original
    adjusted = [{**r, "charged_tokens": r["charged_tokens"] - cached_credit(r)} for r in rows]
    result = ORIGINAL_PACING(adjusted, reservation, now)
    day = int(now // 86400) * 86400
    today = [r for r in rows if (r["settled"] or r["created"]) >= day]
    return {
        **result,
        "full_daily_tokens": sum(r["charged_tokens"] for r in today),
        "known_cached_daily_tokens": sum(cached_credit(r) for r in today),
        "admission": "known-cached-input-excluded-v1",
    }


def inspect():
    with patch.object(base, "pacing", pacing):
        return ORIGINAL_INSPECT()


class CachedQuotaStore(RuntimeStore):
    """Same SQLite transaction/receipt format; corrected quota-only projection."""

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
            raise ContractError("Amendment supports only unchanged C06 free-tier policy")
        policy.validate_prices(prices)
        if type(reserved_tokens) is not int or not 0 < reserved_tokens <= policy.tpm:
            raise ContractError("Invalid token reservation")
        if type(reserved_cost) is not int or reserved_cost != 0:
            raise ContractError("Amendment cannot enable paid spending")
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
            if any(r["request_key"] == key and r["state"] == "completed" for r in rows):
                raise QuotaError("Completed requests must not be sent again")
            state = pacing(rows, reserved_tokens, now)
            if state["status"] != "ready":
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
            db.execute(
                """INSERT INTO events(
                   id,account,request_key,created,kind,source_attempt,evidence_ref)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex,
                    account,
                    key,
                    now,
                    "cached_quota_admission_v1",
                    attempt,
                    "c06-quota-amendment-001:sha256:" + source_hash(),
                ),
            )
            return Admission(attempt_id=attempt)


def verify_amendment():
    from context_engine.evaluation.protocol import code_hash

    plan = json.loads(AMENDMENT.read_text())
    if (
        plan["admission_source_sha256"] != source_hash()
        or plan["execution_id"] != base.EXECUTION
        or plan["quota_policy"] != base.POLICY
        or code_hash() != ARCHIVED_HASH
    ):
        raise ValueError("Admission amendment or archived source changed")
    baseline = json.loads((base.ROOT / "output/c06-live-batch-131.json").read_text())
    if baseline["digest"] != plan["baseline_snapshot_digest"]:
        raise ValueError("Baseline changed")
    return plan


def batch(snapshot):
    """Install scoped operational store override, never modify archived files."""
    from context_engine.cli import main as cli_main
    from context_engine.evaluation import run_commands

    verify_amendment()
    snapshot = Path(snapshot).absolute()
    if snapshot.parent != base.ROOT / "output" or snapshot.exists():
        raise ValueError("Unsafe or existing snapshot")
    sidecar = snapshot.with_suffix(".admission.json")
    proof = {
        "execution_id": base.EXECUTION,
        "admission_source_sha256": source_hash(),
        "archived_engine_sha256": ARCHIVED_HASH,
        "amendment_sha256": hashlib.sha256(AMENDMENT.read_bytes()).hexdigest(),
        "snapshot": snapshot.name,
        "before": inspect(),
        "created_utc_epoch": time.time(),
        "note": "Quota-admission amendment; full receipt usage and frozen experiment unchanged",
    }
    fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(proof, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    # Use only the owner's current explicit file, not a stale inherited key.
    os.environ.pop("GROQ_API_KEY", None)
    with patch.object(run_commands, "RuntimeStore", CachedQuotaStore):
        return cli_main(
            [
                "benchmark-run",
                "--mode",
                "live",
                "--allow-live",
                "--env-file",
                ".env",
                "--live-config",
                "output/private/c06-live-config.json",
                "--run-dir",
                "output/private/c06-live-matrix",
                "--snapshot",
                str(snapshot),
                "--max-calls",
                "744",
            ]
        )


def dispatch(snapshot):
    base.emit({"status": "batch_start", "snapshot": snapshot.name, "admission": "cached-v1"})
    command = [
        str(base.CLI.parent / "python"),
        str(Path(__file__).resolve()),
        "--allow-live",
        "--batch",
        str(snapshot),
    ]
    child = subprocess.Popen(command, cwd=base.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        try:
            stdout, _ = child.communicate(timeout=30)
            break
        except subprocess.TimeoutExpired:
            base.emit({"status": "batch_running", "snapshot": snapshot.name})
    if child.returncode or len(stdout) > 16384:
        raise ValueError("Amended runner failed; preserve journal")
    result = json.loads(stdout)
    if result.get("execution_id") != base.EXECUTION:
        raise ValueError("Execution identity changed")
    base.emit({k: result.get(k) for k in ("status", "reason", "calls", "snapshot")})
    if result.get("status") == "FINISHED":
        return "finished"
    if result.get("status") == "PAUSED" and result.get("reason") == "quota":
        return "quota"
    raise ValueError("Non-quota stop")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--batch", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.batch:
            if not args.allow_live:
                raise ValueError("Live authorization required")
            return batch(args.batch)
        if args.allow_live:
            verify_amendment()
        with patch.object(base, "inspect", inspect), patch.object(base, "dispatch", dispatch):
            return base.main(["--allow-live"] if args.allow_live else [])
    except Exception:
        base.emit({"status": "stop", "reason": "cached_admission_failed_preserve_ledger"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
