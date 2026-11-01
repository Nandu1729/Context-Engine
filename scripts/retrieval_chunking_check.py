#!/usr/bin/env python3
"""Offline retrieval check for D119 cause (c): is the answer text cut off by chunking,
and does dropping stop words from keyword search help? No model calls, no src change.

Variants (each run with core and ChatMemory defaults at 3000 tokens):
  base        360/80 characters, all words (current defaults)
  stopwords   360/80, English stop words removed from BM25 query and chunks
  chunk600    600/150 characters
  chunk600_sw 600/150 and stop words removed
Variants are applied in this process only: chunk sizes through the RetrievalConfig
passed to assemble_context (and the strategy harness), stop words by patching the
RETRIEVE layer's `lexical_tokens`.

LongMemEval-S (470 eligible questions, same frame as D118): evidence-turn recall
(any/all/latest, as in longmemeval_retrieval.py) and answer-text recall: for
"extractive" questions (the gold has a non-numeric word and its v3 tokens appear in
an evidence turn), is the gold phrase anywhere in the assembled context? `cut` counts
extractive questions whose gold-bearing evidence turn is in context but the gold
text is not (chunking or CAP removed it).
Synthetic benchmark: `compare_strategies` evidence_at_source (the evidence sentence
is in context) for the retrieval strategies, original and reworded questions.
"""

import argparse
import collections
import functools
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# NLTK's English stop-word list (179 words), lowercased, no punctuation variants.
STOP_WORDS = frozenset(
    """i me my myself we our ours ourselves you you're you've you'll you'd your yours
    yourself yourselves he him his himself she she's her hers herself it it's its itself
    they them their theirs themselves what which who whom this that that'll these those
    am is are was were be been being have has had having do does did doing a an the and
    but if or because as until while of at by for with about against between into
    through during before after above below to from up down in out on off over under
    again further then once here there when where why how all any both each few more
    most other some such no nor not only own same so than too very s t can will just
    don don't should should've now d ll m o re ve y ain aren aren't couldn couldn't didn
    didn't doesn doesn't hadn hadn't hasn hasn't haven haven't isn isn't ma mightn
    mightn't mustn mustn't needn needn't shan shan't shouldn shouldn't wasn wasn't weren
    weren't won won't wouldn wouldn't""".split()
)
VARIANTS = {
    "base": (360, 80, False),
    "stopwords": (360, 80, True),
    "chunk600": (600, 150, False),
    "chunk600_sw": (600, 150, True),
}
SYNTHETIC_STRATEGIES = ("retrieval_window", "combined", "retrieval_semantic", "combined_semantic")
OUT = Path(__file__).resolve().parents[1] / "output/retrieval-chunking-001"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_variant(name):
    """Patch this process: chunk sizes in RetrievalConfig defaults, stop words in BM25."""
    from context_engine import config
    from context_engine.evaluation import strategies
    from context_engine.layers import retrieve

    size, overlap, stop = VARIANTS[name]
    original = getattr(retrieve, "_original_lexical_tokens", retrieve.lexical_tokens)
    retrieve._original_lexical_tokens = original
    retrieve.lexical_tokens = (
        (lambda text: [t for t in original(text) if t not in STOP_WORDS]) if stop else original
    )
    base = getattr(config, "_OriginalRetrievalConfig", config.RetrievalConfig)
    config._OriginalRetrievalConfig = base

    def sized(**kwargs):
        return base(**(kwargs | {"chunk_characters": size, "overlap_characters": overlap}))

    strategies.RetrievalConfig = sized  # The pipeline itself checks isinstance: untouched.
    return sized


def contains(haystack, needle):
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


@functools.cache
def _modules():
    return _load("longmemeval_accuracy_live")


