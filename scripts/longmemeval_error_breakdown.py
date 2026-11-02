#!/usr/bin/env python3
"""Offline breakdown of the D118 run -002 wrong answers, and lenient-v3 regrade (D119).

Rebuilds every assembled context from the dataset (its request hash must match the
live manifest), reads the private receipts, and classifies each lenient-v2 miss by
the first rule that applies:

  (a) format_only   lenient-v3 accepts the reply (a1), or the reply contains the
                    whole gold phrase plus other words (a2). v3 tokens on both sides.
  (b) rubric_gold   the gold cannot pass exact match: it lists an alternative
                    ("acceptable", "(or "), is a preference description (type
                    single-session-preference), or has 8 or more words.
  (c) evidence_missing
                    c1: a needed evidence turn is not in context (knowledge-update:
                    the newest evidence turn; other types: every evidence turn);
                    c2: the turns are there, but the gold phrase appears in the full
                    evidence turns and not in the assembled context (chunking cut it).
  (d) model_error   evidence present and the reply is "unknown" (d1) or a wrong
                    answer (d2); d*_extractive when the gold phrase is in context,
                    d*_computed when it is not anywhere (counts, dates, sums).

Public output has counts and per-row ids/labels/booleans only; examples, replies and
contexts stay in output/private/. No network, no model calls.
"""

import collections
import importlib.util
import json
import random
from pathlib import Path

from context_engine.evaluation.grading import GRADERS, answer_correct_lenient_v3, v3_tokens
from context_engine.providers.contracts import Completion, fingerprint


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


live = _load("longmemeval_accuracy_live")
ROOT = live.ROOT
PUBLIC = ROOT / "output/longmemeval-error-breakdown-001"
PRIVATE = ROOT / "output/private/longmemeval-error-breakdown-001"
GRADER_NAMES = (*GRADERS, "lenient-v3")
GROUPS = ("format_only", "rubric_gold", "evidence_missing", "model_error")
RUBRIC_WORDS = 8


def contains(haystack, needle):
    """Whole-token contiguous match of v3 token lists."""
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def classify(item, reply, context, evidence_texts, needed_present):
    gold, answer = v3_tokens(str(item["answer"])), v3_tokens(reply)
    if answer_correct_lenient_v3(reply, (str(item["answer"]),)):
        return "format_only", "a1_lenient_v3"
    if answer != ["unknown"] and contains(answer, gold):
        return "format_only", "a2_gold_plus_words"
    text = str(item["answer"]).casefold()
    if (
        "acceptable" in text
        or "(or " in text
        or item["question_type"] == "single-session-preference"
        or len(gold) >= RUBRIC_WORDS
    ):
        return "rubric_gold", "b_rubric_or_description"
    if not needed_present:
        return "evidence_missing", "c1_turn_missing"
    in_context = contains(v3_tokens(context), gold)
    if not in_context and any(contains(v3_tokens(t), gold) for t in evidence_texts):
        return "evidence_missing", "c2_answer_text_cut"
    kind = "d1_unknown" if answer == ["unknown"] else "d2_wrong"
    return "model_error", f"{kind}_{'extractive' if in_context else 'computed'}"


def wilson(count, total):
    return live.wilson(count, total)


