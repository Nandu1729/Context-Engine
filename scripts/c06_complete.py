#!/usr/bin/env python3
"""Foreground pacing for the existing frozen C06 run; no provider/model changes.

Default: read-only status. --allow-live invokes only the archived CLI. Wait for
minute quota, but stop on daily exhaustion, error/uncertainty, or complete matrix.
Never changes policies, records, keys or identities; never runs as a daemon.
"""

import argparse
import fcntl
import json
import math
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "output/private/c06-live-account.sqlite"
JOURNAL = ROOT / "output/private/c06-live-matrix/run.sqlite"
CLI = ROOT / "output/private/c06-frozen-env/bin/context-engine"
EXECUTION = "dd8c88217a8a2b3d2ba4635b9a126f5cdb4776ee283047425603ce8a0b30de77"
POLICY = {
    "account_id": "groq-personal-context-engine-v1",
    "billing_mode": "free_tier",
    "daily_budget_microusd": 0,
    "rpm": 30,
    "tpm": 8000,
    "rpd": 1000,
    "tpd": 200000,
}


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def pacing(rows, reservation, now):
    """Read-only conservative mirror; archived CLI remains admission authority."""
    if type(reservation) is not int or not 0 < reservation <= POLICY["tpm"]:
        return {"status": "stop", "reason": "invalid_or_unserviceable_reservation"}
    if any(r["state"] in ("reserved", "inflight", "uncertain") for r in rows):
        return {"status": "stop", "reason": "uncertain_or_active_attempt"}
    if any(r["charged_tokens"] is None or r["cost"] is None for r in rows):
        return {"status": "stop", "reason": "unknown_usage"}
    if any(r["cost"] != 0 for r in rows):
        return {"status": "stop", "reason": "nonzero_cost"}
    day_start = int(now // 86400) * 86400

    def anchor(row):
        return row["settled"] if row["settled"] is not None else row["created"]

    daily = [r for r in rows if anchor(r) >= day_start]
    minute = [r for r in rows if anchor(r) > now - 60]
    tokens = sum(r["charged_tokens"] for r in daily)
    info = {
        "daily_tokens": tokens,
        "daily_remaining": POLICY["tpd"] - tokens,
        "next_reservation": reservation,
    }
    if (
        tokens + reservation > POLICY["tpd"]
        or sum(r["request_count"] for r in daily) + 1 > POLICY["rpd"]
    ):
        return {
            **info,
            "status": "stop",
            "reason": "daily_quota",
            "next_local_utc_window": day_start + 86400,
        }
    if (
        sum(r["charged_tokens"] for r in minute) + reservation > POLICY["tpm"]
        or sum(r["request_count"] for r in minute) + 1 > POLICY["rpm"]
    ):
        # Waiting until the full minute clears is conservative and avoids polling inference.
        wait = max(anchor(r) for r in minute) + 61 - now
        return {**info, "status": "wait", "seconds": min(30, max(1, math.ceil(wait)))}
    return {**info, "status": "ready"}


def readonly(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe database path")
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def inspect():
    now = time.time()
    with readonly(LEDGER) as ledger:
        accounts = ledger.execute("SELECT * FROM accounts").fetchall()
        if len(accounts) != 1 or json.loads(accounts[0]["policy"]) != POLICY:
            raise ValueError("policy changed")
        if now + 5 < accounts[0]["last_clock"]:
            raise ValueError("clock moved backwards")
        now = max(now, accounts[0]["last_clock"])
        attempts = [dict(r) for r in ledger.execute("SELECT * FROM attempts")]
    with readonly(JOURNAL) as journal:
        states = list(journal.execute("SELECT phase,record FROM benchmark_probes"))
        done = [r for r in states if r["phase"] == "done"]
        info = {"terminal": len(done), "remaining": 744 - len(done)}
        if any(r["phase"] == "dispatching" for r in states):
            return {**info, "status": "stop", "reason": "uncertain_dispatch"}
        records = [json.loads(r["record"]) for r in done]
        if any(r["state"] not in ("success", "non_fit") for r in records):
            return {**info, "status": "stop", "reason": "terminal_error_or_truncation"}
        if len(done) == 744:
            # Completion still needs the archived snapshot/report integrity gates.
            return {**info, "status": "complete"}
        pending = [json.loads(r["record"]) for r in states if r["phase"] == "pending"]
        if len(pending) != 1:
            return {**info, "status": "stop", "reason": "unexpected_pending_count"}
        row = pending[0]
        identity = json.loads(
            journal.execute("SELECT payload FROM benchmark_identity").fetchone()[0]
        )
        generation = identity["profile"]["clients"][row["model"]]["generation"]
        reservation = row["estimate"]["estimated_tokens"] + generation["max_completion_tokens"]
        return {
            **info,
            "next": [row["model"], row["budget"], row["variant"], row["fact_id"]],
            **pacing(attempts, reservation, now),
        }


def next_snapshot():
    numbers = []
    for path in (ROOT / "output").glob("c06-live-batch-*.json"):
        match = re.fullmatch(r"c06-live-batch-(\d+).json", path.name)
        if match:
            numbers.append(int(match[1]))
    if not numbers:
        raise ValueError("existing snapshots missing")
    return ROOT / "output" / f"c06-live-batch-{max(numbers) + 1:03d}.json"


def dispatch(snapshot):
    command = [
        str(CLI),
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
    emit({"status": "batch_start", "snapshot": snapshot.name})
    child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        try:
            stdout, _ = child.communicate(timeout=30)
            break
        except subprocess.TimeoutExpired:
            emit({"status": "batch_running", "snapshot": snapshot.name})
    # Never echo subprocess exceptions, stderr, credentials or provider bodies.
    if child.returncode or len(stdout) > 16384:
        raise ValueError("archived runner failed; preserve intents")
    result = json.loads(stdout)
    if result.get("execution_id") != EXECUTION:
        raise ValueError("execution changed")
    emit({k: result.get(k) for k in ("status", "reason", "calls", "snapshot")})
    if result.get("status") == "FINISHED":
        return "finished"
    if result.get("status") == "PAUSED" and result.get("reason") == "quota":
        return "quota"
    raise ValueError("non-quota pause")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.allow_live:
            emit(inspect())
            return 0
        fd = os.open(
            ROOT / "output/private/c06-completion.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                state = inspect()
                emit(state)
                if state["status"] in ("stop", "complete"):
                    return int(state["status"] == "stop")
                if state["status"] == "wait":
                    time.sleep(state["seconds"])
                    continue
                if dispatch(next_snapshot()) == "finished":
                    return 0
    except Exception:
        emit({"status": "stop", "reason": "controller_failed_preserve_journal_and_ledger"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
