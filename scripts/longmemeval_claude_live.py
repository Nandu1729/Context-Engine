#!/usr/bin/env python3
"""D123 proposal: a second model family and an outside judge on LongMemEval-S.

Claude Fable 5.1 (the strongest listed model; adaptive thinking, effort "high", 8192
output tokens so thinking is not cut off) answers stage B's 95 questions (seed 118) in
its two 3000-token arms with stage B's system prompt; the contexts are byte-identical
to the mercury-3 ones. Claude Opus 5.5 (adaptive thinking, effort "medium", 2048
tokens, the published LongMemEval judge prompts) judges every Fable answer and
re-judges every stage B mercury-3 answer that has text. Both models are then graded
by the same judge, from another family than mercury-3, and the mercury judge can be
checked against it.

The stage B runner is reused with its settings replaced in this process only. Call
numbers: answers 0-189, their judges 190-379, re-judges 380-664 (stage B slot order;
none for stage B answers without text). Own ledger and run directory, one attempt per
call, stops on any provider error except confirmed zero-token `provider_rejected`
(max 10) and up to 10 answers and 10 judge replies with no text (`empty_response`;
counted wrong / "no", never resent), and before any call that could exceed the cap.
Worst cases add TOKEN_MARGIN because Claude's tokenizer may count more tokens than the
local estimate. Reads only the ANTHROPIC_API_KEY line of .env. Commands: `plan`
(offline), `run --allow-live [--max-slots N]`, `peek`, `report`.
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

from context_engine.providers import transport as transport_module
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    AnthropicGenerationConfig,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    TransportFailure,
)
from context_engine.providers.store import RuntimeStore


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = _load("longmemeval_accuracy_live_b")  # D119 stage B runner, patched below.
base, d118, lme, smoke = b.base, b.d118, b.lme, b.smoke
require, emit, read, save, wilson = base.require, base.emit, base.read, base.save, base.wilson

RUN_ID = "longmemeval-claude-001"
LEDGER = b.ROOT / "output/private/longmemeval-d123-account.sqlite"
STAGE_B_PUBLIC = b.ROOT / "output/longmemeval-accuracy-b-001/report.json"
STAGE_B_RUN = b.RUN  # Before patch(): stage B's private run directory.
STAGE_B_ANSWERS = b.ANSWERS  # 285
ARMS = {arm: b.ARMS[arm] for arm in ("core_default", "chatmemory_default")}
QUESTIONS = 95
ANSWERS = QUESTIONS * len(ARMS)  # 190
JUDGES = 2 * ANSWERS  # Calls 190-379 judge the Fable answers.
MAX_CALLS = JUDGES + STAGE_B_ANSWERS  # 665; re-judges are 380-664.
TOTAL_CALLS = 700
CAP_MICROUSD = 130_000_000  # $130 of the owner's $200 credit; covers the worst case.
TOKEN_MARGIN = 1.5
ANSWER = AnthropicGenerationConfig(
    model="claude-fable-5-1", max_completion_tokens=8192, thinking="adaptive", effort="high"
)
JUDGE = AnthropicGenerationConfig(
    model="claude-opus-5-5", max_completion_tokens=2048, thinking="adaptive", effort="medium"
)
# Published prices (USD per 1M tokens: input / cache hit / output), platform.claude.com
# pricing page read 2026-11-02.
ANSWER_PRICES = PriceCard("anthropic-claude-fable-5-1-2026-11-02", 10_000_000, 250_000, 50_000_000)
JUDGE_PRICES = PriceCard("anthropic-claude-opus-5-5-2026-11-02", 4_000_000, 200_000, 20_000_000)
POLICY = QuotaPolicy(
    account_id="anthropic-longmemeval-d123",
    daily_budget_microusd=CAP_MICROUSD,
    rpm=20,
    tpm=60_000,  # Estimated input + reserved output per minute; gentle on rate limits.
    rpd=TOTAL_CALLS,
    tpd=3_000_000,
    billing_mode="metered",
)
EMPTY = "empty_response"

_accepted, _call, _report = b.accepted, b.call, b.report


def accepted(number, result):
    """Stage B's accepted-error rule, for the 0.17.1+ code of a reply with no text."""
    if result["error_code"] == EMPTY:
        result = result | {"error_code": "invalid_response"}
    return _accepted(number, result)


def margin(tokens):
    return math.ceil(tokens * TOKEN_MARGIN)