def analyse():
    manifest = live.read(live.RUN / "manifest.json")
    questions = live.sample(live.eligible(live.load_items()), live.QUESTIONS)
    items = {q["question_id"]: q for q in questions}
    done, open_claims = live.receipts(manifest)
    live.require(len(done) == live.MAX_CALLS and not open_claims)
    rows, private = [], []
    for slot in manifest["slots"]:
        item = items[slot["question_id"]]
        result, _, found = live.assemble(item, slot["setting"])
        live.require(fingerprint(result.request.to_wire()) == slot["request_hash"])
        turns, ordered = live.lme.history(item)
        text = {t.turn_id: " ".join(m.content for m in t.messages) for t in turns}
        needed = ordered[-1:] if item["question_type"] == "knowledge-update" else ordered
        context = "\n".join(m["content"] for m in result.request.to_wire()["messages"])
        receipt = done[slot["slot"]]["result"]
        live.require(receipt["status"] == "success")
        reply = Completion.from_dict(receipt["completion"]).content
        gold = (str(item["answer"]),)
        grades = {name: grader(reply, gold) for name, grader in GRADERS.items()}
        grades["lenient-v3"] = answer_correct_lenient_v3(reply, gold)
        row = {
            "slot": slot["slot"],
            "question_id": slot["question_id"],
            "type": slot["type"],
            "setting": slot["setting"],
            **grades,
            "needed_evidence_in_context": set(needed) <= set(found),
            "group": None,
            "rule": None,
        }
        if not grades["lenient-v2"]:
            row["group"], row["rule"] = classify(
                item, reply, context, [text[i] for i in ordered], row["needed_evidence_in_context"]
            )
            private.append(
                {
                    **{k: row[k] for k in ("question_id", "type", "setting", "group", "rule")},
                    "question": item["question"],
                    "gold": gold[0],
                    "reply": reply[:300],
                }
            )
        rows.append(row)
    return rows, private


def summarize(rows):
    settings = {}
    for setting in live.SETTINGS:
        mine = [r for r in rows if r["setting"] == setting]
        by_type = collections.defaultdict(lambda: dict.fromkeys(("answered", *GRADER_NAMES), 0))
        for r in mine:
            by_type[r["type"]]["answered"] += 1
            for name in GRADER_NAMES:
                by_type[r["type"]][name] += r[name]
        wrong = [r for r in mine if r["group"]]
        settings[setting] = {
            "answered": len(mine),
            **{
                name: {
                    "correct": sum(r[name] for r in mine),
                    "wilson95": wilson(sum(r[name] for r in mine), len(mine)),
                }
                for name in GRADER_NAMES
            },
            "by_type": dict(sorted(by_type.items())),
            "wrong_lenient_v2": len(wrong),
            "groups": {g: sum(r["group"] == g for r in wrong) for g in GROUPS},
            "rules": dict(sorted(collections.Counter(r["rule"] for r in wrong).items())),
        }
    paired = {}
    core = {r["question_id"]: r for r in rows if r["setting"] == "core_default"}
    for name in GRADER_NAMES:
        counts = collections.Counter()
        for r in rows:
            if r["setting"] == "chatmemory_default":
                counts[(core[r["question_id"]][name], r[name])] += 1
        paired[name] = {
            "only_chatmemory": counts[(False, True)],
            "only_core": counts[(True, False)],
            "both": counts[(True, True)],
            "neither": counts[(False, False)],
        }
    return settings, paired


def main():
    rows, private = analyse()
    settings, paired = summarize(rows)
    report = {
        "id": "longmemeval-error-breakdown-001",
        "approval": "D119 stage A",
        "source_run": live.RUN_ID,
        "inference_calls": 0,
        "wrong_definition": "lenient-v2 is false",
        "rules": __doc__.split("first rule that applies:")[1].split("Public output")[0].strip(),
        "results": settings,
        "paired_core_vs_chatmemory": paired,
        "rows": rows,
        "limitations": [
            "Rules are mechanical: a2 can accept a hedged reply, and b counts a rubric gold "
            "whether or not the reply meets the rubric.",
            "c2 and d*_extractive need the gold words verbatim; computed answers (counts, "
            "dates) never match text, so they fall in d*_computed.",
            "One model, one run, temperature 0.5; partly simulated chats.",
        ],
    }
    PUBLIC.mkdir(exist_ok=True)
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    (PUBLIC / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    examples = {}
    for rule in sorted({p["rule"] for p in private}):
        chosen = [p for p in private if p["rule"] == rule]
        random.Random(live.SEED).shuffle(chosen)
        examples[rule] = chosen[:3]
    (PRIVATE / "examples.json").write_text(json.dumps(examples, indent=2) + "\n")
    print(json.dumps({"results": settings, "paired": paired}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
