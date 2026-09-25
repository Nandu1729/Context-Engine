"""Separate receipt-bound qualification002 execution; never edits live001."""

import hashlib
import importlib.util
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from context_engine.answers import AnswerContract
from context_engine.config import BudgetConfig
from context_engine.errors import ContractError
from context_engine.evaluation.protocol import runtime_identity
from context_engine.models import Scope
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
PARENT_HASH = "d7839652e66d6c4c52dc3da398538fd2d2bf6b48c3cde6e1a9adf2a35dca57d9"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


if hashlib.sha256((ROOT / "scripts/c09_live.py").read_bytes()).hexdigest() != PARENT_HASH:
    raise ValueError("Parent runner drift")
live = module("c09_qualification_transport", "c09_live.py")
qualification = module("c09_qualification", "c09_qualification.py")
live.RUN = ROOT / "output/private/c09-qualification-live-002"
live.PROTOCOL = ROOT / "docs/C09_QUALIFICATION_LIVE_PROTOCOL.md"
live.SCOPE_VERSION = "c09-qualification-live-002"
live.prepare = qualification.prepare
original_pacing = live.pacing


def identity():
    live.configuration()
    live.require(
        hashlib.sha256((ROOT / "scripts/c09_live.py").read_bytes()).hexdigest() == PARENT_HASH
    )
    _, _, fixture = qualification.load()
    plan = live.prepare()
    live.require(plan["planned_slots"] == 32)
    live.require(plan["manifest_hash"] == qualification.fingerprint(fixture))
    return {
        "schema_version": 1,
        "id": live.SCOPE_VERSION,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parent_sha256": PARENT_HASH,
        "protocol_sha256": hashlib.sha256(live.PROTOCOL.read_bytes()).hexdigest(),
        "preparation": plan,
        "runtime": runtime_identity(),
        "generation": asdict(live.GENERATION),
        "retries": asdict(live.RETRIES),
        "replay": asdict(live.ReplayPolicy()),
        "quota": asdict(live.POLICY),
        "prices": asdict(live.PRICES),
        "provider_dependencies": live.dependency_profile(),
        "ledger_path": str(live.LEDGER),
        "max_calls": 32,
        "approval": "D080",
        "admission_input_multiplier": 1.8,
    }


def reconstruct(row):
    cases, _, _ = qualification.load()
    case = next(c for c in cases if c["id"] == row["case"])
    result = qualification.assemble(case, row["budget"], row["variant"], TiktokenCounter())
    live.require(live.fingerprint(result.request.to_wire()) == row["request_hash"])
    live.require(result.diagnostics.estimate.estimated_tokens == row["estimated_tokens"])
    return (
        result.request,
        BudgetConfig(input_cap=row["budget"], completion_reservation=256),
        Scope("c09-synthetic", case["id"]),
    )


def pacing(rows, reservation, now):
    # Admission-only safety margin; never rewrite engine estimates or ledger history.
    return original_pacing(rows, math.ceil(max(0, reservation - 256) * 1.8) + 256, now)


