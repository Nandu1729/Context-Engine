#!/usr/bin/env python3
"""D121 proposal: does a larger output limit fix out-of-tokens date answers?

In D119 stage B, 33 of 43 answers that used all 1024 completion tokens on thinking
were temporal-reasoning questions. This run repeats every temporal-reasoning question
of stage B's 95 (26) in its two 3000-token arms with 2048 completion tokens. All else
is stage B: seed 118, system prompt, reasoning "low", temperature 0.5, mercury-3 judge
with the published LongMemEval prompts, one attempt per call. Each answer is paired
with its own stage B answer, so the output limit is the only change.

The stage B runner is reused with its settings replaced in this process only. Own
ledger and run directory; stops on any provider error except confirmed zero-token
`provider_rejected` (max 10) and up to 10 answers and 10 judge replies with no text
(`empty_response`, 0.17.1; counted wrong / "no", never resent), and before any call
that could exceed the cap. Commands: `plan` (offline), `run --allow-live
[--max-slots N]`, `peek`, `report`. Answers stay under output/private/.
"""

import collections
import hashlib
import importlib.util
import sys
from dataclasses import asdict, replace
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = _load("longmemeval_accuracy_live_b")  # D119 stage B runner, patched below.
base, d118, lme = b.base, b.d118, b.lme
require, read, wilson = base.require, base.read, base.wilson

RUN_ID = "longmemeval-temporal-tokens-001"
LEDGER = b.ROOT / "output/private/longmemeval-d121-account.sqlite"
STAGE_B = b.ROOT / "output/longmemeval-accuracy-b-001/report.json"
STAGE_B_RUN = b.RUN  # Before patch(): stage B's private run directory.
QUESTION_TYPE = "temporal-reasoning"
ARMS = {arm: b.ARMS[arm] for arm in ("core_default", "chatmemory_default")}
STAGE_B_QUESTIONS = 95
QUESTIONS = 26  # Temporal-reasoning questions among stage B's 95.
ANSWERS = QUESTIONS * len(ARMS)  # 52
MAX_CALLS = 2 * ANSWERS  # 104 = answers + one judge call each.
TOTAL_CALLS = 110
CAP_MICROUSD = 70_000  # Worst case 65,266 at list price.
ANSWER = replace(b.ANSWER, max_completion_tokens=2048)
EMPTY = "empty_response"  # A reply with no text (D120); stage B saw it as invalid_response.

_accepted = b.accepted


def accepted(number, result):
    """Stage B's accepted-error rule, for the 0.17.1 code of a reply with no text."""
    if result["error_code"] == EMPTY:
        result = result | {"error_code": "invalid_response"}
    return _accepted(number, result)


def build():
    require(b.load_freeze()["runtime"]["code_hash"] == b.code_hash())
    sample = d118.sample(d118.eligible(d118.load_items()), STAGE_B_QUESTIONS, b.SEED)
    questions = [q for q in sample if q["question_type"] == QUESTION_TYPE]
    require(len(questions) == QUESTIONS)
    slots, requests, contexts = [], [], []
    for item in questions:
        for arm in ARMS:
            result, budget, ordered = b.assemble(item, arm)
            estimate = b.validate_request(request=result.request, config=budget, counter=b.COUNTER)
            diagnostics = result.diagnostics
            found = set(diagnostics.kept_turn_ids) | set(diagnostics.retrieved_turn_ids)
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
                    "needed_evidence_in_context": set(ordered) <= found,
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
        "approval": "D121 temporal output-limit check",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "stage_b_runner_sha256": hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest(),
        "code_hash": b.code_hash(),
        "dataset": {"file": lme.DATA.name, "revision": "98d7416c", "sha256": lme.SHA256},
        "seed": b.SEED,
        "question_type": QUESTION_TYPE,
        "arms": ARMS,
        "system": b.SYSTEM,
        "answer_generation": asdict(ANSWER),
        "judge_generation": asdict(b.JUDGE),
        "judge_source": b.JUDGE_SOURCE,
        "judge_templates": b.JUDGE_TEMPLATES,
        "retries": asdict(b.RETRIES),
        "quota": asdict(b.POLICY),
        "prices": asdict(b.PRICES),
        "cap_microusd": CAP_MICROUSD,
        "max_calls": MAX_CALLS,
        "max_rejections": b.MAX_REJECTIONS,
        "slots": slots,
    }