def worst_answer(slot):
    return ANSWER_PRICES.reserve_cost(
        margin(slot["estimated_tokens"]), ANSWER.max_completion_tokens
    )


def worst_judge(input_tokens):
    return JUDGE_PRICES.reserve_cost(margin(input_tokens), JUDGE.max_completion_tokens)


def stage_b_slots():
    """Stage B's answer slots (public report rows, same order as its call numbers)."""
    rows = read(STAGE_B_PUBLIC)["rows"]
    require([r["slot"] for r in rows] == list(range(STAGE_B_ANSWERS)))
    return rows


def worst_total(slots):
    rejudges = [r for r in stage_b_slots() if rejudge_input_bound(r) is not None]
    return sum(worst_answer(s) + worst_judge(s["judge_upper_bound_tokens"]) for s in slots) + sum(
        worst_judge(rejudge_input_bound(r)) for r in rejudges
    )


_ITEMS = {}


def rejudge_input_bound(row):
    """Judge input bound for a stage B answer with text (None: nothing to judge)."""
    if row["status"] != "success" or row.get("out_of_tokens") or row.get("accepted_error"):
        return None
    return b.judge_upper_bound(_ITEMS[row["question_id"]])


def pacing(rows, estimated_tokens, completion_tokens, now):
    """Stage B pacing with this call's own price card and token margin. Answers and
    judges are told apart by their output limit (8192 vs 2048)."""
    prices = JUDGE_PRICES if completion_tokens == JUDGE.max_completion_tokens else ANSWER_PRICES
    if any(r["state"] in b.ACTIVE or r["charged_tokens"] is None for r in rows):
        return "unsafe_account", 0
    worst = prices.reserve_cost(margin(estimated_tokens), completion_tokens)
    if sum(r["cost"] for r in rows) + worst > CAP_MICROUSD:
        return "cap_would_exceed", 0
    return _pacing(rows, estimated_tokens, completion_tokens, now)


_pacing = b.pacing


def stage_b_reply(slot):
    """Stage B's mercury-3 answer text for one of its slots, or None."""
    receipt = STAGE_B_RUN / f"receipt-{slot:03d}.json"
    if not receipt.exists():
        return None
    completion = b.content(read(receipt))
    return None if completion is None else completion.content


def call(number, manifest, requests, items, done):
    if number < JUDGES:
        return _call(number, manifest, requests, items, done)
    row = stage_b_slots()[number - JUDGES]
    reply = stage_b_reply(row["slot"])
    if reply is None:
        return None, None, None, None, None
    request, budget, estimate = b.judge_request(items[row["question_id"]], reply)
    return JUDGE, request, budget, estimate, b.fingerprint(request.to_wire())


def build():
    require(b.load_freeze()["runtime"]["code_hash"] == b.code_hash())
    questions = d118.sample(d118.eligible(d118.load_items()), QUESTIONS, b.SEED)
    require(len(questions) == QUESTIONS)
    _ITEMS.clear()
    _ITEMS.update({q["question_id"]: q for q in questions})
    slots, requests, contexts = [], [], []
    for item in questions:
        for arm in ARMS:
            result, budget, ordered = b.assemble(item, arm)
            estimate = b.validate_request(request=result.request, config=budget, counter=b.COUNTER)
            diagnostics = result.diagnostics
            found = set(diagnostics.kept_turn_ids) | set(diagnostics.retrieved_turn_ids)
            needed = ordered[-1:] if item["question_type"] == "knowledge-update" else ordered
            slots.append(
                {
                    "slot": len(slots),
                    "kind": "answer",
                    "question_id": item["question_id"],
                    "type": item["question_type"],
                    "arm": arm,
                    "estimated_tokens": estimate.estimated_tokens,
                    "judge_upper_bound_tokens": b.judge_upper_bound(item),
                    "evidence_any": bool(set(ordered) & found),
                    "needed_evidence_in_context": set(needed) <= found,
                    "request_hash": b.fingerprint(result.request.to_wire()),
                }
            )
            requests.append((result.request, budget))
            contexts.append("\n".join(m.content for m in result.request.messages))
    require(len(slots) == ANSWERS)
    return questions, slots, requests, contexts


def identity(slots):
    return {
        "id": RUN_ID,
        "approval": "D123 Claude Fable answers, Opus judge",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
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
        "stage_b_rows_sha256": hashlib.sha256(STAGE_B_PUBLIC.read_bytes()).hexdigest(),
        "slots": slots,
    }


