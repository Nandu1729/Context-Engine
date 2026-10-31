#!/usr/bin/env python3
"""One bounded free-tier Groq answer-accuracy run over offline strategies (D109).

900-token budget only, frozen synthetic corpus, five assembled strategies x 31 facts
(max 155 calls), gpt-oss-20b, 256 completion tokens, no retries, no paid usage.
Commands: `plan` (offline, default), `run --allow-live`, `report`, `amend --decision`.
Stops on any provider error (including rate limits) or unknown/nonzero cost. After an
owner-approved amendment (D110), a confirmed zero-token `provider_rejected` 4xx is a
terminal failed slot (never retried) and the run continues, up to MAX_REJECTIONS.
Answer content stays under output/private/; console output is status JSON only.
"""

import argparse
import asyncio
import fcntl
import hashlib
import json
import math
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from context_engine.budget import validate_request
from context_engine.evaluation.corpus import aliases, load_bundle, strict_json
from context_engine.evaluation.grading import answer_correct
from context_engine.evaluation.protocol import code_hash, load_freeze
from context_engine.evaluation.strategies import assemble_strategy
from context_engine.models import canonical_json
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    Completion,
    GenerationConfig,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    RetryConfig,
    fingerprint,
)
from context_engine.providers.credentials import load_api_key, private_bytes
from context_engine.providers.store import ACTIVE, RuntimeStore
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "strategy-accuracy-900-001"
RUN = ROOT / "output/private" / RUN_ID
PUBLIC = ROOT / "output" / RUN_ID
LEDGER = ROOT / "output/private/c06-live-account.sqlite"
CONFIG = ROOT / "output/private/c06-live-config.json"
MODEL = "openai/gpt-oss-20b"
BUDGET = 900
STRATEGIES = (
    "recent_window",
    "summary_window",
    "retrieval_window",
    "combined",
    "combined_no_recover",
)
MAX_CALLS = 155
MAX_REJECTIONS = 10
AMENDMENT_RULE = "confirmed zero-token provider_rejected is a terminal failed slot; continue"
POLICY = QuotaPolicy(account_id="groq-personal-context-engine-v1", billing_mode="free_tier")
PRICES = PriceCard("owner-confirmed-free-2026-09-13", 0, 0, 0)
GENERATION = GenerationConfig(model=MODEL, max_completion_tokens=256)
RETRIES = RetryConfig(max_attempts=1, attempt_timeout=20, total_timeout=25)


def require(condition):
    if not condition:
        raise ValueError("Strategy-accuracy safety/integrity check failed; preserve evidence")


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def read(path):
    return strict_json(Path(path).read_text(), maximum=4_000_000)


def save(path, value):
    """Exclusive, durable write; never overwrites evidence."""
    path = Path(path)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def configuration():
    data = strict_json(private_bytes(CONFIG, 65536).decode(), maximum=65536)
    require(data["quota"] == asdict(POLICY))
    require(data["prices"][MODEL] == asdict(PRICES))
    require(data["max_run_cost_microusd"] == 0)
    require(Path(data["ledger_path"]).absolute() == LEDGER)
    POLICY.validate_prices(PRICES)


def ledger():
    """Read-only account inspection; prints nothing private."""
    require(LEDGER.is_file() and not LEDGER.is_symlink())
    db = sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY id")]
        for row in rows:
            RuntimeStore._validate_row(row)
        return rows
    finally:
        db.close()


