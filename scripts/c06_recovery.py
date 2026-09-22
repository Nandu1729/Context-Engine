#!/usr/bin/env python3
"""Continue untouched C06 cases after one specifically reviewed rejection.

Never retry/rewrite the rejected case. One logical case per batch, stop on any
new failure. Metadata-only HTTP observation; no response bodies or headers.
Operational amendment002 is separate from the frozen engine and amendment001.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import c06_cached_quota as cache

base = cache.base
PLAN = base.ROOT / "output/c06-recovery-amendment-002.json"
BASELINE = base.ROOT / "output/c06-live-batch-138.json"
REVIEWED = "aabbf859b652b68adf0ac46f72948f5b5897dfaca0c758060aacd300fa5ddcbd"
ATTEMPT = "5ae2f0761efd45f88f17fb05c32ab083"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    cache.verify_amendment()
    plan = json.loads(PLAN.read_text())
    baseline = json.loads(BASELINE.read_text())
    if (
        plan["source_sha256"] != digest(__file__)
        or plan["baseline_sha256"] != digest(BASELINE)
        or plan["execution_id"] != base.EXECUTION
        or plan["reviewed_probe"] != REVIEWED
        or plan["reviewed_attempt"] != ATTEMPT
        or baseline["execution_id"] != base.EXECUTION
    ):
        raise ValueError("Recovery provenance changed")
    return baseline


def checked_records(baseline, current):
    old = {e["probe_id"]: e for e in baseline["entries"] if e["phase"] == "done"}
    done = {e["probe_id"]: e for e in current if e["phase"] == "done"}
    if any(done.get(k) != v for k, v in old.items()):
        raise ValueError("Historical entry changed")
    errors = [e for e in done.values() if e["record"]["state"] not in ("success", "non_fit")]
    if len(errors) != 1 or errors[0]["probe_id"] != REVIEWED:
        raise ValueError("New or different failure requires review")
    rejected = errors[0]["receipt"]["ledger_rows"]
    if len(rejected) != 1 or any(
        rejected[0][key] != value
        for key, value in {
            "id": ATTEMPT,
            "state": "rejected",
            "reason": "provider_rejected",
            "charged_tokens": 0,
            "cost": 0,
        }.items()
    ):
        raise ValueError("Reviewed rejection changed")
    return done


def inspect():
    baseline = verify()
    # Original inspection still checks account policy and clock before the error hold.
    state = cache.ORIGINAL_INSPECT()
    if state.get("reason") != "terminal_error_or_truncation":
        return state
    with base.readonly(base.JOURNAL) as con:
        current = []
        for row in con.execute("SELECT * FROM benchmark_probes"):
            current.append(
                {
                    "probe_id": row["id"],
                    "phase": row["phase"],
                    "record": json.loads(row["record"]),
                    "receipt": json.loads(row["receipt"]) if row["receipt"] else None,
                    "reserved_cost": row["reserved_cost"],
                }
            )
        identity = json.loads(con.execute("SELECT payload FROM benchmark_identity").fetchone()[0])
    if identity["profile"] != baseline["profile"]:
        raise ValueError("Execution profile changed")
    done = checked_records(baseline, current)
    info = {"terminal": len(done), "remaining": 744 - len(done), "reviewed_errors": 1}
    if len(done) == 744:
        return {**info, "status": "complete"}
    pending = [e["record"] for e in current if e["phase"] == "pending"]
    if len(pending) != 1:
        raise ValueError("Unexpected pending count")
    row = pending[0]
    reservation = (
        row["estimate"]["estimated_tokens"]
        + identity["profile"]["clients"][row["model"]]["generation"]["max_completion_tokens"]
    )
    with base.readonly(base.LEDGER) as con:
        account = con.execute("SELECT last_clock FROM accounts").fetchone()[0]
        attempts = [dict(r) for r in con.execute("SELECT * FROM attempts")]
    return {
        **info,
        "next": [row["model"], row["budget"], row["variant"], row["fact_id"]],
        **cache.pacing(attempts, reservation, max(time.time(), account)),
    }


def exclusive_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def one_case(argv):
    argv = list(argv)
    position = argv.index("--max-calls") + 1
    if argv[position] != "744":
        raise ValueError("Unexpected original batch bound")
    argv[position] = "1"
    return argv


def batch(snapshot):
    import httpx

    from context_engine import cli

    state = inspect()
    if state["status"] != "ready":
        raise ValueError("Not ready for reviewed continuation")
    snapshot = Path(snapshot).absolute()
    if snapshot.parent != base.ROOT / "output" or snapshot.exists():
        raise ValueError("Unsafe snapshot path")
    proof = {
        "execution_id": base.EXECUTION,
        "recovery_amendment_sha256": digest(PLAN),
        "recovery_source_sha256": digest(__file__),
        "snapshot": snapshot.name,
        "before": state,
        "created_utc_epoch": time.time(),
    }
    exclusive_json(snapshot.with_suffix(".recovery.json"), proof)
    statuses = []

    async def observe(response):
        # Do not read bodies, headers, request objects, keys or provider messages.
        statuses.append({"status": int(response.status_code), "at": time.time()})

    original_client = httpx.AsyncClient
    original_main = cli.main

    class ObservedClient(original_client):
        def __init__(self, *args, **kwargs):
            if "event_hooks" in kwargs:
                raise ValueError("Unexpected transport hooks")
            super().__init__(*args, **kwargs, event_hooks={"response": [observe]})

    try:
        with (
            patch.object(httpx, "AsyncClient", ObservedClient),
            patch.object(cli, "main", lambda args: original_main(one_case(args))),
            patch.object(cache, "inspect", inspect),
        ):
            return cache.batch(snapshot)
    finally:
        exclusive_json(snapshot.with_suffix(".http-status.json"), {**proof, "responses": statuses})


def dispatch(snapshot):
    base.emit({"status": "batch_start", "snapshot": snapshot.name, "recovery": "reviewed-002"})
    child = subprocess.Popen(
        [
            str(base.CLI.parent / "python"),
            str(Path(__file__).resolve()),
            "--allow-live",
            "--batch",
            str(snapshot),
        ],
        cwd=base.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    while True:
        try:
            stdout, _ = child.communicate(timeout=30)
            break
        except subprocess.TimeoutExpired:
            base.emit({"status": "batch_running", "snapshot": snapshot.name})
    if child.returncode or len(stdout) > 16384:
        raise ValueError("Recovery runner failed; preserve intents")
    result = json.loads(stdout)
    if result.get("execution_id") != base.EXECUTION or result.get("calls", 2) > 1:
        raise ValueError("Unexpected batch identity or size")
    base.emit({k: result.get(k) for k in ("status", "reason", "calls", "snapshot")})
    # Review every new terminal outcome before dispatching another case.
    inspect()
    if result.get("status") == "FINISHED":
        return "finished"
    if result.get("status") == "PAUSED" and result.get("reason") in ("quota", "batch_limit"):
        return "quota"
    raise ValueError("Unexpected stop")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--batch", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.batch:
            if not args.allow_live:
                raise ValueError("Explicit live opt-in required")
            return batch(args.batch)
        verify()
        with patch.object(base, "inspect", inspect), patch.object(base, "dispatch", dispatch):
            return base.main(["--allow-live"] if args.allow_live else [])
    except Exception:
        base.emit({"status": "stop", "reason": "recovery_review_required_preserve_records"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
