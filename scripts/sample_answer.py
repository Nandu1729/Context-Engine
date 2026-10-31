"""D105 single authorized request; historical experiments and sample app stay offline."""

import argparse
import asyncio
import math
import os
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from context_engine.budget import validate_request
from context_engine.config import Settings
from context_engine.evaluation.execution import dependency_profile
from context_engine.evaluation.protocol import runtime_identity
from context_engine.inspection import load_job
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    ADAPTER_VERSION,
    ENDPOINT,
    Completion,
    ReplayPolicy,
    fingerprint,
)
from context_engine.providers.credentials import load_api_key
from context_engine.providers.store import ACTIVE, RuntimeStore
from context_engine.providers.transport import GroqTransport
from context_engine.tokens import TiktokenCounter
from scripts import longmemeval_live as safety
from scripts.incident_demo import offline_network

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output/private/sample-answer-001"
PROTOCOL = ROOT / "docs/C10_SAMPLE_ANSWER_PROTOCOL.md"
INPUT = safety.REVIEW / "row-049/input-baseline.json"
INPUT_HASH = "4798dc0fdb5174fb68efee364142c853fdb7ebcb207911e7bb74a9548f567fb5"
VERSION = "sample-answer-001"
require, read, save, file_hash = safety.require, safety.read, safety.save, safety.file_hash


def prepared():
    with offline_network():
        require(file_hash(INPUT) == INPUT_HASH)
        job = load_job(INPUT, Settings())
        result = job.run()
        saved = read(INPUT.with_name("assembly-baseline-900.json"))
        require(result.request.to_wire() == saved["request"])
        require(result.diagnostics.estimate.estimated_tokens == 892)
        require(job.arguments["budget"].input_cap == 900)
        require(job.arguments["budget"].completion_reservation == 256)
        require(not job.arguments["retrieval_config"].recover_capped_window)
        return result.request, job.arguments["budget"], job.arguments["pinned_facts"].scope


def identity():
    safety.configuration()
    require(file_hash(safety.SOURCE) == safety.SOURCE_HASH)
    split = read(safety.REVIEW / "split.json")
    require(any(r["row"] == 49 for r in split["partitions"]["development"]))
    require(all(r["row"] != 49 for r in split["partitions"]["heldout"]))
    request, budget, scope = prepared()
    files = [
        Path(__file__),
        PROTOCOL,
        Path(safety.__file__),
        ROOT / "scripts/incident_demo.py",
        INPUT,
        INPUT.with_name("assembly-baseline-900.json"),
        INPUT.with_name("labels-baseline.json"),
        safety.REVIEW / "split.json",
    ]
    return {
        "id": VERSION,
        "approval": "D105",
        "max_calls": 1,
        "files": {str(p.relative_to(ROOT)): file_hash(p) for p in files},
        "runtime": runtime_identity(),
        "dependencies": dependency_profile(),
        "request_hash": fingerprint(request.to_wire()),
        "budget": asdict(budget),
        "scope": asdict(scope),
        "generation": asdict(safety.GENERATION),
        "retries": asdict(safety.RETRIES),
        "quota": asdict(safety.POLICY),
        "prices": asdict(safety.PRICES),
        "replay": asdict(ReplayPolicy()),
        "ledger_path": str(safety.LEDGER),
        "estimated_tokens": 892,
    }


def request_key(manifest):
    request, budget, scope = prepared()
    return fingerprint(
        {
            "adapter": ADAPTER_VERSION,
            "endpoint": ENDPOINT,
            "payload": safety.GENERATION.to_wire(request),
            "account": safety.POLICY.account_id,
            "scope": asdict(scope),
            "security_scope": VERSION,
            "snapshot_revision": manifest["request_hash"],
            "policy_version": fingerprint(manifest),
            "budget": asdict(budget),
            "counting": validate_request(
                request=request, config=budget, counter=TiktokenCounter()
            ).to_dict(),
            "prices": asdict(safety.PRICES),
            "transport": GroqTransport().namespace,
        }
    )


def inspect(manifest, rows):
    require(
        {
            k: v
            for k, v in manifest.items()
            if k
            not in {
                "baseline",
                "model_preflight",
                "provenance",
            }
        }
        == identity()
    )
    require(manifest["provenance"] in {"LIVE", "TEST_ONLY"})
    preflight = manifest["model_preflight"]
    require(
        preflight["model"] == safety.MODEL
        and preflight["active"] is True
        and preflight["listed"] is True
    )
    attempts = {r["id"]: r for r in rows}
    require(
        all(
            k in attempts and fingerprint(attempts[k]) == h for k, h in manifest["baseline"].items()
        )
    )
    extra = {k: v for k, v in attempts.items() if k not in manifest["baseline"]}
    require(len(extra) <= 1)
    require(
        all(
            p.name in {"manifest.json", "runner.lock", "claim.json", "receipt.json"}
            and not p.is_symlink()
            for p in RUN.iterdir()
        )
    )
    claim_path, receipt_path = RUN / "claim.json", RUN / "receipt.json"
    if not claim_path.exists():
        require(not receipt_path.exists() and not extra)
        return "ready", None
    claim = read(claim_path)
    require(claim == {"execution_id": fingerprint(manifest), "request_key": request_key(manifest)})
    require(all(r["request_key"] == claim["request_key"] for r in extra.values()))
    if not receipt_path.exists():
        return "uncertain_do_not_resend", None
    receipt = read(receipt_path)
    require(set(receipt) == {"claim_hash", "result", "elapsed_seconds"})
    require(receipt["claim_hash"] == fingerprint(claim))
    require(
        type(receipt["elapsed_seconds"]) in (int, float)
        and math.isfinite(receipt["elapsed_seconds"])
        and receipt["elapsed_seconds"] >= 0
    )
    result = receipt["result"]
    require(result["request_key"] == claim["request_key"] and result["replay_of"] is None)
    require(result["content_included"] is True)
    require(result["status"] in {"success", "error", "truncated", "filtered", "tool_calls"})
    require(
        isinstance(result["attempt_ids"], list)
        and len(result["attempt_ids"]) == len(extra)
        and set(result["attempt_ids"]) == set(extra)
    )
    for attempt in extra.values():
        require(attempt["model"] == safety.MODEL and attempt["reserved_cost"] == 0)
        require(attempt["reserved_tokens"] == manifest["estimated_tokens"] + 256)
        require(safety.strict_json(attempt["price_json"]) == asdict(safety.PRICES))
    if result["completion"] is not None:
        completion = Completion.from_dict(result["completion"])
        require(len(extra) == 1 and completion.model == safety.MODEL)
        attempt = next(iter(extra.values()))
        require(attempt["completion_hash"] == fingerprint(completion.to_dict()))
        require(safety.strict_json(attempt["usage_json"]) == asdict(completion.usage))
        require(attempt["charged_tokens"] == completion.usage.total_tokens)
        require(attempt["cost"] == result["new_cost_microusd"] == 0)
        require(
            result["status"]
            == {
                "stop": "success",
                "length": "truncated",
                "content_filter": "filtered",
                "tool_calls": "tool_calls",
            }[completion.finish_reason]
        )
        require((attempt["state"] == "completed") == (result["status"] == "success"))
    else:
        require(result["status"] == "error")
    return "recorded_no_more_calls", receipt