def pacing(rows, reservation, now):
    if any(r["state"] in ACTIVE or r["cost"] != 0 or r["charged_tokens"] is None for r in rows):
        return "unsafe_account", 0

    def anchor(r):
        return r["settled"] if r["settled"] is not None else r["created"]

    daily = [r for r in rows if anchor(r) >= int(now // 86400) * 86400]
    minute = [r for r in rows if anchor(r) > now - 60]
    if (
        sum(r["charged_tokens"] for r in daily) + reservation > POLICY.tpd
        or sum(r["request_count"] for r in daily) + 1 > POLICY.rpd
    ):
        return "daily_quota", 0
    if (
        sum(r["charged_tokens"] for r in minute) + reservation > POLICY.tpm
        or sum(r["request_count"] for r in minute) + 1 > POLICY.rpm
    ):
        return "minute_wait", min(30, max(1, math.ceil(max(map(anchor, minute)) + 61 - now)))
    return "ready", 0


def build():
    """Deterministic plan: fact-major order so a partial run compares strategies fairly."""
    require(load_freeze()["runtime"]["code_hash"] == code_hash())
    bundle = load_bundle()
    counter = TiktokenCounter()
    slots, requests = [], []
    for fact in bundle.facts:
        for strategy in STRATEGIES:
            result, budget = assemble_strategy(bundle, fact, BUDGET, strategy)
            require(budget.completion_reservation == GENERATION.max_completion_tokens)
            estimate = validate_request(request=result.request, config=budget, counter=counter)
            slots.append(
                {
                    "slot": len(slots),
                    "fact_id": fact["fact_id"],
                    "zone": fact["zone"],
                    "strategy": strategy,
                    "estimated_tokens": estimate.estimated_tokens,
                    "request_hash": fingerprint(result.request.to_wire()),
                }
            )
            scope = bundle.job(fact["question"]).arguments["pinned_facts"].scope
            requests.append((result.request, budget, scope))
    require(len(slots) == MAX_CALLS)
    return bundle, slots, requests


def identity(slots):
    return {
        "id": RUN_ID,
        "approval": "D109",
        "runner_sha256": runner_hash(),
        "code_hash": code_hash(),
        "model": MODEL,
        "budget": BUDGET,
        "generation": asdict(GENERATION),
        "retries": asdict(RETRIES),
        "quota": asdict(POLICY),
        "max_calls": MAX_CALLS,
        "slots": slots,
    }


def runner_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def amendment():
    path = RUN / "amendment-001.json"
    return read(path) if path.exists() else None


def verify(manifest, expected):
    """Same plan; the runner may differ only under a recorded amendment."""
    require(
        {k: v for k, v in manifest.items() if k != "runner_sha256"}
        == {k: v for k, v in expected.items() if k != "runner_sha256"}
    )
    change = amendment()
    if change is None:
        require(manifest["runner_sha256"] == expected["runner_sha256"])
    else:
        require(
            set(change)
            == {
                "decision",
                "base_runner_sha256",
                "runner_sha256",
                "rule",
                "reviewed_failures",
                "max_rejections",
            }
        )
        require(change["base_runner_sha256"] == manifest["runner_sha256"])
        require(change["runner_sha256"] == expected["runner_sha256"])
        require(change["rule"] == AMENDMENT_RULE and change["max_rejections"] == MAX_REJECTIONS)
    return change


def skippable(result, rows):
    """A confirmed, zero-token, zero-cost provider 4xx rejection (not 429/uncertain)."""
    attempts = {r["id"]: r for r in rows}
    ids = result["attempt_ids"]
    return (
        result["status"] == "error"
        and result["error_code"] == "provider_rejected"
        and result["new_cost_microusd"] == 0
        and result["warning"] is None
        and len(ids) == 1
        and ids[0] in attempts
        and attempts[ids[0]]["state"] == "rejected"
        and attempts[ids[0]]["charged_tokens"] == 0
        and attempts[ids[0]]["cost"] == 0
    )


def receipts(manifest):
    """Validated receipts by slot; any unreceipted claim stops dispatch."""
    done, open_claims = {}, []
    execution = fingerprint(manifest)
    for slot in manifest["slots"]:
        claim, receipt = (
            RUN / f"claim-{slot['slot']:03d}.json",
            RUN / f"receipt-{slot['slot']:03d}.json",
        )
        if not claim.exists():
            require(not receipt.exists())
            continue
        require(read(claim) == {"execution": execution, "slot": slot["slot"]})
        if not receipt.exists():
            open_claims.append(slot["slot"])
            continue
        value = read(receipt)
        require(value["claim_hash"] == fingerprint(read(claim)))
        require(len(value["result"]["attempt_ids"]) <= 1)
        done[slot["slot"]] = value
    return done, open_claims


async def dispatch(manifest, requests, client, *, sleep=asyncio.sleep, change=None):
    execution = fingerprint(manifest)
    for slot, (request, budget, scope) in zip(manifest["slots"], requests, strict=True):
        done, open_claims = receipts(manifest)
        if open_claims:
            return "unreceipted_claim"
        errors = [r["result"] for r in done.values() if r["result"]["status"] == "error"]
        if errors:
            rows = ledger()
            if change is None or not all(skippable(e, rows) for e in errors):
                return "preserved_error"
            if len(errors) > MAX_REJECTIONS:
                return "too_many_rejections"
        if slot["slot"] in done:
            continue
        waited = 0
        while True:
            state, delay = pacing(ledger(), slot["estimated_tokens"] + 256, time.time())
            if state == "minute_wait" and waited + delay <= 300:
                await sleep(delay)
                waited += delay
                continue
            break
        if state != "ready":
            return state
        claim = {"execution": execution, "slot": slot["slot"]}
        save(RUN / f"claim-{slot['slot']:03d}.json", claim)
        start = time.monotonic()
        result = await client.complete(
            request,
            budget,
            scope=scope,
            security_scope=RUN_ID,
            snapshot_revision=slot["request_hash"],
            policy_version=execution,
        )
        save(
            RUN / f"receipt-{slot['slot']:03d}.json",
            {
                "claim_hash": fingerprint(claim),
                "result": result.to_dict(include_content=True),
                "elapsed_seconds": time.monotonic() - start,
            },
        )
        emit({"status": result.status, "slot": slot["slot"] + 1, "planned": MAX_CALLS})
        if result.status == "error":
            if change is not None and skippable(result.to_dict(), ledger()):
                continue  # Terminal failed slot; next loop re-checks the rejection cap.
            return f"stopped_{result.error_code}"
        if result.new_cost_microusd != 0:
            return "stopped_unknown_or_nonzero_cost"
    return "finished"


def wilson(correct, total):
    if total == 0:
        return None
    z = 1.959963984540054
    p = correct / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return [round(max(0, center - width), 4), round(min(1, center + width), 4)]


def report(manifest, bundle):
    done, open_claims = receipts(manifest)
    facts = {f["fact_id"]: f for f in bundle.facts}
    by_strategy = {
        s: {"planned": 31, "answered": 0, "correct": 0, "rejected": 0, "statuses": {}}
        for s in STRATEGIES
    }
    tokens = {"input": 0, "output": 0, "reasoning": 0, "estimated_input": 0}
    rows = []
    for slot in manifest["slots"]:
        if slot["slot"] not in done:
            continue
        result = done[slot["slot"]]["result"]
        group = by_strategy[slot["strategy"]]
        group["statuses"][result["status"]] = group["statuses"].get(result["status"], 0) + 1
        correct = None
        if result["status"] == "error":
            group["rejected"] += 1
        if result["completion"] is not None:
            completion = Completion.from_dict(result["completion"])
            group["answered"] += 1
            correct = result["status"] == "success" and answer_correct(
                completion.content, aliases(facts[slot["fact_id"]])
            )
            group["correct"] += correct
            tokens["input"] += completion.usage.input_tokens
            tokens["output"] += completion.usage.output_tokens
            tokens["reasoning"] += completion.usage.reasoning_tokens or 0
            tokens["estimated_input"] += slot["estimated_tokens"]
        rows.append(
            {
                **{k: slot[k] for k in ("slot", "fact_id", "zone", "strategy")},
                "status": result["status"],
                "correct": correct,
            }
        )
    for group in by_strategy.values():
        group["accuracy_of_answered"] = (
            round(group["correct"] / group["answered"], 4) if group["answered"] else None
        )
        group["wilson95_of_answered"] = wilson(group["correct"], group["answered"])
        # Conservative: rejected and unsent slots count as not correct.
        group["accuracy_of_planned"] = round(group["correct"] / group["planned"], 4)
    return {
        "id": RUN_ID,
        "status": "COMPLETE" if len(done) == MAX_CALLS else "PARTIAL",
        "provider_calls": sum(len(r["result"]["attempt_ids"]) for r in done.values()),
        "unreceipted_claims": len(open_claims),
        "amendment": amendment(),
        "model": MODEL,
        "budget": BUDGET,
        "strategies": by_strategy,
        "tokens": tokens,
        "rows": rows,
        "limitations": [
            "One synthetic scenario authored with the engine; not real-world accuracy.",
            "Strict grading: only the exact value (or one-field JSON) counts as correct.",
            "Single run, temperature 0, one model; no retries.",
        ],
    }


def load_groq_key():
    """Read only the GROQ_API_KEY line; the shared .env also holds other keys."""
    data = private_bytes(ROOT / ".env", 8192).decode("ascii")
    values = [
        line.partition("=")[2].strip()
        for line in data.splitlines()
        if line.strip().partition("=")[0].strip() == "GROQ_API_KEY"
    ]
    require(len(values) == 1)
    os.environ["GROQ_API_KEY"] = values[0].strip("\"'")
    return load_api_key(None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("plan", "run", "report", "amend"), nargs="?", default="plan"
    )
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--decision")
    args = parser.parse_args()
    try:
        configuration()
        bundle, slots, requests = build()
        expected = identity(slots)
        if args.command == "plan":
            rows = ledger()
            now = time.time()
            today = [r for r in rows if (r["settled"] or r["created"]) >= int(now // 86400) * 86400]
            reserved = sum(s["estimated_tokens"] + 256 for s in slots)
            emit(
                {
                    "status": "PLANNED",
                    "calls": len(slots),
                    "max_estimated_input_tokens": max(s["estimated_tokens"] for s in slots),
                    "reserved_tokens_total": reserved,
                    "account_tokens_used_today_utc": sum(r["charged_tokens"] or 0 for r in today),
                    "account_requests_today_utc": sum(r["request_count"] for r in today),
                    "tpd": POLICY.tpd,
                    "account_state": pacing(rows, 1, now)[0],
                    "run_exists": RUN.exists(),
                }
            )
            return 0
        if args.command == "amend":
            manifest = read(RUN / "manifest.json")
            require(args.decision == "D110" and amendment() is None)
            require(manifest["runner_sha256"] != expected["runner_sha256"])
            done, open_claims = receipts(manifest)
            rows = ledger()
            failures = sorted(s for s, r in done.items() if r["result"]["status"] == "error")
            require(not open_claims and failures)
            require(all(skippable(done[s]["result"], rows) for s in failures))
            save(
                RUN / "amendment-001.json",
                {
                    "decision": args.decision,
                    "base_runner_sha256": manifest["runner_sha256"],
                    "runner_sha256": expected["runner_sha256"],
                    "rule": AMENDMENT_RULE,
                    "reviewed_failures": failures,
                    "max_rejections": MAX_REJECTIONS,
                },
            )
            emit({"status": "AMENDED", "reviewed_failures": failures})
            return 0
        if args.command == "run":
            require(args.allow_live)
            RUN.mkdir(mode=0o700, parents=False, exist_ok=True)
            manifest_path = RUN / "manifest.json"
            if not manifest_path.exists():
                save(manifest_path, expected)
            manifest = read(manifest_path)
            change = verify(manifest, expected)
            fd = os.open(RUN / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                client = ProviderClient(
                    store=RuntimeStore(LEDGER),
                    quota=POLICY,
                    prices=PRICES,
                    api_key=load_groq_key(),
                    generation=GENERATION,
                    retries=RETRIES,
                    replay=ReplayPolicy(),
                )
                outcome = asyncio.run(dispatch(manifest, requests, client, change=change))
            emit({"status": outcome})
            return int(outcome != "finished")
        manifest = read(RUN / "manifest.json")
        verify(manifest, expected)
        value = report(manifest, bundle)
        PUBLIC.mkdir(exist_ok=True)
        path = PUBLIC / "report.json"
        if path.exists():
            path.unlink()  # Derived from immutable receipts; regenerated on demand.
        save(path, value)
        emit({k: value[k] for k in ("status", "provider_calls", "tokens")})
        emit(
            {
                s: {k: g[k] for k in ("answered", "correct", "statuses")}
                for s, g in value["strategies"].items()
            }
        )
        return 0
    except Exception as error:
        emit({"status": "STOP", "reason": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