def stage_b_rows():
    """Stage B grades per (question, arm), keyed like D118 rows for the paired table."""
    rows = {}
    for row in read(STAGE_B)["rows"]:
        if row["arm"] in ARMS:
            rows[(row["question_id"], row["arm"])] = row
    return rows


def plan(questions, slots):
    previous = stage_b_rows()
    value = {
        "status": "PLANNED",
        "seed": b.SEED,
        "question_type": QUESTION_TYPE,
        "questions": len(questions),
        "answer_max_completion_tokens": ANSWER.max_completion_tokens,
        "stage_b_out_of_tokens_on_these": {
            arm: sum(
                previous[(s["question_id"], arm)]["out_of_tokens"] for s in slots if s["arm"] == arm
            )
            for arm in ARMS
        },
        "arms": {
            arm: {
                "calls": sum(s["arm"] == arm for s in slots),
                "max_estimated_input_tokens": max(
                    s["estimated_tokens"] for s in slots if s["arm"] == arm
                ),
                "worst_case_microusd": sum(b.worst_answer(s) for s in slots if s["arm"] == arm),
            }
            for arm in ARMS
        },
        "judge": {
            "calls": len(slots),
            "max_input_tokens_upper_bound": max(s["judge_upper_bound_tokens"] for s in slots),
            "worst_case_microusd": sum(b.worst_judge(s["judge_upper_bound_tokens"]) for s in slots),
        },
        "calls": MAX_CALLS,
        "call_limit": TOTAL_CALLS,
        "worst_case_total_microusd": b.worst_total(slots),
        "cap_microusd": CAP_MICROUSD,
        "minimum_minutes": -(-MAX_CALLS // b.POLICY.rpm),
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
    return value


_report = b.report


def report(manifest, questions, contexts):
    value, private, disagreements = _report(manifest, questions, contexts)
    previous = stage_b_rows()
    for arm, result in value["results"].items():
        result["planned"] = QUESTIONS
        result.pop("paired_vs_d118")
        mine = [r for r in value["rows"] if r["arm"] == arm and "strict-v1" in r]
        paired = {}
        for name in ("strict-v1", "lenient-v2", "lenient-v3", "judge"):
            counts = collections.Counter(
                (bool(previous[(r["question_id"], arm)][name]), bool(r[name])) for r in mine
            )
            paired[name] = {
                "improved": counts[(False, True)],
                "regressed": counts[(True, False)],
                "both_right": counts[(True, True)],
                "both_wrong": counts[(False, False)],
            }
        result["paired_vs_stage_b"] = paired
        before = [previous[(r["question_id"], arm)] for r in mine]
        result["stage_b_same_questions"] = {
            "out_of_tokens": sum(p["out_of_tokens"] for p in before),
            **{
                name: {"correct": sum(bool(p[name]) for p in before), "of": len(before)}
                | {"wilson95": wilson(sum(bool(p[name]) for p in before), len(before))}
                for name in ("strict-v1", "lenient-v2", "lenient-v3", "judge")
            },
        }
    value |= {
        "approval": "D121 temporal output-limit check",
        "question_type": QUESTION_TYPE,
        "answer_max_completion_tokens": ANSWER.max_completion_tokens,
        "limitations": [
            "26 temporal-reasoning questions (stage B's sample); one run; one model.",
            "Histories mix public chat logs with sessions simulated by the dataset authors.",
            "The judge is mercury-3 grading mercury-3 answers (same model family), with the "
            "published LongMemEval prompts written for GPT-4o; not human-checked.",
            "Temperature 0.5 (the API minimum): some paired changes are sampling noise.",
            "A larger limit also lets an answer think longer when it would not have run out.",
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
        "POLICY": replace(
            b.POLICY,
            account_id="inception-longmemeval-d121",
            daily_budget_microusd=CAP_MICROUSD,
            rpd=TOTAL_CALLS,
        ),
        "ANSWER": ANSWER,
        "RUNTIME_RUNNER_SHA256": None,
        "D118_SETTING": {arm: arm for arm in ARMS},
        "d118_rows": stage_b_rows,
        "accepted": accepted,
        "build": build,
        "identity": identity,
        "plan": plan,
        "report": report,
    }
    for name, value in settings.items():
        require(hasattr(b, name))
        setattr(b, name, value)


def main(argv=None):
    patch()
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    return b.main()


if __name__ == "__main__":
    raise SystemExit(main())