def longmemeval_row(task):
    """One question x variant x setting (runs in a worker process)."""
    from context_engine import assemble_context
    from context_engine.config import BudgetConfig
    from context_engine.evaluation.grading import v3_tokens
    from context_engine.models import KeyedPins

    item, variant, setting = task
    live = _modules()
    lme = live.lme
    sized = apply_variant(variant)
    options = live.SETTINGS[setting]
    turns, ordered = lme.history(item)
    result = assemble_context(
        turns,
        item["question"],
        KeyedPins(lme.SCOPE),
        BudgetConfig(input_cap=live.BUDGET, retrieval_reserve=options["reserve"]),
        system=live.SYSTEM.format(date=item["question_date"]),
        at=lme.parse_date(item["question_date"]),
        retrieval_config=sized(top_k=options["top_k"]),
        embedder="builtin",
        diverse_turns=options["diverse_turns"],
    )
    d = result.diagnostics
    found = set(d.kept_turn_ids) | set(d.retrieved_turn_ids)
    evidence = set(ordered)
    text = {t.turn_id: " ".join(m.content for m in t.messages) for t in turns}
    gold = v3_tokens(str(item["answer"]))
    bearing = [i for i in ordered if contains(v3_tokens(text[i]), gold)]
    extractive = bool(bearing) and any(not w.replace(".", "").isdigit() for w in gold)
    context = v3_tokens("\n".join(m.content for m in result.request.messages))
    in_context = extractive and contains(context, gold)
    return {
        "question_id": item["question_id"],
        "type": item["question_type"],
        "variant": variant,
        "setting": setting,
        "any": bool(evidence & found),
        "all": evidence <= found,
        "latest": ordered[-1] in found,
        "extractive": extractive,
        "answer_text": in_context,
        "cut": extractive and bool(set(bearing) & found) and not in_context,
        "retrieved_chunks": len(d.retrieved_chunk_ids),
        "kept_turns": len(d.kept_turn_ids),
    }


def longmemeval(workers, limit):
    live = _modules()
    items = live.eligible(live.load_items())[:limit]
    tasks = [(i, v, s) for v in VARIANTS for s in live.SETTINGS for i in items]
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(longmemeval_row, tasks, chunksize=8))
    summary = {}
    for (variant, setting), group in sorted(
        collections.defaultdict(list, _group(rows, ("variant", "setting"))).items()
    ):
        extractive = [r for r in group if r["extractive"]]
        summary.setdefault(variant, {})[setting] = {
            "questions": len(group),
            **{k: sum(r[k] for r in group) for k in ("any", "all", "latest")},
            "extractive": len(extractive),
            "answer_text": sum(r["answer_text"] for r in extractive),
            "cut": sum(r["cut"] for r in extractive),
            "mean_retrieved_chunks": round(
                sum(r["retrieved_chunks"] for r in group) / len(group), 2
            ),
            "mean_kept_turns": round(sum(r["kept_turns"] for r in group) / len(group), 2),
        }
    return summary, rows


def _group(rows, keys):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    return groups


def synthetic_task(variant):
    from context_engine.evaluation.corpus import load_bundle
    from context_engine.evaluation.strategies import compare_strategies

    apply_variant(variant)
    bundle, out = load_bundle(), {}
    for questions in ("original", "paraphrased"):
        report = compare_strategies(bundle, questions=questions)
        for entry in report["results"]:
            if entry["strategy"] in SYNTHETIC_STRATEGIES:
                key = f"{questions}:{entry['budget']}:{entry['strategy']}"
                out[key] = f"{entry['evidence_at_source']}/{entry['probes']}"
    return variant, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    start = time.perf_counter()
    with ProcessPoolExecutor(len(VARIANTS)) as pool:
        synthetic = dict(pool.map(synthetic_task, VARIANTS))
    print(f"synthetic done {time.perf_counter() - start:.0f}s", file=sys.stderr)
    summary, rows = longmemeval(args.workers, args.limit)
    report = {
        "id": "retrieval-chunking-001",
        "approval": "D119 stage A",
        "inference_calls": 0,
        "dataset": "longmemeval_s_cleaned@98d7416c (470 eligible questions)",
        "budget": 3000,
        "variants": {
            k: dict(zip(("chunk", "overlap", "stop_words"), v, strict=True))
            for k, v in VARIANTS.items()
        },
        "longmemeval": summary,
        "synthetic_evidence_at_source": synthetic,
        "seconds": round(time.perf_counter() - start, 1),
        "rows": rows,
        "limitations": [
            "Answer-text recall needs the gold words verbatim, so it covers extractive "
            "questions only; computed answers (counts, dates) are excluded.",
            "Stop-word list is NLTK's English list; no other list was tried.",
            "Synthetic corpus authored with the engine (31 facts).",
        ],
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    shown = ("longmemeval", "synthetic_evidence_at_source")
    print(json.dumps({k: report[k] for k in shown}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
