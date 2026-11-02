#!/usr/bin/env python3
"""D125 proposal: the 1.0 confirmation run on every eligible LongMemEval-S question.

All 470 eligible questions (labelled evidence, no abstention), each in two 3000-token
arms: `new_default` calls `assemble_context` with no retrieval settings at all (the
0.18.0 defaults: 40% reserve, automatic top_k, one chunk per turn) and `old_default`
passes 0.17's defaults explicitly (280 reserve, top 4, diversity off). Claude Fable 5.1
answers (adaptive thinking, effort "high", 8192 tokens) and Claude Opus 5.5 judges with
the published LongMemEval prompts, as in D123, with stage B's system prompt.

The D123 runner's Claude settings and the stage B runner are reused, with settings
replaced in this process only. Call numbers: answers 0-939, their judges 940-1879. Own
ledger and run directory, one attempt per call, stops on any provider error except
confirmed zero-token `provider_rejected` (max 10) and up to 10 answers and 10 judge
replies with no text (`empty_response`; counted wrong / "no", never resent). The cap is
a spending limit: before every call, spent + that call's worst case (TOKEN_MARGIN on
input, the full output limit) must fit, so the run stops before it could pass the cap.
The all-calls worst case is far above the expected cost and is reported, not required to
fit. Reads only the ANTHROPIC_API_KEY line of .env. Commands: `plan` (offline),
`run --allow-live [--max-slots N]`, `peek`, `report`.
"""

import argparse
import asyncio
import collections
import fcntl
import hashlib
import importlib.util
import math
import os
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.models import KeyedPins
from context_engine.providers import transport as transport_module
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import QuotaPolicy, ReplayPolicy
from context_engine.providers.store import RuntimeStore


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = _load("longmemeval_claude_live")  # D123 runner: Claude settings, key and parsing.
b = c.b  # Its stage B runner instance, patched below.
base, d118, lme = b.base, b.d118, b.lme
require, emit, read, save, wilson = base.require, base.emit, base.read, base.save, base.wilson

RUN_ID = "longmemeval-v1-001"
LEDGER = b.ROOT / "output/private/longmemeval-d125-account.sqlite"
ARMS = {
    # None: automatic. `assemble` passes no retrieval settings at all for this arm.
    "new_default": {"budget": 3000, "reserve": None, "top_k": None, "diverse_turns": True},
    "old_default": {"budget": 3000, "reserve": 280, "top_k": 4, "diverse_turns": False},
}
QUESTIONS = 470
ANSWERS = QUESTIONS * len(ARMS)  # 940
MAX_CALLS = 2 * ANSWERS  # 1880: answers, then one judge call each.
TOTAL_CALLS = 2000
CAP_MICROUSD = 90_000_000  # $90 spending limit; expected about $47 at D123's usage.
ANSWER, JUDGE = c.ANSWER, c.JUDGE
ANSWER_PRICES, JUDGE_PRICES, TOKEN_MARGIN = c.ANSWER_PRICES, c.JUDGE_PRICES, c.TOKEN_MARGIN
POLICY = QuotaPolicy(
    account_id="anthropic-longmemeval-d125",
    daily_budget_microusd=CAP_MICROUSD,
    rpm=40,
    tpm=120_000,  # Estimated input + reserved output per minute.
    rpd=TOTAL_CALLS,
    tpd=40_000_000,
    billing_mode="metered",
)
# D123 averages per call (612 calls): answers 3906 input / 160 output tokens, judges
# 491 / 48. Used only for the plan's expected cost.
D123_ANSWER_TOKENS, D123_JUDGE_TOKENS = (3906, 160), (491, 48)

_assemble, _report, _pacing, build = b.assemble, b.report, b.pacing, b.build


def margin(tokens):
    return math.ceil(tokens * TOKEN_MARGIN)


def worst_answer(slot):
    return ANSWER_PRICES.reserve_cost(
        margin(slot["estimated_tokens"]), ANSWER.max_completion_tokens
    )


def worst_judge(input_tokens):
    return JUDGE_PRICES.reserve_cost(margin(input_tokens), JUDGE.max_completion_tokens)


def worst_total(slots):
    return sum(worst_answer(s) + worst_judge(s["judge_upper_bound_tokens"]) for s in slots)


def expected_total():
    answer = ANSWER_PRICES.reserve_cost(*D123_ANSWER_TOKENS)
    judge = JUDGE_PRICES.reserve_cost(*D123_JUDGE_TOKENS)
    return ANSWERS * (answer + judge)