def stage_b_rows():
    """Stage B grades per (question, arm), keyed like D118 rows for the paired table."""
    return {(r["question_id"], r["arm"]): r for r in stage_b_slots() if r["arm"] in ARMS}


def plan(questions, slots):
    rejudges = [r for r in stage_b_slots() if rejudge_input_bound(r) is not None]
    value = {
        "status": "PLANNED",
        "seed": b.SEED,
        "questions": len(questions),
        "answer_model": ANSWER.model,
        "judge_model": JUDGE.model,
        "arms": {
            arm: {
                "calls": sum(s["arm"] == arm for s in slots),
                "max_estimated_input_tokens": max(
                    s["estimated_tokens"] for s in slots if s["arm"] == arm
                ),
                "worst_case_microusd": sum(worst_answer(s) for s in slots if s["arm"] == arm),
            }
            for arm in ARMS
        },
        "judge_fable_answers": {
            "calls": len(slots),
            "worst_case_microusd": sum(worst_judge(s["judge_upper_bound_tokens"]) for s in slots),
        },
        "rejudge_stage_b_answers": {
            "calls": len(rejudges),
            "by_arm": dict(sorted(collections.Counter(r["arm"] for r in rejudges).items())),
            "worst_case_microusd": sum(worst_judge(rejudge_input_bound(r)) for r in rejudges),
        },
        "calls_max": len(slots) * 2 + len(rejudges),
        "call_limit": TOTAL_CALLS,
        "token_margin": TOKEN_MARGIN,
        "worst_case_total_microusd": worst_total(slots),
        "cap_microusd": CAP_MICROUSD,
        "minimum_minutes": -(-(len(slots) * 2 + len(rejudges)) // POLICY.rpm),
        "ledger_rows": len(b.ledger()),
        "ledger_cost_so_far_microusd": sum(r["cost"] for r in b.ledger()),
        "run_exists": b.RUN.exists(),
    }
    manifest = STAGE_B_RUN / "manifest.json"  # Private; absent on other machines.
    if manifest.exists():
        hashes = {(s["question_id"], s["arm"]): s["request_hash"] for s in read(manifest)["slots"]}
        value["same_contexts_as_stage_b"] = sum(
            hashes[(s["question_id"], s["arm"])] == s["request_hash"] for s in slots
        )
    value["stage_b_replies_found"] = sum(stage_b_reply(r["slot"]) is not None for r in rejudges)
    return value


def report(manifest, questions, contexts):
    # Stage B's report records ANSWER.model and ANSWER.temperature; Claude settings have
    # no temperature (not sent), so it sees a stand-in for the duration of the call.
    b.ANSWER = SimpleNamespace(model=ANSWER.model, temperature=None)
    try:
        value, private, disagreements = _report(manifest, questions, contexts)
    finally:
        b.ANSWER = ANSWER
    done, _ = b.receipts(manifest)
    previous = stage_b_rows()
    outside_on_stage_b = {}
    for row in stage_b_slots():
        number = JUDGES + row["slot"]
        if number in done:
            outside_on_stage_b[row["slot"]] = b.judged(done[number], number)
    for arm, result in value["results"].items():
        result.pop("paired_vs_d118")
        mine = [r for r in value["rows"] if r["arm"] == arm and "strict-v1" in r]
        outside_mercury = {
            r["question_id"]: outside_on_stage_b.get(r["slot"])
            for r in stage_b_slots()
            if r["arm"] == arm
        }
        # Same question, same arm, same outside judge: Fable vs mercury-3. A mercury
        # answer without text (not re-judged) counts as wrong, as in stage B.
        counts = collections.Counter(
            (bool(outside_mercury[r["question_id"]]), bool(r["judge"])) for r in mine
        )
        result["paired_vs_mercury_same_judge"] = {
            "improved": counts[(False, True)],
            "regressed": counts[(True, False)],
            "both_right": counts[(True, True)],
            "both_wrong": counts[(False, False)],
        }
        lenient = collections.Counter(
            (bool(previous[(r["question_id"], arm)]["lenient-v3"]), bool(r["lenient-v3"]))
            for r in mine
        )
        result["paired_vs_mercury_lenient_v3"] = {
            "improved": lenient[(False, True)],
            "regressed": lenient[(True, False)],
        }
    rejudge = {}
    for arm in b.ARMS_STAGE_B:
        rows = [r for r in stage_b_slots() if r["arm"] == arm]
        judged = [r for r in rows if outside_on_stage_b.get(r["slot"]) is not None]
        both = collections.Counter(
            (bool(r["judge"]), bool(outside_on_stage_b[r["slot"]])) for r in judged
        )
        outside_correct = sum(bool(outside_on_stage_b.get(r["slot"])) for r in rows)
        rejudge[arm] = {
            "rejudged": len(judged),
            "outside_judge": {
                "correct": outside_correct,
                "of": len(rows),
                "wilson95": wilson(outside_correct, len(rows)),
            },
            "mercury_judge_correct": sum(bool(r["judge"]) for r in rows),
            "agree": both[(True, True)] + both[(False, False)],
            "mercury_yes_outside_no": both[(True, False)],
            "mercury_no_outside_yes": both[(False, True)],
            "outside_vs_lenient_v3_agree": sum(
                bool(outside_on_stage_b[r["slot"]]) == bool(r["lenient-v3"]) for r in judged
            ),
        }
    needed = sum(stage_b_reply(r["slot"]) is not None for r in stage_b_slots())
    value |= {
        "approval": "D123 Claude Fable answers, Opus judge",
        "answer_model": ANSWER.model,
        "judge_model": JUDGE.model,
        "stage_b_rejudge": rejudge,
        "rejudge_status": "COMPLETE" if len(outside_on_stage_b) == needed else "PARTIAL",
        "list_price_cost_microusd": sum(
            r["result"]["new_cost_microusd"] or 0 for r in done.values()
        ),
        "limitations": [
            "95 of 470 eligible LongMemEval-S questions; one run per model.",
            "Histories mix public chat logs with sessions simulated by the dataset authors.",
            "The judge (Opus 5.5) is the same family as the Fable answers it grades, and a "
            "different family from mercury-3; prompts written for GPT-4o; not human-checked.",
            "Temperature: API defaults (Claude, not sent) vs 0.5 (mercury-3).",
            "Fable thought adaptively (effort high, 8192 tokens); mercury-3 used reasoning "
            "'low' with 1024 tokens: model and thinking budget both differ.",
            "Budgets use a local token estimate; Claude counts tokens differently.",
        ],
    }
    return value, private, disagreements


CAPTURE_ORIGINAL = transport_module.parse_anthropic_message


def capturing_parse(raw, expected_model):
    """Diagnostic only: save the raw body (never headers or the key) of a response that
    fails parsing, then fail exactly as before."""
    try:
        return CAPTURE_ORIGINAL(raw, expected_model)
    except TransportFailure:
        path = b.CAPTURE["path"]
        if path is not None and not path.exists():
            path.write_bytes(raw)
            path.chmod(0o600)
        raise


def anthropic_key(env_file=b.ROOT / ".env"):
    """Read only the ANTHROPIC_API_KEY line; never print it."""
    lines = smoke.private_bytes(env_file, 8192).decode("ascii").splitlines()
    values = [
        line.partition("=")[2].strip().strip("\"'")
        for line in lines
        if line.strip().partition("=")[0].strip() == "ANTHROPIC_API_KEY"
    ]
    if len(values) != 1 or not values[0] or any(c.isspace() for c in values[0]):
        raise ValueError("Missing or invalid ANTHROPIC_API_KEY; value is never displayed")
    return values[0]


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
        "d118_rows": stage_b_rows,
        "accepted": accepted,
        "build": build,
        "identity": identity,
        "plan": plan,
        "report": report,
        "call": call,
        "pacing": pacing,
        "worst_answer": worst_answer,
        "worst_judge": worst_judge,
        "worst_total": worst_total,
    }
    b.ARMS_STAGE_B = dict(b.ARMS)
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
        if args.command in ("plan", "run") and not (b.RUN / "manifest.json").exists():
            require(sum(r["cost"] for r in b.ledger()) + worst_total(slots) <= CAP_MICROUSD)
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
                transport_module.parse_anthropic_message = capturing_parse  # This process only.
                store, key = RuntimeStore(LEDGER), anthropic_key()
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
        emit(
            {
                k: value[k]
                for k in ("status", "rejudge_status", "provider_calls", "list_price_cost_microusd")
            }
        )
        return 0
    except Exception as error:
        emit({"status": "STOP", "reason": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
