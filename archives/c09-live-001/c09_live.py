#!/usr/bin/env python3
"""One bounded C09 experiment. Default status is read-only; live needs --allow-live.

External runner: does not modify the frozen package, C06 journal or old artifacts.
The CLI has one fixed run/account identity, not caller-selected quota pools.
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
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from context_engine.budget import validate_request
from context_engine.config import BudgetConfig
from context_engine.evaluation.corpus import strict_json
from context_engine.evaluation.execution import dependency_profile
from context_engine.evaluation.heldout import engine_inputs, load, prepare
from context_engine.evaluation.heldout.scoring import contains, normalize
from context_engine.models import canonical_json
from context_engine.pipeline import AssemblyOptions, assemble_context
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
RUN = ROOT / "output/private/c09-live-001"
LEDGER = ROOT / "output/private/c06-live-account.sqlite"
CONFIG = ROOT / "output/private/c06-live-config.json"
PROTOCOL = ROOT / "docs/C09_LIVE_PROTOCOL.md"
MODEL = "openai/gpt-oss-20b"
SOURCE = "e65cb926df31f42d0f06a0c72c67f86860633ba56d00dbb075cf33b9f2ccfadf"
POLICY = QuotaPolicy(account_id="groq-personal-context-engine-v1", billing_mode="free_tier")
PRICES = PriceCard("owner-confirmed-free-2026-09-13", 0, 0, 0)
GENERATION = GenerationConfig(model=MODEL, max_completion_tokens=256)
RETRIES = RetryConfig(max_attempts=1, attempt_timeout=20, total_timeout=25)
SCOPE_VERSION = "c09-live-001"


def require(condition):
    if not condition:
        raise ValueError("C09 integrity/safety check failed; preserve evidence")


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def read(path):
    return strict_json(Path(path).read_text(), maximum=4_000_000)


def save(path, value):
    """Exclusive, durable evidence. A partial file fails closed on the next resume."""
    path = Path(path)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
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


def identity():
    configuration()
    plan = prepare(split="evaluation", retention=True)
    require(plan["planned_slots"] == 32 and plan["runtime"]["code_hash"] == SOURCE)
    return {
        "schema_version": 1,
        "id": SCOPE_VERSION,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "preparation": plan,
        "generation": asdict(GENERATION),
        "retries": asdict(RETRIES),
        "replay": asdict(ReplayPolicy()),
        "quota": asdict(POLICY),
        "prices": asdict(PRICES),
        "provider_dependencies": dependency_profile(),
        "ledger_path": str(LEDGER),
        "max_calls": 32,
        "approval": "D077",
    }


def initialize():
    manifest = identity()
    rows = ledger()
    require(not any(r["state"] in ACTIVE for r in rows))
    manifest["baseline"] = {r["id"]: fingerprint(r) for r in rows}
    manifest["provenance"] = "LIVE"
    RUN.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(RUN / "manifest.json", manifest)
    emit({"status": "FROZEN", "execution_id": fingerprint(manifest), "planned": 32})


def reconstruct(row):
    cases, _, protocol, _ = load()
    case = next(c for c in cases if c["id"] == row["case"])
    require(case["split"] == "evaluation")
    at = datetime.fromisoformat(protocol["evaluated_at"])
    history, pins, question = engine_inputs(case, at)
    budget = BudgetConfig(input_cap=row["budget"], completion_reservation=256)
    result = assemble_context(
        history,
        question,
        pins,
        budget,
        system=protocol["system"],
        at=at,
        options=AssemblyOptions(
            cap=row["variant"] != "WINDOW",
            retrieve=row["variant"] != "WINDOW",
            summarize=False,
        ),
    )
    require(fingerprint(result.request.to_wire()) == row["request_hash"])
    require(result.diagnostics.estimate.estimated_tokens == row["estimated_tokens"])
    return result.request, budget, pins.scope


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
    require({k: v for k, v in manifest.items() if k not in {"baseline", "provenance"}} == expected)
    require(manifest["provenance"] in {"LIVE", "TEST_ONLY"})
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
    require(len(claimed) <= 32 and len(used) + len(unmatched) <= 32)
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


async def dispatch(manifest, client, *, sleep=asyncio.sleep):
    execution_id = fingerprint(manifest)
    for i, row in enumerate(manifest["preparation"]["rows"]):
        waited = 0
        while True:
            rows = ledger()
            receipts, claims = inspect(manifest, rows)
            if claims - receipts.keys():
                return "unreceipted_claim"
            if any(r["result"]["status"] != "success" for r in receipts.values()):
                return "preserved_error"
            if i in receipts or row["status"] != "PREPARED":
                break
            state, delay = pacing(rows, row["estimated_tokens"] + 256, time.time())
            if state == "minute_wait" and waited + delay <= 300:
                emit({"status": state, "seconds": delay, "completed": len(receipts)})
                await sleep(delay)
                waited += delay
                continue
            if state != "ready":
                return state
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
            # Do not dispatch again until the receipt matches actual account settlement.
            inspect(manifest, ledger())
            emit({"status": result.status, "slot": i + 1, "planned": 32})
            if result.status != "success" or result.new_cost_microusd != 0:
                return "provider_error_or_unknown_usage"
            break
    return "finished"


def wilson(correct, total):
    z = 1.959963984540054
    p = correct / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return [max(0, center - width), min(1, center + width)]


def report(manifest, account_rows):
    receipts, claims = inspect(manifest, account_rows)
    new_attempts = [r for r in account_rows if r["id"] not in manifest["baseline"]]
    known_usage = [json.loads(r["usage_json"]) for r in new_attempts if r["usage_json"]]
    _, truth, _, _ = load()
    rows, groups = [], defaultdict(list)
    for i, plan in enumerate(manifest["preparation"]["rows"]):
        receipt = receipts.get(i)
        result = receipt["result"] if receipt else None
        completion = result["completion"] if result else None
        success = result is not None and result["status"] == "success"
        answer = completion["content"] if completion else None
        expected = truth[plan["case"]]
        usage = completion["usage"] if completion else None
        row = {k: plan[k] for k in ("case", "category", "split", "variant", "budget", "retained")}
        row.update(
            status=result["status"]
            if result
            else "uncertain"
            if i in claims
            else "non_fit"
            if plan["status"] != "PREPARED"
            else "missing",
            answer=answer,
            correct=success and normalize(answer) == normalize(expected["answer"]),
            forbidden=answer is not None
            and any(contains(answer, x) for x in expected["forbidden"]),
            usage=usage,
            estimated_input=plan["estimated_tokens"],
            provider_input_overrun=usage is not None and usage["input_tokens"] > plan["budget"],
            input_ratio=usage["input_tokens"] / plan["estimated_tokens"] if usage else None,
            elapsed_seconds=receipt["elapsed_seconds"] if receipt else None,
        )
        rows.append(row)
        groups[plan["variant"], plan["budget"]].append(row)
    summaries = []
    for (variant, budget), values in sorted(groups.items()):
        correct = sum(r["correct"] for r in values)
        summaries.append(
            {
                "variant": variant,
                "budget": budget,
                "planned": len(values),
                "correct": correct,
                "responded": sum(r["status"] == "success" for r in values),
                "forbidden": sum(r["forbidden"] for r in values),
                "retained": sum(r["retained"] is True for r in values),
                "retention_eligible": sum(r["retained"] is not None for r in values),
                "input_overruns": sum(r["provider_input_overrun"] for r in values),
                "wilson95_descriptive_only": wilson(correct, len(values)),
                "correctness_target": "PASS" if correct / len(values) >= 0.9 else "FAIL",
            }
        )
    complete = len(receipts) == len(rows)
    live = manifest["provenance"] == "LIVE"
    return {
        "schema_version": 1,
        "provenance": manifest["provenance"],
        "execution_id": fingerprint(manifest),
        "execution_identity": manifest,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "planned": len(rows),
        "claims": len(claims),
        "provider_attempts": len(new_attempts),
        "known_input_tokens": sum(u["input_tokens"] for u in known_usage),
        "known_output_tokens": sum(u["output_tokens"] for u in known_usage),
        "unresolved_attempts": sum(r["state"] in ACTIVE for r in new_attempts),
        "dispositions": dict(Counter(r["status"] for r in rows)),
        "answer_quality": "MEASURED_SYNTHETIC" if live and receipts else "NOT_EVALUATED",
        "quality_target": "NOT_EVALUATED"
        if not live
        else "INCOMPLETE"
        if not complete
        else "PASS"
        if all(g["correctness_target"] == "PASS" for g in summaries)
        else "FAIL",
        "forbidden_target": "NOT_EVALUATED"
        if not live
        else "FAIL"
        if any(r["forbidden"] for r in rows)
        else "PASS"
        if complete and all(r["status"] == "success" for r in rows)
        else "INCOMPLETE",
        "input_budget_target": "NOT_EVALUATED"
        if not live
        else "FAIL"
        if any(r["provider_input_overrun"] for r in rows)
        else "PASS"
        if complete and len(known_usage) == len(rows)
        else "INCOMPLETE",
        "configured_cost_microusd": sum(
            r["result"]["new_cost_microusd"] or 0 for r in receipts.values()
        ),
        "cost_uncertain": any(r["result"]["new_cost_microusd"] is None for r in receipts.values())
        or bool(claims - receipts.keys()),
        "groups": summaries,
        "rows": rows,
        "receipts": receipts,
        "caveat": "Author-visible synthetic smoke; no acceptance or population accuracy claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("init", "status", "run", "report"), default="status", nargs="?"
    )
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize()
            return 0
        require(RUN.is_dir() and not RUN.is_symlink())
        manifest = read(RUN / "manifest.json")
        if args.command == "run":
            require(args.allow_live and manifest["provenance"] == "LIVE")
            fd = os.open(RUN / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                inspect(manifest, ledger())
                # Explicit file wins; inherited stale keys never select another account.
                os.environ.pop("GROQ_API_KEY", None)
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
            require(args.output is not None)
            args.output.mkdir(parents=True, exist_ok=False)
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
                    "quality_target",
                )
            }
        )
        return 0
    except Exception:
        emit({"status": "STOP", "reason": "safety_or_integrity_check_failed_preserve_all_evidence"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