@contextmanager
def run_lock():
    path = RUN / "runner.lock"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def client_check(client):
    require(type(client) is ProviderClient and client.store.path == safety.LEDGER)
    require(client.quota == safety.POLICY and client.prices == safety.PRICES)
    require(client.generation == safety.GENERATION and client.retries == safety.RETRIES)
    require(client.replay == ReplayPolicy())


async def dispatch(manifest, client):
    client_check(client)
    rows = safety.ledger()
    state, _ = inspect(manifest, rows)
    if state != "ready":
        return state
    reservation = math.ceil(manifest["estimated_tokens"] * 1.8) + 256
    state, _ = safety.pacing(rows, reservation, time.time())
    if state != "ready":
        return state
    request, budget, scope = prepared()
    claim = {"execution_id": fingerprint(manifest), "request_key": request_key(manifest)}
    save(RUN / "claim.json", claim)
    start = time.monotonic()
    result = await client.complete(
        request,
        budget,
        scope=scope,
        security_scope=VERSION,
        snapshot_revision=manifest["request_hash"],
        policy_version=fingerprint(manifest),
    )
    save(
        RUN / "receipt.json",
        {
            "claim_hash": fingerprint(claim),
            "result": result.to_dict(include_content=True),
            "elapsed_seconds": time.monotonic() - start,
        },
    )
    inspect(manifest, safety.ledger())
    return "recorded_no_more_calls"


def status(manifest, *, show_answer=False):
    rows = safety.ledger()
    state, receipt = inspect(manifest, rows)
    new = [r for r in rows if r["id"] not in manifest["baseline"]]
    result = receipt["result"] if receipt else None
    completion = result["completion"] if result else None
    value = {
        "status": state,
        "result_status": result["status"] if result else None,
        "planned_calls": 1,
        "provider_attempts": len(new),
        "usage": completion["usage"] if completion else None,
        "configured_cost_microusd": result["new_cost_microusd"] if result else None,
        "usage_uncertain": state == "uncertain_do_not_resend"
        or any(r["state"] in ACTIVE or r["charged_tokens"] is None for r in new),
        "input_cap_overrun": bool(completion and completion["usage"]["input_tokens"] > 900),
        "execution_id": fingerprint(manifest),
    }
    if show_answer and completion:
        value["answer"] = completion["content"]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "run", "status"))
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--show-answer", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            require(args.allow_live and not RUN.exists())
            frozen = identity()
            rows = safety.ledger()
            require(safety.pacing(rows, 1862, time.time())[0] == "ready")
            key = load_api_key(ROOT / ".env")
            preflight = asyncio.run(safety.model_preflight(key))
            require(0 <= time.time() - preflight["checked_at"] <= 300)
            require(rows == safety.ledger())
            frozen.update(
                baseline={r["id"]: fingerprint(r) for r in rows},
                model_preflight=preflight,
                provenance="LIVE",
            )
            RUN.mkdir(mode=0o700, parents=True, exist_ok=False)
            save(RUN / "manifest.json", frozen)
            safety.emit({"status": "FROZEN", "max_calls": 1, "execution_id": fingerprint(frozen)})
            return 0
        require(RUN.is_dir() and not RUN.is_symlink())
        manifest = read(RUN / "manifest.json")
        if args.command == "run":
            require(args.allow_live and manifest["provenance"] == "LIVE")
            with run_lock():
                state, _ = inspect(manifest, safety.ledger())
                if state == "ready":
                    require(0 <= time.time() - manifest["model_preflight"]["checked_at"] <= 300)
                    client = ProviderClient(
                        store=RuntimeStore(safety.LEDGER),
                        quota=safety.POLICY,
                        prices=safety.PRICES,
                        api_key=load_api_key(ROOT / ".env"),
                        generation=safety.GENERATION,
                        retries=safety.RETRIES,
                        replay=ReplayPolicy(),
                    )
                    state = asyncio.run(dispatch(manifest, client))
                safety.emit({"status": state})
        safety.emit(status(manifest, show_answer=args.show_answer))
        return 0
    except Exception:
        safety.emit({"status": "STOP", "reason": "safety_check_failed_preserve_evidence"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
