#!/usr/bin/env python3
"""One bounded free-tier Groq run: reworded questions, keyword vs hybrid retrieval (D114).

900 tokens; strategies `combined` (keyword, default) and `combined_semantic` (hybrid,
Model2Vec potion-base-8M); 31 reworded questions each (max 62 calls); gpt-oss-20b,
256 completion tokens, no retries, no paid usage. Confirmed zero-token
`provider_rejected` 4xx are terminal failed slots (D110 rule, max 10); rate limits,
uncertain errors or any cost stop the run. Reuses the safety helpers of
`strategy_accuracy_live.py`. Needs the [semantic] and [provider] extras.
Commands: `plan` (offline), `run --allow-live`, `report`.
"""

import argparse
import asyncio
import fcntl
import hashlib
import importlib.util
import os
import time
from dataclasses import asdict
from pathlib import Path

from context_engine.budget import validate_request
from context_engine.evaluation.corpus import aliases, load_bundle
from context_engine.evaluation.grading import answer_correct
from context_engine.evaluation.protocol import code_hash, load_freeze
from context_engine.evaluation.strategies import assemble_strategy, load_paraphrases
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, ReplayPolicy, fingerprint
from context_engine.providers.store import RuntimeStore
from context_engine.tokens import TiktokenCounter

_spec = importlib.util.spec_from_file_location(
    "strategy_accuracy_live", Path(__file__).with_name("strategy_accuracy_live.py")
)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

ROOT = base.ROOT
RUN_ID = "semantic-accuracy-900-001"
RUN = ROOT / "output/private" / RUN_ID
PUBLIC = ROOT / "output" / RUN_ID
STRATEGIES = ("combined", "combined_semantic")
MAX_CALLS = 62
MAX_REJECTIONS = 10
require, emit, read, save = base.require, base.emit, base.read, base.save


def build(embedder):
    require(load_freeze()["runtime"]["code_hash"] == code_hash())
    bundle = load_bundle()
    questions = load_paraphrases(bundle)
    counter = TiktokenCounter()
    slots, requests = [], []
    for fact in bundle.facts:
        for strategy in STRATEGIES:
            result, budget = assemble_strategy(
                bundle,
                fact,
                base.BUDGET,
                strategy,
                question=questions[fact["fact_id"]],
                embedder=embedder,
            )
            require(budget.completion_reservation == base.GENERATION.max_completion_tokens)
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


def identity(slots, embedder_name):
    return {
        "id": RUN_ID,
        "approval": "D114",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "base_runner_sha256": base.runner_hash(),
        "code_hash": code_hash(),
        "model": base.MODEL,
        "budget": base.BUDGET,
        "question_set": "paraphrased",
        "embedder": embedder_name,
        "generation": asdict(base.GENERATION),
        "retries": asdict(base.RETRIES),
        "quota": asdict(base.POLICY),
        "max_calls": MAX_CALLS,
        "max_rejections": MAX_REJECTIONS,
        "slots": slots,
    }


def receipts(manifest):
    done, open_claims = {}, []
    execution = fingerprint(manifest)
    for slot in manifest["slots"]:
        claim = RUN / f"claim-{slot['slot']:03d}.json"
        receipt = RUN / f"receipt-{slot['slot']:03d}.json"
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


async def dispatch(manifest, requests, client, *, sleep=asyncio.sleep):
    execution = fingerprint(manifest)
    for slot, (request, budget, scope) in zip(manifest["slots"], requests, strict=True):
        done, open_claims = receipts(manifest)
        if open_claims:
            return "unreceipted_claim"
        errors = [r["result"] for r in done.values() if r["result"]["status"] == "error"]
        if errors:
            rows = base.ledger()
            if not all(base.skippable(e, rows) for e in errors):
                return "preserved_error"
            if len(errors) > MAX_REJECTIONS:
                return "too_many_rejections"
        if slot["slot"] in done:
            continue
        waited = 0
        while True:
            state, delay = base.pacing(base.ledger(), slot["estimated_tokens"] + 256, time.time())
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
            if base.skippable(result.to_dict(), base.ledger()):
                continue
            return f"stopped_{result.error_code}"
        if result.new_cost_microusd != 0:
            return "stopped_unknown_or_nonzero_cost"
    return "finished"