def pacing(rows, estimated_tokens, completion_tokens, now):
    """Stage B pacing with this call's price card, token margin and this run's cap."""
    prices = JUDGE_PRICES if completion_tokens == JUDGE.max_completion_tokens else ANSWER_PRICES
    if any(r["state"] in b.ACTIVE or r["charged_tokens"] is None for r in rows):
        return "unsafe_account", 0
    worst = prices.reserve_cost(margin(estimated_tokens), completion_tokens)
    if sum(r["cost"] for r in rows) + worst > CAP_MICROUSD:
        return "cap_would_exceed", 0
    return _pacing(rows, estimated_tokens, completion_tokens, now)


def assemble(item, arm):
    """`new_default`: the SDK defaults, no retrieval settings passed. Others: stage B's."""
    if arm != "new_default":
        return _assemble(item, arm)
    turns, ordered = lme.history(item)
    budget = BudgetConfig(input_cap=3000, completion_reservation=ANSWER.max_completion_tokens)
    result = assemble_context(
        turns,
        item["question"],
        KeyedPins(lme.SCOPE),
        budget,
        system=b.SYSTEM.format(date=item["question_date"]),
        at=lme.parse_date(item["question_date"]),
    )
    return result, budget, ordered


def identity(slots):
    return {
        "id": RUN_ID,
        "approval": "D125 1.0 confirmation run",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "claude_runner_sha256": hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
        "stage_b_runner_sha256": hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest(),
        "code_hash": b.code_hash(),
        "dataset": {"file": lme.DATA.name, "revision": "98d7416c", "sha256": lme.SHA256},
        "seed": b.SEED,
        "arms": ARMS,
        "system": b.SYSTEM,
        "answer_generation": asdict(ANSWER),
        "judge_generation": asdict(JUDGE),
        "judge_source": b.JUDGE_SOURCE,
        "judge_templates": b.JUDGE_TEMPLATES,
        "retries": asdict(b.RETRIES),
        "quota": asdict(POLICY),
        "prices": {"answer": asdict(ANSWER_PRICES), "judge": asdict(JUDGE_PRICES)},
        "token_margin": TOKEN_MARGIN,
        "cap_microusd": CAP_MICROUSD,
        "max_calls": MAX_CALLS,
        "max_rejections": b.MAX_REJECTIONS,
        "slots": slots,
    }


def plan(questions, slots):
    rows = b.ledger()
    return {
        "status": "PLANNED",
        "seed": b.SEED,
        "questions": len(questions),
        "by_type": dict(sorted(collections.Counter(q["question_type"] for q in questions).items())),
        "answer_model": ANSWER.model,
        "judge_model": JUDGE.model,
        "arms": {
            arm: {
                "calls": sum(s["arm"] == arm for s in slots),
                "max_estimated_input_tokens": max(
                    s["estimated_tokens"] for s in slots if s["arm"] == arm
                ),
                "evidence_in_context": sum(s["evidence_any"] for s in slots if s["arm"] == arm),
                "needed_evidence_in_context": sum(
                    s["needed_evidence_in_context"] for s in slots if s["arm"] == arm
                ),
            }
            for arm in ARMS
        },
        "calls": MAX_CALLS,
        "call_limit": TOTAL_CALLS,
        "expected_microusd_at_d123_usage": expected_total(),
        "worst_case_all_calls_microusd": worst_total(slots),
        "cap_microusd": CAP_MICROUSD,
        "pacing": f"<= {POLICY.rpm} requests and {POLICY.tpm} tokens per rolling minute",
        "minimum_minutes": math.ceil(MAX_CALLS / POLICY.rpm),
        "ledger_rows": len(rows),
        "ledger_cost_so_far_microusd": sum(r["cost"] for r in rows),
        "run_exists": b.RUN.exists(),
    }


def no_previous_run():
    """No earlier run to pair with: report() pairs the two arms of this run instead."""
    return collections.defaultdict(lambda: dict.fromkeys(("strict-v1", "lenient-v2", "lenient-v3")))


