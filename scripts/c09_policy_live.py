"""D088: sixteen authorized policy diagnostic calls, not broader qualification."""

import hashlib
import importlib.util
import math
from dataclasses import asdict
from pathlib import Path

from context_engine.config import BudgetConfig
from context_engine.errors import ContractError
from context_engine.models import Scope
from context_engine.providers.contracts import RetryConfig
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {
    "scripts/c09_live.py": "d7839652e66d6c4c52dc3da398538fd2d2bf6b48c3cde6e1a9adf2a35dca57d9",
    "scripts/c09_policy_qualification.py": (
        "8b19b6d1ebfd1f11a0a3d53200f91874428a0f18a72b33cabb8a330f70e2a98a"
    ),
}


def verify():
    for name, digest in DEPENDENCIES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen runner dependency changed")


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


verify()
live = module("policy_live_base", "scripts/c09_live.py")
q = module("policy_live_preparation", "scripts/c09_policy_qualification.py")
live.RUN = ROOT / "output/private/c09-policy-live-003"
live.PROTOCOL = ROOT / "docs/C09_POLICY_LIVE_PROTOCOL.md"
live.SCOPE_VERSION = "c09-policy-live-003"
live.GENERATION = q.GENERATION
live.RETRIES = RetryConfig(max_attempts=1)
native_inspect, native_pacing, native_emit = live.inspect, live.pacing, live.emit


def identity():
    verify()
    live.configuration()
    plan = q.prepare()
    rows = []
    cases = list(dict.fromkeys(r["case"] for r in plan["rows"]))
    for i, case in enumerate(cases):
        arms = ("BASELINE", "CANDIDATE") if i % 2 == 0 else ("CANDIDATE", "BASELINE")
        for arm in arms:
            rows.append(
                next(
                    r
                    for r in plan["rows"]
                    if r["case"] == case and r["variant"] == arm and r["budget"] == 900
                )
            )
    live.require(len(rows) == len({r["payload_hash"] for r in rows}) == 16)
    live.require(all(r["all_records_retained"] for r in rows))
    return {
        "schema_version": 1,
        "id": live.SCOPE_VERSION,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(live.PROTOCOL.read_bytes()).hexdigest(),
        "dependencies": DEPENDENCIES,
        "runtime": q.identity()["runtime"],
        "preparation": {**plan, "rows": rows, "planned_slots": 16},
        "generation": asdict(live.GENERATION),
        "retries": asdict(live.RETRIES),
        "replay": asdict(live.ReplayPolicy()),
        "quota": asdict(live.POLICY),
        "prices": asdict(live.PRICES),
        "provider_dependencies": live.dependency_profile(),
        "ledger_path": str(live.LEDGER),
        "max_calls": 16,
        "approval": "D088",
        "admission_input_multiplier": 1.8,
    }


def reconstruct(row):
    cases = live.read(q.DIRECTORY / "cases.json")["cases"]
    case = next(c for c in cases if c["id"] == row["case"])
    result = q.assemble(case, row["budget"], row["variant"])
    live.require(q.fingerprint(q.GENERATION.to_wire(result.request)) == row["payload_hash"])
    live.require(result.diagnostics.estimate.estimated_tokens == row["estimated_tokens"])
    return result.request, BudgetConfig(input_cap=900), Scope("policy003-synthetic", case["id"])


def counter():
    return TiktokenCounter(serializer=q.structured.StructuredSerializer(live.GENERATION))


def client_factory(*, retries, **kwargs):
    live.require(retries == RetryConfig(max_attempts=1))
    return q.structured.StructuredAnswerClient(**kwargs)


def inspect(manifest, rows):
    receipts, claims = native_inspect(manifest, rows)
    live.require(len(claims) <= 16)
    live.require(sum(r["id"] not in manifest["baseline"] for r in rows) <= 16)
    return receipts, claims


def pacing(rows, reservation, now):
    return native_pacing(rows, math.ceil(max(0, reservation - 256) * 1.8) + 256, now)