def report(manifest, account_rows):
    receipts, claims = live.inspect(manifest, account_rows)
    _, truth, _ = qualification.load()
    rows = []
    for i, plan in enumerate(manifest["preparation"]["rows"]):
        receipt = receipts.get(i)
        result = receipt["result"] if receipt else None
        completion = result["completion"] if result else None
        status = (
            result["status"]
            if result
            else "uncertain"
            if i in claims
            else "non_fit"
            if plan["status"] != "PREPARED"
            else "missing"
        )
        raw = completion["content"] if completion else ""
        parsed = None
        if completion:
            try:
                parsed = AnswerContract(plan["kind"]).parse(raw)
            except ContractError:
                pass
        expected = truth[plan["case"]]
        usage = completion["usage"] if completion else None
        success = status == "success"
        rows.append(
            {
                **plan,
                "status": status,
                "answer": raw if completion else None,
                "parsed_answer": parsed,
                "conforming": success and parsed is not None,
                "correct": success and parsed == expected["answer"],
                "correct_abstention": success and parsed == expected["answer"] == "UNKNOWN",
                "wrong_abstention": success
                and parsed == "UNKNOWN"
                and expected["answer"] != "UNKNOWN",
                "forbidden": any(
                    word.casefold() in raw.casefold()
                    or (parsed is not None and word.casefold() in parsed.casefold())
                    for word in expected["forbidden"]
                ),
                "usage": usage,
                "provider_input_overrun": usage is not None
                and usage["input_tokens"] > plan["budget"],
                "input_ratio": usage["input_tokens"] / plan["estimated_tokens"] if usage else None,
                "elapsed_seconds": receipt["elapsed_seconds"] if receipt else None,
            }
        )
    groups = []
    for budget in (900, 3000):
        for variant in ("CONTROL", "PRIMARY"):
            selected = [r for r in rows if r["budget"] == budget and r["variant"] == variant]
            group = {"budget": budget, "variant": variant, "planned": len(selected)}
            for field in (
                "correct",
                "conforming",
                "correct_abstention",
                "wrong_abstention",
                "forbidden",
            ):
                group[field] = sum(r[field] for r in selected)
            group.update(
                responded=sum(r["status"] == "success" for r in selected),
                input_overruns=sum(r["provider_input_overrun"] for r in selected),
                retained=sum(r["retained"] is True for r in selected),
                retention_eligible=sum(r["retained"] is not None for r in selected),
            )
            group["engineering_target"] = (
                "PASS"
                if group["correct"] == group["conforming"] == group["responded"] == 8
                and group["correct_abstention"] == 2
                and group["forbidden"] == group["input_overruns"] == 0
                else "FAIL"
            )
            groups.append(group)
    new = [r for r in account_rows if r["id"] not in manifest["baseline"]]
    usage = [json.loads(r["usage_json"]) for r in new if r["usage_json"]]
    complete = len(receipts) == len(rows)
    is_live = manifest["provenance"] == "LIVE"
    pairs = []
    for control in (r for r in rows if r["variant"] == "CONTROL"):
        primary = next(
            r
            for r in rows
            if r["case"] == control["case"]
            and r["budget"] == control["budget"]
            and r["variant"] == "PRIMARY"
        )
        pairs.append(
            {
                "case": control["case"],
                "budget": control["budget"],
                "control_correct": control["correct"],
                "primary_correct": primary["correct"],
                "correctness_delta": int(primary["correct"]) - int(control["correct"]),
            }
        )
    return {
        "schema_version": 1,
        "provenance": manifest["provenance"],
        "execution_id": live.fingerprint(manifest),
        "execution_identity": manifest,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "planned": len(rows),
        "claims": len(claims),
        "provider_attempts": len(new),
        "dispositions": dict(Counter(r["status"] for r in rows)),
        "known_input_tokens": sum(u["input_tokens"] for u in usage),
        "known_output_tokens": sum(u["output_tokens"] for u in usage),
        "unresolved_attempts": sum(r["state"] in live.ACTIVE for r in new),
        "configured_cost_microusd": sum(r["cost"] or 0 for r in new),
        "cost_uncertain": any(r["cost"] is None for r in new) or bool(claims - receipts.keys()),
        "answer_quality": "MEASURED_SYNTHETIC" if is_live and receipts else "NOT_EVALUATED",
        "quality_target": "NOT_EVALUATED"
        if not is_live
        else "INCOMPLETE"
        if not complete
        else "PASS"
        if all(g["engineering_target"] == "PASS" for g in groups if g["variant"] == "PRIMARY")
        else "FAIL",
        "groups": groups,
        "pairs": pairs,
        "rows": rows,
        "receipts": receipts,
        "caveat": "Author-visible synthetic comparison, not independent or owner acceptance.",
    }


live.identity = identity
live.reconstruct = reconstruct
live.pacing = pacing
live.report = report

if __name__ == "__main__":
    raise SystemExit(live.main())