def report(manifest, questions, contexts):
    # Stage B's report records ANSWER.temperature; Claude settings have none (not sent).
    b.ANSWER = SimpleNamespace(model=ANSWER.model, temperature=None)
    try:
        value, private, disagreements = _report(manifest, questions, contexts)
    finally:
        b.ANSWER = ANSWER
    for result in value["results"].values():
        result.pop("paired_vs_d118")
    graded = {
        (r["question_id"], r["arm"]): r
        for r in value["rows"]
        if "strict-v1" in r and r["status"] != "not_run"
    }
    paired = {}
    for name in ("judge", "lenient-v3"):
        counts = collections.Counter(
            (bool(graded[(q["question_id"], "old_default")][name]), bool(row[name]))
            for q in questions
            if (row := graded.get((q["question_id"], "new_default"))) is not None
            and (q["question_id"], "old_default") in graded
        )
        paired[name] = {
            "improved": counts[(False, True)],
            "regressed": counts[(True, False)],
            "both_right": counts[(True, True)],
            "both_wrong": counts[(False, False)],
        }
    value |= {
        "approval": "D125 1.0 confirmation run",
        "answer_model": ANSWER.model,
        "judge_model": JUDGE.model,
        "paired_new_vs_old_default": paired,
        "limitations": [
            "One run per arm; LongMemEval-S histories mix public chat logs with sessions "
            "simulated by the dataset authors (not real users' chats).",
            "The judge (Opus 5.5) is the same family as the Fable answers it grades; "
            "prompts written for GPT-4o; not human-checked.",
            "Temperature: API defaults (not sent). Budgets use a local token estimate; "
            "Claude counts tokens differently.",
            "D123's 95 questions are among these 470, so its run is not independent.",
        ],
    }
    return value, private, disagreements


def patch():
    """Point the stage B runner at this run's settings (this process only)."""
    settings = {
        "RUN_ID": RUN_ID,
        "RUN": b.ROOT / "output/private" / RUN_ID,
        "PUBLIC": b.ROOT / "output" / RUN_ID,
        "LEDGER": LEDGER,
        "ARMS": ARMS,
        "QUESTIONS": QUESTIONS,
        "ANSWERS": ANSWERS,
        "MAX_CALLS": MAX_CALLS,
        "TOTAL_CALLS": TOTAL_CALLS,
        "CAP_MICROUSD": CAP_MICROUSD,
        "POLICY": POLICY,
        "PRICES": ANSWER_PRICES,  # Only used by stage B's own (replaced) cost functions.
        "ANSWER": ANSWER,
        "JUDGE": JUDGE,
        "RUNTIME_RUNNER_SHA256": None,
        "D118_SETTING": {arm: arm for arm in ARMS},
        "d118_rows": no_previous_run,
        "accepted": c.accepted,
        "assemble": assemble,
        "identity": identity,
        "plan": plan,
        "report": report,
        "pacing": pacing,
        "worst_answer": worst_answer,
        "worst_judge": worst_judge,
        "worst_total": worst_total,
    }
    for name, value in settings.items():
        require(hasattr(b, name))
        setattr(b, name, value)


def main():
    patch()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("plan", "run", "peek", "report"), nargs="?", default="plan"
    )
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--max-slots", type=int)
    args = parser.parse_args()
    try:
        for prices in (ANSWER_PRICES, JUDGE_PRICES):
            POLICY.validate_prices(prices)
        questions, slots, requests, contexts = build()
        expected = identity(slots)
        items = {item["question_id"]: item for item in questions}
        if args.command == "plan":
            emit(plan(questions, slots))
            return 0
        if args.command == "run":
            require(args.allow_live)
            b.RUN.mkdir(mode=0o700, parents=False, exist_ok=True)
            manifest_path = b.RUN / "manifest.json"
            if not manifest_path.exists():
                save(manifest_path, expected)
            manifest = read(manifest_path)
            b.require_manifest(manifest, expected)
            fd = os.open(b.RUN / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                transport_module.parse_anthropic_message = c.capturing_parse  # This process.
                store, key = RuntimeStore(LEDGER), c.anthropic_key()
                clients = [
                    ProviderClient(
                        store=store,
                        quota=POLICY,
                        prices=prices,
                        api_key=key,
                        generation=generation,
                        retries=b.RETRIES,
                        replay=ReplayPolicy(),
                    )
                    for generation, prices in ((ANSWER, ANSWER_PRICES), (JUDGE, JUDGE_PRICES))
                ]
                outcome = asyncio.run(
                    b.dispatch(manifest, requests, items, clients, max_slots=args.max_slots)
                )
            emit({"status": outcome})
            return int(outcome not in ("finished", "paused"))
        manifest = read(b.RUN / "manifest.json")
        b.require_manifest(manifest, expected)
        if args.command == "peek":
            b.peek(manifest, questions, contexts)
            return 0
        value, private, disagreements = report(manifest, questions, contexts)
        b.PUBLIC.mkdir(exist_ok=True)
        for path, data in (
            (b.PUBLIC / "report.json", value),
            (b.RUN / "answers.json", private),
            (b.RUN / "judge-disagreements.json", disagreements),
        ):
            if path.exists():
                path.unlink()  # Derived from immutable receipts; regenerated on demand.
            save(path, data)
        emit({k: value[k] for k in ("status", "provider_calls", "list_price_cost_microusd")})
        return 0
    except Exception as error:
        emit({"status": "STOP", "reason": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