def report(manifest, bundle):
    done, open_claims = receipts(manifest)
    facts = {f["fact_id"]: f for f in bundle.facts}
    groups = {s: {"planned": 31, "answered": 0, "correct": 0, "rejected": 0} for s in STRATEGIES}
    tokens = {"input": 0, "output": 0, "reasoning": 0, "estimated_input": 0}
    rows = []
    for slot in manifest["slots"]:
        if slot["slot"] not in done:
            continue
        result = done[slot["slot"]]["result"]
        group = groups[slot["strategy"]]
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
    for group in groups.values():
        group["accuracy_of_answered"] = (
            round(group["correct"] / group["answered"], 4) if group["answered"] else None
        )
        group["wilson95_of_answered"] = base.wilson(group["correct"], group["answered"])
        group["accuracy_of_planned"] = round(group["correct"] / group["planned"], 4)
    return {
        "id": RUN_ID,
        "status": "COMPLETE" if len(done) == MAX_CALLS else "PARTIAL",
        "provider_calls": sum(len(r["result"]["attempt_ids"]) for r in done.values()),
        "unreceipted_claims": len(open_claims),
        "model": base.MODEL,
        "budget": base.BUDGET,
        "question_set": "paraphrased",
        "embedder": manifest["embedder"],
        "strategies": groups,
        "tokens": tokens,
        "rows": rows,
        "limitations": [
            "One synthetic scenario; reworded questions written by the engine author.",
            "Strict grading: only the exact value (or one-field JSON) counts as correct.",
            "Single run, temperature 0, one model; no retries.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "report"), nargs="?", default="plan")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    try:
        from context_engine.embeddings import Model2VecEmbedder

        base.configuration()
        embedder = Model2VecEmbedder()
        bundle, slots, requests = build(embedder)
        expected = identity(slots, embedder.name)
        if args.command == "plan":
            rows = base.ledger()
            now = time.time()
            day = int(now // 86400) * 86400
            today = [r for r in rows if (r["settled"] or r["created"]) >= day]
            emit(
                {
                    "status": "PLANNED",
                    "calls": len(slots),
                    "max_estimated_input_tokens": max(s["estimated_tokens"] for s in slots),
                    "reserved_tokens_total": sum(s["estimated_tokens"] + 256 for s in slots),
                    "account_tokens_used_today_utc": sum(r["charged_tokens"] or 0 for r in today),
                    "tpd": base.POLICY.tpd,
                    "account_state": base.pacing(rows, 1, now)[0],
                    "embedder": embedder.name,
                    "run_exists": RUN.exists(),
                }
            )
            return 0
        if args.command == "run":
            require(args.allow_live)
            RUN.mkdir(mode=0o700, parents=False, exist_ok=True)
            manifest_path = RUN / "manifest.json"
            if not manifest_path.exists():
                save(manifest_path, expected)
            manifest = read(manifest_path)
            require(manifest == expected)
            fd = os.open(RUN / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                client = ProviderClient(
                    store=RuntimeStore(base.LEDGER),
                    quota=base.POLICY,
                    prices=base.PRICES,
                    api_key=base.load_groq_key(),
                    generation=base.GENERATION,
                    retries=base.RETRIES,
                    replay=ReplayPolicy(),
                )
                outcome = asyncio.run(dispatch(manifest, requests, client))
            emit({"status": outcome})
            return int(outcome != "finished")
        manifest = read(RUN / "manifest.json")
        require(manifest == expected)
        value = report(manifest, bundle)
        PUBLIC.mkdir(exist_ok=True)
        path = PUBLIC / "report.json"
        if path.exists():
            path.unlink()  # Derived from immutable receipts; regenerated on demand.
        save(path, value)
        emit({k: value[k] for k in ("status", "provider_calls", "tokens")})
        emit(
            {
                s: {k: g[k] for k in ("answered", "correct", "rejected")}
                for s, g in value["strategies"].items()
            }
        )
        return 0
    except Exception as error:
        emit({"status": "STOP", "reason": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
