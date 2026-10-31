#!/usr/bin/env python3
"""D100: a fixed 14-call LongMemEval development comparison, never a benchmark pass.

Portable safety routines adapted from the unchanged c09_live.py. No historical
runner is imported, executed, or re-frozen. The public CLI fixes account and paths.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import sqlite3
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import httpx

from context_engine.budget import validate_request
from context_engine.config import BudgetConfig
from context_engine.evaluation.corpus import strict_json
from context_engine.evaluation.execution import dependency_profile
from context_engine.evaluation.protocol import runtime_identity
from context_engine.models import ChatRequest, Message, Scope, canonical_json
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    ADAPTER_VERSION,
    ENDPOINT,
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
from context_engine.providers.transport import GroqTransport
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "output/private/longmemeval-review-001"
RUN = ROOT / "output/private/longmemeval-live-001"
LEDGER = ROOT / "output/private/c06-live-account.sqlite"
CONFIG = ROOT / "output/private/c06-live-config.json"
PROTOCOL = ROOT / "docs/C10_LONGMEMEVAL_LIVE_PROTOCOL.md"
SOURCE = Path("/Users/nandyyy/Downloads/longmemeval_s_cleaned.json")
SOURCE_HASH = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
PLAN_HASH = "2fac0e0f7b2b32f7aa6b7d9c76384c432a41d146e09ad1d3cabf0f456759123e"
SPLIT_HASH = "aab5693329fa716acd05621b4d791e508779c6e80471e22e94021d6537229279"
MODEL = "openai/gpt-oss-20b"
POLICY = QuotaPolicy(account_id="groq-personal-context-engine-v1", billing_mode="free_tier")
PRICES = PriceCard("owner-confirmed-free-2026-09-13", 0, 0, 0)
GENERATION = GenerationConfig(model=MODEL, max_completion_tokens=256)
RETRIES = RetryConfig(max_attempts=1, attempt_timeout=20, total_timeout=25)
BUDGET = BudgetConfig(input_cap=3000, completion_reservation=256, summary_reserve=0)
SCOPE_VERSION = "longmemeval-live-001"
SEED = "longmemeval-live-development-v1"
CATEGORIES = (
    "abstention",
    "knowledge-update",
    "multi-session",
    "single-session-assistant",
    "single-session-preference",
    "single-session-user",
    "temporal-reasoning",
)


def require(condition):
    if not condition:
        raise ValueError("LongMemEval integrity/safety check failed; preserve evidence")


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def read(path):
    require(not Path(path).is_symlink())
    return strict_json(Path(path).read_text(encoding="utf-8"), maximum=4_000_000)


def save(path, value):
    """Exclusive, durable evidence. A partial file fails closed on the next resume."""
    path = Path(path)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    if os.name == "posix":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def configuration():
    data = strict_json(private_bytes(CONFIG, 65536).decode(), maximum=65536)
    require(set(data) == {"quota", "prices", "ledger_path", "max_run_cost_microusd"})
    require(data["quota"] == asdict(POLICY))
    require(data["prices"][MODEL] == asdict(PRICES))
    require(data["max_run_cost_microusd"] == 0)
    require(Path(data["ledger_path"]).absolute() == LEDGER)
    POLICY.validate_prices(PRICES)


def ledger():
    """Read-only, all-account inspection; no private contents are printed."""
    require(LEDGER.is_file() and not LEDGER.is_symlink())
    db = sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        accounts = db.execute("SELECT * FROM accounts").fetchall()
        require(len(accounts) == 1 and json.loads(accounts[0]["policy"]) == asdict(POLICY))
        require(accounts[0]["account"] == fingerprint(POLICY.account_id))
        require(time.time() + 5 >= accounts[0]["last_clock"])
        rows = [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY id")]
        for row in rows:
            RuntimeStore._validate_row(row)
            require(row["account"] == accounts[0]["account"])
        return rows
    finally:
        db.close()


def file_hash(path):
    require(path.is_file() and not path.is_symlink())
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def select(split, runs):
    """Category coverage, then hash order; no labels, scores or answer quality."""
    candidates = split["partitions"]["development"]
    heldout = {r["row"] for r in split["partitions"]["heldout"]}
    require(len({r["row"] for r in candidates}) == len(candidates))
    require(not heldout.intersection(r["row"] for r in candidates))
    chosen = []
    for category in CATEGORIES:
        eligible = []
        for item in candidates:
            if item["category"] != category:
                continue
            matches = [
                r
                for r in runs
                if r["row"] == item["row"]
                and r["budget"] == 3000
                and r["arm"] in {"dated", "dated_recovery"}
                and r["partition"] == "development"
            ]
            require(
                len(matches) == 2 and {r["arm"] for r in matches} == {"dated", "dated_recovery"}
            )
            require(all(r["category"] == category and r["status"] == "ASSEMBLED" for r in matches))
            if not any(r["source_flags"]["sessions_after_question"] for r in matches):
                eligible.append(item)
        require(eligible)
        chosen.append(
            min(eligible, key=lambda r: (fingerprint([SEED, r["question_id"]]), r["row"]))
        )
    require(len({r["row"] for r in chosen}) == 7)
    return chosen


def preparation():
    plan, split, report = [read(REVIEW / f"{name}.json") for name in ("plan", "split", "report")]
    require(fingerprint(plan) == PLAN_HASH == report["plan_sha256"])
    require(split["split_sha256"] == SPLIT_HASH == plan["split_sha256"])
    require(fingerprint({k: v for k, v in split.items() if k != "split_sha256"}) == SPLIT_HASH)
    require(plan["source_sha256"] == SOURCE_HASH and plan["runtime"] == runtime_identity())
    require(report["heldout_assembled"] == report["heldout_scored"] == 0)
    for name, expected in plan["scripts"].items():
        require(file_hash(ROOT / "scripts" / name) == expected)
    chosen = select(split, report["runs"])
    files = {
        f"{name}.json": file_hash(REVIEW / f"{name}.json") for name in ("plan", "split", "report")
    }
    rows = []
    for i, item in enumerate(chosen):
        arms = ("dated", "dated_recovery") if i % 2 == 0 else ("dated_recovery", "dated")
        for arm in arms:
            relative = f"row-{item['row']:03d}"
            names = {
                kind: f"{relative}/{kind}-{arm}" + ("-3000" if kind == "assembly" else "") + ".json"
                for kind in ("assembly", "input", "labels")
            }
            for name in names.values():
                files[name] = file_hash(REVIEW / name)
            wire = read(REVIEW / names["assembly"])["request"]
            prior = next(
                r
                for r in report["runs"]
                if r["row"] == item["row"] and r["arm"] == arm and r["budget"] == 3000
            )
            require(fingerprint(wire) == prior["request_sha256"])
            row = {
                **item,
                "variant": arm,
                "budget": 3000,
                "status": "PREPARED",
                "estimated_tokens": prior["estimated_tokens"],
                "request_hash": fingerprint(wire),
                "paths": names,
                "source_flags": prior["source_flags"],
                "coverage": prior["coverage"],
            }
            reconstruct(row)
            rows.append(row)
    require(len(rows) == 14)
    return {
        "planned_slots": 14,
        "rows": rows,
        "files": files,
        "selection_seed": SEED,
        "heldout_used": 0,
        "split_sha256": SPLIT_HASH,
    }


def reconstruct(row):
    wire = read(REVIEW / row["paths"]["assembly"])["request"]
    require(set(wire) == {"messages"})
    require(all(set(m) == {"role", "content"} for m in wire["messages"]))
    request = ChatRequest(
        tuple(Message(f"m{i}", m["role"], m["content"]) for i, m in enumerate(wire["messages"]))
    )
    require(request.to_wire() == wire and fingerprint(wire) == row["request_hash"])
    estimate = validate_request(request=request, config=BUDGET, counter=TiktokenCounter())
    require(estimate.estimated_tokens == row["estimated_tokens"] <= 3000)
    # Opaque scope uses only the public question ID, never evaluator labels.
    scope = Scope("longmemeval-demo", hashlib.sha256(row["question_id"].encode()).hexdigest()[:24])
    return request, BUDGET, scope


def identity():
    configuration()
    return {
        "schema_version": 1,
        "id": SCOPE_VERSION,
        "approval": "D100",
        "max_calls": 14,
        "runner_sha256": file_hash(Path(__file__)),
        "protocol_sha256": file_hash(PROTOCOL),
        "runtime": runtime_identity(),
        "preparation": preparation(),
        "generation": asdict(GENERATION),
        "retries": asdict(RETRIES),
        "replay": asdict(ReplayPolicy()),
        "quota": asdict(POLICY),
        "prices": asdict(PRICES),
        "provider_dependencies": dependency_profile(),
        "ledger_path": str(LEDGER),
        "admission_input_multiplier": 1.8,
    }


def request_key(row, execution_id):
    request, budget, scope = reconstruct(row)
    return fingerprint(
        {
            "adapter": ADAPTER_VERSION,
            "endpoint": ENDPOINT,
            "payload": GENERATION.to_wire(request),
            "account": POLICY.account_id,
            "scope": asdict(scope),
            "security_scope": SCOPE_VERSION,
            "snapshot_revision": fingerprint(row),
            "policy_version": execution_id,
            "budget": asdict(budget),
            "counting": validate_request(
                request=request, config=budget, counter=TiktokenCounter()
            ).to_dict(),
            "prices": asdict(PRICES),
            "transport": GroqTransport().namespace,
        }
    )


def inspect(manifest, rows):
    """Bind saved claims/receipts to the original plan and actual account ledger."""
    expected = identity()
    require(
        {
            k: v
            for k, v in manifest.items()
            if k not in {"baseline", "provenance", "model_preflight"}
        }
        == expected
    )
    require(manifest["provenance"] in {"LIVE", "TEST_ONLY"})
    preflight = manifest["model_preflight"]
    require(
        preflight["model"] == MODEL and preflight["active"] is True and preflight["listed"] is True
    )
    attempts = {r["id"]: r for r in rows}
    require(
        all(
            k in attempts and fingerprint(attempts[k]) == v for k, v in manifest["baseline"].items()
        )
    )
    execution_id = fingerprint(manifest)
    receipts, claimed, used = {}, set(), set()
    planned = manifest["preparation"]["rows"]
    allowed = {"manifest.json", "runner.lock"}
    for i, row in enumerate(planned):
        claim_path, receipt_path = RUN / f"claim-{i:02d}.json", RUN / f"receipt-{i:02d}.json"
        allowed.update({claim_path.name, receipt_path.name})
        if not claim_path.exists():
            require(not receipt_path.exists())
            continue
        require(row["status"] == "PREPARED")
        claim = read(claim_path)
        require(
            claim
            == {
                "execution_id": execution_id,
                "slot": i,
                "request_key": request_key(row, execution_id),
            }
        )
        claimed.add(i)
        if not receipt_path.exists():
            continue  # Report incomplete; dispatch refuses any unreceipted claim.
        receipt = read(receipt_path)
        require(set(receipt) == {"claim_hash", "result", "elapsed_seconds"})
        require(receipt["claim_hash"] == fingerprint(claim))
        require(
            type(receipt["elapsed_seconds"]) in (float, int)
            and math.isfinite(receipt["elapsed_seconds"])
            and receipt["elapsed_seconds"] >= 0
        )
        result = receipt["result"]
        require(result["request_key"] == claim["request_key"])
        require(result["content_included"] is True and result["replay_of"] is None)
        require(result["status"] in {"success", "error", "truncated", "tool_calls", "filtered"})
        ids = result["attempt_ids"]
        require(isinstance(ids, list) and len(ids) <= 1)
        require(not (set(ids) & (used | set(manifest["baseline"]))))
        require(all(k in attempts for k in ids))
        used.update(ids)
        for k in ids:
            attempt = attempts[k]
            require(attempt["request_key"] == claim["request_key"] and attempt["model"] == MODEL)
            require(json.loads(attempt["price_json"]) == asdict(PRICES))
            require(attempt["reserved_tokens"] == row["estimated_tokens"] + 256)
            require(attempt["reserved_cost"] == 0)
        if result["completion"] is not None:
            completion = Completion.from_dict(result["completion"])
            require(len(ids) == 1 and completion.model == MODEL)
            attempt = attempts[ids[0]]
            require(attempt["completion_hash"] == fingerprint(completion.to_dict()))
            require(json.loads(attempt["usage_json"]) == asdict(completion.usage))
            require(attempt["charged_tokens"] == completion.usage.total_tokens)
            require(attempt["cost"] == result["new_cost_microusd"] == 0)
            require((result["status"] == "success") == (completion.finish_reason == "stop"))
            require((attempt["state"] == "completed") == (result["status"] == "success"))
        else:
            require(result["status"] == "error")
        receipts[i] = receipt
    require(all(p.name in allowed and not p.is_symlink() for p in RUN.iterdir()))
    # Unknown extra account traffic cannot be attributed to this experiment.
    unmatched = set(attempts) - set(manifest["baseline"]) - used
    unresolved_keys = {request_key(planned[i], execution_id) for i in claimed - receipts.keys()}
    require(all(attempts[k]["request_key"] in unresolved_keys for k in unmatched))
    require(len(claimed) <= 14 and len(used) + len(unmatched) <= 14)
    return receipts, claimed


def pacing(rows, reservation, now):
    if any(r["state"] in ACTIVE or r["cost"] != 0 or r["charged_tokens"] is None for r in rows):
        return "unsafe_account", 0
    if not 0 < reservation <= POLICY.tpm:
        return "unserviceable_reservation", 0

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


async def model_preflight(key, *, transport=None):
    """Read-only model-list check, no redirects/retries and no response-body logging."""
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        async with client.stream(
            "GET",
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": "Bearer " + key},
        ) as response:
            require(response.status_code == 200)
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                require(len(data) <= 1_000_000)
    result = strict_json(data.decode("utf-8"), maximum=1_000_000)
    matches = [m for m in result["data"] if m.get("id") == MODEL]
    require(len(matches) == 1 and matches[0].get("active") is True)
    return {"model": MODEL, "listed": True, "active": True, "checked_at": time.time()}


def initialize(preflight):
    require(
        preflight["model"] == MODEL and preflight["active"] is True and preflight["listed"] is True
    )
    require(0 <= time.time() - preflight["checked_at"] <= 300)
    require(file_hash(SOURCE) == SOURCE_HASH)
    manifest = identity()
    rows = ledger()
    require(pacing(rows, 5656, time.time())[0] in {"ready", "minute_wait"})
    manifest.update(
        baseline={r["id"]: fingerprint(r) for r in rows},
        provenance="LIVE",
        model_preflight=preflight,
    )
    RUN.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(RUN / "manifest.json", manifest)
    emit({"status": "FROZEN", "execution_id": fingerprint(manifest), "planned": 14})


@contextmanager
def run_lock():
    # Exclusive creation works without importing POSIX-only modules. A crash leaves
    # a stale lock: fail closed; do not automatically remove or reset it on resume.
    path = RUN / "runner.lock"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def client_check(client):
    require(type(client) is ProviderClient and client.quota == POLICY and client.prices == PRICES)
    require(client.generation == GENERATION and client.retries == RETRIES)
    require(client.replay == ReplayPolicy() and client.store.path == LEDGER)


async def dispatch(manifest, client, *, sleep=asyncio.sleep):
    client_check(client)
    execution_id = fingerprint(manifest)
    for i, row in enumerate(manifest["preparation"]["rows"]):
        waited = 0
        while True:
            rows = ledger()
            receipts, claims = inspect(manifest, rows)
            if claims - receipts.keys():
                return "unreceipted_claim"
            if any(r["result"]["status"] == "error" for r in receipts.values()):
                return "preserved_error"
            if i in receipts:
                break
            reservation = math.ceil(row["estimated_tokens"] * 1.8) + 256
            state, delay = pacing(rows, reservation, time.time())
            if state == "minute_wait" and waited + delay <= 300:
                emit({"status": state, "seconds": delay, "recorded": len(receipts)})
                await sleep(delay)
                waited += delay
                continue
            if state != "ready":
                return state
            client_check(client)
            request, budget, scope = reconstruct(row)
            claim = {
                "execution_id": execution_id,
                "slot": i,
                "request_key": request_key(row, execution_id),
            }
            save(RUN / f"claim-{i:02d}.json", claim)
            start = time.monotonic()
            result = await client.complete(
                request,
                budget,
                scope=scope,
                security_scope=SCOPE_VERSION,
                snapshot_revision=fingerprint(row),
                policy_version=execution_id,
            )
            save(
                RUN / f"receipt-{i:02d}.json",
                {
                    "claim_hash": fingerprint(claim),
                    "result": result.to_dict(include_content=True),
                    "elapsed_seconds": time.monotonic() - start,
                },
            )
            inspect(manifest, ledger())
            emit(
                {
                    "status": result.status,
                    "slot": i + 1,
                    "planned": 14,
                    "nonempty": bool(result.completion and result.completion.content.strip()),
                }
            )
            if result.status == "error" or result.new_cost_microusd != 0:
                return "provider_error_or_unknown_usage"
            break
    return "finished"


def report(manifest, account_rows):
    receipts, claims = inspect(manifest, account_rows)
    new = [r for r in account_rows if r["id"] not in manifest["baseline"]]
    outcomes = []
    for i, row in enumerate(manifest["preparation"]["rows"]):
        receipt = receipts.get(i)
        result = receipt["result"] if receipt else None
        completion = result["completion"] if result else None
        answer = completion["content"] if completion else None
        truth = read(REVIEW / row["paths"]["labels"])["answer"]
        usage = completion["usage"] if completion else None
        success = bool(result and result["status"] == "success")
        outcomes.append(
            {
                "slot": i,
                "row": row["row"],
                "question_id": row["question_id"],
                "category": row["category"],
                "variant": row["variant"],
                "status": result["status"]
                if result
                else ("uncertain" if i in claims else "not_attempted"),
                "answer": answer,
                "reference_answer": truth,
                "nonempty": bool(success and answer and answer.strip()),
                "literal_exact_match": bool(success and answer == str(truth)),
                "semantic_review": "PENDING",
                "coverage": row["coverage"],
                "estimated_input_tokens": row["estimated_tokens"],
                "usage": usage,
                "provider_input_overrun": usage is not None and usage["input_tokens"] > 3000,
                "elapsed_seconds": receipt["elapsed_seconds"] if receipt else None,
            }
        )
    groups = []
    for variant in ("dated", "dated_recovery"):
        group = [r for r in outcomes if r["variant"] == variant]
        groups.append(
            {
                "variant": variant,
                "planned": 7,
                **{
                    k: sum(r[k] for r in group)
                    for k in ("nonempty", "literal_exact_match", "provider_input_overrun")
                },
            }
        )
    return {
        "execution_id": fingerprint(manifest),
        "provenance": manifest["provenance"],
        "status": "COMPLETE" if len(receipts) == 14 else "INCOMPLETE",
        "planned": 14,
        "claims": len(claims),
        "provider_attempts": len(new),
        "dispositions": dict(Counter(r["status"] for r in outcomes)),
        "input_tokens": sum(r["usage"]["input_tokens"] for r in outcomes if r["usage"]),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in outcomes if r["usage"]),
        "charged_tokens": sum(r["charged_tokens"] or 0 for r in new),
        "configured_cost_microusd": sum(r["cost"] or 0 for r in new),
        "unresolved_attempts": sum(r["state"] in ACTIVE for r in new),
        "usage_uncertain": any(r["charged_tokens"] is None or r["state"] in ACTIVE for r in new)
        or bool(claims - receipts.keys()),
        "source_unchanged": file_hash(SOURCE) == SOURCE_HASH,
        "heldout_used": 0,
        "answer_quality": "DEVELOPMENT_OBSERVATIONS"
        if manifest["provenance"] == "LIVE"
        else "TEST_ONLY",
        "official_benchmark_score": "NOT_EVALUATED",
        "independent_review": "PENDING",
        "groups": groups,
        "outcomes": outcomes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "status", "run", "report"))
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            require(args.allow_live and not RUN.exists())
            configuration()
            key = load_api_key(ROOT / ".env")
            initialize(asyncio.run(model_preflight(key)))
            return 0
        require(RUN.is_dir() and not RUN.is_symlink())
        manifest = read(RUN / "manifest.json")
        if args.command == "run":
            require(args.allow_live and manifest["provenance"] == "LIVE")
            with run_lock():
                receipts, claims = inspect(manifest, ledger())
                if len(receipts) == 14:
                    emit({"status": "finished", "additional_calls": 0})
                    return 0
                require(not (claims - receipts.keys()))
                require(file_hash(SOURCE) == SOURCE_HASH)
                key = load_api_key(ROOT / ".env")
                client = ProviderClient(
                    store=RuntimeStore(LEDGER),
                    quota=POLICY,
                    prices=PRICES,
                    api_key=key,
                    generation=GENERATION,
                    retries=RETRIES,
                    replay=ReplayPolicy(),
                )
                outcome = asyncio.run(dispatch(manifest, client))
                emit({"status": outcome})
                return int(outcome != "finished")
        value = report(manifest, ledger())
        if args.command == "report":
            require(args.output is not None and not args.output.exists())
            args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
            save(args.output / "report.json", value)
        emit(
            {
                k: value[k]
                for k in (
                    "status",
                    "planned",
                    "claims",
                    "provider_attempts",
                    "dispositions",
                    "charged_tokens",
                    "unresolved_attempts",
                    "usage_uncertain",
                )
            }
        )
        return 0
    except Exception:
        emit({"status": "STOP", "reason": "safety_or_integrity_failure_preserve_all_evidence"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
