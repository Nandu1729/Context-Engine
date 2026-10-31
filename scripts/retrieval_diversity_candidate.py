"""Isolated lexical diversity experiment; not a service or production extension."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rank_bm25 import BM25Plus

from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.context import LayerDiagnostic
from context_engine.layers.common import fits_block, history_digest, plan_window, set_block
from context_engine.layers.retrieve import (
    RetrieveLayer,
    chunk_turns,
    evidence_block,
    lexical_tokens,
    overlaps,
    represented_in_window,
    window_messages,
)
from context_engine.models import KeyedPins, canonical_json
from context_engine.work import raise_if_cancelled
from scripts import retrieval_quality_probe as probe
from scripts.incident_demo import offline_network

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/C11_DIVERSITY_PROTOCOL.md"
BASELINE = ROOT / "output/retrieval-quality-probe-001.json"
VERSION = "lexical-diversity-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def identity():
    return {"version": VERSION, "script": sha(Path(__file__)), "protocol": sha(PROTOCOL)}


def jaccard(left, right):
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def select_diverse(ranked, top_k, accepts, cancellation=None):
    """Fixed equal weighting; only accepted chunks affect redundancy penalties."""
    if not ranked:
        return ()
    peak = max(score for score, _, _ in ranked)
    if peak <= 0:
        raise ValueError("Expected positive retrieval scores")
    pending = list(ranked)
    selected, terms = (), []
    while pending and len(selected) < top_k:
        raise_if_cancelled(cancellation)
        scored = []
        for score, chunk, tokens in pending:
            raise_if_cancelled(cancellation)
            redundancy = max((jaccard(tokens, t) for t in terms), default=0.0)
            scored.append((0.5 * score / peak - 0.5 * redundancy, chunk, tokens, score))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        pending = []
        accepted = False
        for _, chunk, tokens, original_score in scored:
            raise_if_cancelled(cancellation)
            if accepted:
                pending.append((original_score, chunk, tokens))
            elif any(overlaps(chunk, old) for old in selected):
                continue
            elif accepts(selected + (chunk,)):
                selected += (chunk,)
                terms.append(tokens)
                accepted = True
        if not accepted:
            break
    return selected


class DiversityRetrieveLayer(RetrieveLayer):
    def apply(self, context):
        # Baseline performs all existing index/type/source checks first. This is
        # deliberately extra offline work,not a speed optimization.
        baseline = super().apply(context)
        planned = plan_window(context, self.counter)
        visible = window_messages(planned)
        old = tuple(
            t
            for t in planned.original_turns
            if t.turn_id not in planned.plan.window_turn_ids
            or (
                self.config.recover_capped_window
                and any(m.content != visible[(t.turn_id, m.message_id)] for m in t.messages)
            )
        )
        query = sorted(set(lexical_tokens(planned.question.content)))
        if not query or not old or not planned.plan.retrieval_tokens:
            return baseline
        if self.chunk_index is None:
            chunks = chunk_turns(old, self.config, cancellation=context.cancellation)
        else:
            ids = {t.turn_id for t in old}
            chunks = tuple(c for c in self.chunk_index.chunks if c.source.turn_id in ids)
        searchable = []
        for chunk in chunks:
            raise_if_cancelled(context.cancellation)
            if not represented_in_window(chunk, visible):
                terms = lexical_tokens(chunk.content)
                if terms:
                    searchable.append((chunk, terms))
        if not searchable:
            return baseline
        scores = BM25Plus(
            [terms for _, terms in searchable], k1=self.config.k1, b=self.config.b, delta=1.0
        ).get_scores(query)
        ranked = [
            (float(score), chunk, frozenset(terms))
            for (chunk, terms), score in zip(searchable, scores, strict=True)
            if set(query).intersection(terms) and score > self.config.minimum_score
        ]
        selected = select_diverse(
            ranked,
            self.config.top_k,
            lambda values: fits_block(
                planned,
                evidence_block(values, self.counter),
                planned.plan.retrieval_tokens,
                self.counter,
            ),
            context.cancellation,
        )
        block = evidence_block(selected, self.counter)
        return replace(
            set_block(
                planned,
                block,
                LayerDiagnostic(
                    "RETRIEVE",
                    VERSION,
                    tuple(dict.fromkeys(c.source.turn_id for c in selected)),
                    output_text_tokens=block.text_tokens,
                ),
            ),
            retrieved_chunks=selected,
        )


def candidate_assemble(*args, **kwargs):
    # Research process only. No concurrent service calls may use this substitution.
    with patch("context_engine.pipeline.RetrieveLayer", DiversityRetrieveLayer):
        result = assemble_context(*args, **kwargs)
    return replace(
        result,
        diagnostics=replace(
            result.diagnostics,
            config_fingerprint=digest([result.diagnostics.config_fingerprint, identity()]),
        ),
    )


def data(messages, prefix):
    return [
        json.loads(m["content"].split("\n", 1)[1])
        for m in messages
        if m["role"] == "user" and m["content"].startswith(prefix + "\n")
    ]


def lost_spans(baseline, candidate):
    """Return every source interval no longer retrieved,including partial losses."""
    remaining = {}
    for block in data(candidate, "[RETRIEVED DATA]"):
        for c in block:
            remaining.setdefault((c["turn"], c["message"]), []).append((c["start"], c["end"]))
    lost = []
    for block in data(baseline, "[RETRIEVED DATA]"):
        for c in block:
            cursor = c["start"]
            for start, end in sorted(remaining.get((c["turn"], c["message"]), [])):
                if end <= cursor or start >= c["end"]:
                    continue
                if start > cursor:
                    lost.append(
                        {"turn": c["turn"], "message": c["message"], "start": cursor, "end": start}
                    )
                cursor = max(cursor, end)
            if cursor < c["end"]:
                lost.append(
                    {"turn": c["turn"], "message": c["message"], "start": cursor, "end": c["end"]}
                )
    return lost


def run():
    with offline_network():
        saved = json.loads(BASELINE.read_text())
        if saved["probe_sha256"] != sha(Path(probe.__file__)):
            raise ValueError("Baseline probe changed")
        if probe.runtime_identity() != saved["runtime"]:
            raise ValueError("Baseline runtime changed")
        expected = {(r["case"], r["budget"]): r for r in saved["rows"]}
        rows = []
        for case in probe.cases():
            history, question, scope = probe.inputs(case)
            before = history_digest(history)
            for budget in (900, 3000):
                args = (
                    history,
                    question,
                    KeyedPins(scope),
                    BudgetConfig(input_cap=budget, retrieval_reserve=280, summary_reserve=0),
                )
                baseline = assemble_context(*args, system=probe.SYSTEM, at=probe.AT)
                if (
                    digest(baseline.request.to_wire())
                    != expected[case[0], budget]["request_sha256"]
                ):
                    raise ValueError("Baseline request mismatch")
                candidate = candidate_assemble(*args, system=probe.SYSTEM, at=probe.AT)
                if history_digest(history) != before:
                    raise ValueError("Original history changed")
                if candidate.diagnostics.estimate.estimated_tokens > budget:
                    raise ValueError("Candidate over budget")
                if (
                    baseline.messages[0] != candidate.messages[0]
                    or baseline.messages[-1] != candidate.messages[-1]
                    or data(baseline.messages, "[WINDOW DATA]")
                    != data(candidate.messages, "[WINDOW DATA]")
                ):
                    raise ValueError("Required content or WINDOW changed")
                old = probe.measure(baseline.messages, history, case[2])
                new = probe.measure(candidate.messages, history, case[2])
                rows.append(
                    {
                        "case": case[0],
                        "budget": budget,
                        "baseline_events": old,
                        "candidate_events": new,
                        "baseline_tokens": baseline.diagnostics.estimate.estimated_tokens,
                        "candidate_tokens": candidate.diagnostics.estimate.estimated_tokens,
                        "candidate_request_sha256": digest(candidate.request.to_wire()),
                        "candidate_config_fingerprint": candidate.diagnostics.config_fingerprint,
                        "lost_retrieved_spans": lost_spans(baseline.messages, candidate.messages),
                    }
                )
        preserved = all(
            not old or new
            for r in rows
            for old, new in zip(r["baseline_events"], r["candidate_events"], strict=True)
        )
        recovered = all(
            all(r["candidate_events"]) for r in rows if r["case"] == "multiple_events_paraphrase"
        )
        return {
            "status": "DIAGNOSTIC_ONLY",
            "identity": identity(),
            "baseline_report_sha256": sha(BASELINE),
            "runtime": saved["runtime"],
            "inference_calls": 0,
            "heldout_used": False,
            "default_adopted": False,
            "answer_quality": "NOT_EVALUATED",
            "rows": rows,
            "baseline_events_preserved": preserved,
            "paraphrase_events_recovered": recovered,
            "continuation_gate": "PASS" if preserved and recovered else "FAIL",
            "source_span_loss_conditions": sum(bool(r["lost_retrieved_spans"]) for r in rows),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("Choose a new output path")
    report = run()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
