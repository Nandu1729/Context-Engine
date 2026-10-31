#!/usr/bin/env python3
"""Offline evidence recall on LongMemEval-S (public, MIT): no model calls.

For each question, the ~490-turn haystack becomes `Turn`s (one per message, dated by
session) and `assemble_context` runs at a budget. A question counts as recalled when
an evidence turn (`has_answer`) is in the assembled context: kept in the recent window
or retrieved. `any` = at least one evidence turn, `all` = every evidence turn.
Questions without labelled evidence turns are skipped.

Data: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned at revision
98d7416c (not redistributed; download into output/private/datasets/).
Usage: longmemeval_retrieval.py [--limit N] [--budget 3000] [--reserve 280] [--top-k 4]
       [--mode keyword|hybrid] [--diverse] [--out report.json]
ChatMemory's defaults at 3000 tokens are --reserve 1200 --top-k 13 --diverse.
"""

import argparse
import collections
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from context_engine import assemble_context
from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output/private/datasets/longmemeval-98d7416c/longmemeval_s_cleaned.json"
SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
SCOPE = Scope("longmemeval", "haystack")
SYSTEM = "Answer the user's question from the conversation memory."


def parse_date(text):
    return datetime.strptime(text.split(" (")[0] + text[-6:], "%Y/%m/%d %H:%M").replace(tzinfo=UTC)


def history(item):
    """Chronological turns and the evidence turn ids (in order: the last is the newest)."""
    turns, evidence = [], []
    sessions = sorted(
        enumerate(zip(item["haystack_dates"], item["haystack_sessions"], strict=True)),
        key=lambda pair: parse_date(pair[1][0]),
    )  # Chronological; session ids can repeat, so turn ids use the haystack position.
    for position, (date, session) in sessions:
        at = parse_date(date)
        for index, message in enumerate(session):
            if not message["content"].strip():
                continue
            turn_id = f"s{position}:{index}"
            if message.get("has_answer"):
                evidence.append(turn_id)
            role = Role.USER if message["role"] == "user" else Role.ASSISTANT
            message = Message(f"m{turn_id}", role, message["content"])
            turns.append(Turn(turn_id, SCOPE, (message,), timestamp=at))
    return tuple(turns), evidence


def evaluate(item, args, embedder):
    turns, ordered = history(item)
    if not ordered:
        return None
    evidence = set(ordered)
    result = assemble_context(
        turns,
        item["question"],
        KeyedPins(SCOPE),
        BudgetConfig(input_cap=args.budget, retrieval_reserve=args.reserve),
        system=SYSTEM,
        at=parse_date(item["question_date"]),
        retrieval_config=RetrievalConfig(top_k=args.top_k),
        embedder=embedder,
        diverse_turns=args.diverse,
    )
    diagnostics = result.diagnostics
    kept, retrieved = set(diagnostics.kept_turn_ids), set(diagnostics.retrieved_turn_ids)
    return {
        "question_id": item["question_id"],
        "type": item["question_type"],
        "turns": len(turns),
        "evidence": len(evidence),
        "window_any": bool(evidence & kept),
        "any": bool(evidence & (kept | retrieved)),
        "all": evidence <= (kept | retrieved),
        "latest": ordered[-1] in kept | retrieved,
        "retrieved_hits": len(evidence & retrieved),
        "kept_turns": len(kept),
        "estimated_tokens": diagnostics.estimate.estimated_tokens,
    }


def summarize(rows):
    def rates(group):
        n = len(group)
        return {
            "n": n,
            **{
                k: round(sum(r[k] for r in group) / n, 4)
                for k in ("window_any", "any", "all", "latest")
            },
        }

    by_type = collections.defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)
    overall = rates(rows) | {
        "mean_kept_turns": round(sum(r["kept_turns"] for r in rows) / len(rows), 2)
    }
    return {"overall": overall, "by_type": {t: rates(g) for t, g in sorted(by_type.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--budget", type=int, default=3000)
    parser.add_argument("--reserve", type=int, default=280)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--mode", choices=("keyword", "hybrid"), default="hybrid")
    parser.add_argument("--diverse", action="store_true", help="one chunk per turn")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    import hashlib

    blob = DATA.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SHA256:
        sys.exit("dataset hash mismatch")
    items = json.loads(blob)[: args.limit]
    embedder = "builtin" if args.mode == "hybrid" else None
    rows, start = [], time.perf_counter()
    for number, item in enumerate(items, 1):
        row = evaluate(item, args, embedder)
        if row is not None:
            rows.append(row)
        if number % 50 == 0:
            print(f"{number}/{len(items)} {time.perf_counter() - start:.0f}s", file=sys.stderr)
    report = {
        "dataset": "longmemeval_s_cleaned@98d7416c",
        "settings": vars(args) | {"out": None},
        "seconds": round(time.perf_counter() - start, 1),
        **summarize(rows),
    }
    print(json.dumps({k: report[k] for k in ("settings", "seconds", "overall")}))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report | {"rows": rows}, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