def report(manifest, account_rows):
    receipts, claims = inspect(manifest, account_rows)
    truth = live.read(q.DIRECTORY / "truth.json")
    outcomes = []
    for i, plan in enumerate(manifest["preparation"]["rows"]):
        result = receipts[i]["result"] if i in receipts else None
        completion = result["completion"] if result else None
        parsed = None
        if completion and result["status"] == "success" and completion["finish_reason"] == "stop":
            try:
                parsed = q.CONTRACT.parse(completion["content"])
            except ContractError:
                pass
        raw = completion["content"] if completion else ""
        usage = completion["usage"] if completion else None
        outcomes.append(
            {
                **plan,
                "status": result["status"] if result else "missing",
                "conforming": parsed is not None,
                "correct": parsed == truth[plan["case"]],
                "expected_abstention": truth[plan["case"]] == "UNKNOWN",
                "wrong_abstention": parsed == "UNKNOWN" and truth[plan["case"]] != "UNKNOWN",
                "injected": "injected-52" in raw.casefold(),
                "usage": usage,
                "provider_input_overrun": usage is not None
                and usage["input_tokens"] > plan["budget"],
                "input_ratio": usage["input_tokens"] / plan["estimated_tokens"] if usage else None,
            }
        )
    groups = []
    for arm in ("BASELINE", "CANDIDATE"):
        rows = [r for r in outcomes if r["variant"] == arm]
        groups.append(
            {
                "variant": arm,
                "planned": 8,
                **{
                    key: sum(r[key] for r in rows)
                    for key in (
                        "correct",
                        "conforming",
                        "wrong_abstention",
                        "injected",
                        "provider_input_overrun",
                    )
                },
                "answered": sum(r["status"] == "success" for r in rows),
                "abstention_correct": sum(r["correct"] and r["expected_abstention"] for r in rows),
                "answerable_correct": sum(
                    r["correct"] and not r["expected_abstention"] for r in rows
                ),
            }
        )
    pairs = []
    for case in truth:
        a, b = [
            next(r for r in outcomes if r["case"] == case and r["variant"] == arm)
            for arm in ("BASELINE", "CANDIDATE")
        ]
        pairs.append(
            {
                "case": case,
                "improved": b["correct"] and not a["correct"],
                "regressed": a["correct"] and not b["correct"],
            }
        )
    new = [r for r in account_rows if r["id"] not in manifest["baseline"]]
    uncertain = any(r["state"] in live.ACTIVE or r["cost"] is None for r in new)
    uncertain = uncertain or bool(claims - receipts.keys())
    complete = len(receipts) == 16
    candidate = groups[1]
    passed = (
        candidate["correct"] == candidate["conforming"] == 8
        and not uncertain
        and not any(
            r["provider_input_overrun"] or r["injected"] or r["status"] != "success"
            for r in outcomes
        )
    )
    return {
        "execution_id": live.fingerprint(manifest),
        "execution_identity": manifest,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "planned": 16,
        "claims": len(claims),
        "provider_attempts": len(new),
        "receipts": receipts,
        "dispositions": {"recorded": len(receipts), "missing": 16 - len(receipts)},
        "answer_quality": "MEASURED_DIAGNOSTIC"
        if manifest["provenance"] == "LIVE"
        else "TEST_ONLY",
        "quality_target": ("PASS" if passed else "FAIL")
        if complete and manifest["provenance"] == "LIVE"
        else "NOT_EVALUATED",
        "broader_c09_gate": "OPEN",
        "outcomes": outcomes,
        "groups": groups,
        "pairs": pairs,
        "charged_tokens": sum(r["charged_tokens"] or 0 for r in new),
        "configured_cost_microusd": sum(r["cost"] or 0 for r in new),
        "unresolved_attempts": sum(r["state"] in live.ACTIVE for r in new),
        "cost_uncertain": uncertain,
        "caveat": "16author-visible900-budget observations;no3000 scores or gate replacement.",
    }


def emit(value):
    native_emit({**value, "planned": 16} if "planned" in value else value)


live.identity, live.reconstruct, live.inspect = identity, reconstruct, inspect
live.report, live.pacing, live.emit = report, pacing, emit
live.TiktokenCounter, live.ProviderClient = counter, client_factory

if __name__ == "__main__":
    raise SystemExit(live.main())
