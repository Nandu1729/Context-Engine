"""Offline-only overlap-union experiment; never installed or used by the service.

The process-local layer substitution is deliberately confined to a single-threaded
research runner. It is NOT a concurrent production assembly API. Core stays0.9.6.
"""

import argparse
import hashlib
import json
import time
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from rank_bm25 import BM25Plus

from context_engine.config import Settings
from context_engine.context import LayerDiagnostic
from context_engine.errors import ContextEngineError, MemoryIntegrityError
from context_engine.evaluation.protocol import runtime_identity
from context_engine.inspection import parse_job
from context_engine.layers.common import fits_block, plan_window, set_block
from context_engine.layers.retrieve import (
    ChunkIndex,
    RetrieveLayer,
    chunk_turns,
    evidence_block,
    lexical_tokens,
    overlaps,
    represented_in_window,
    window_messages,
)
from context_engine.models import Chunk, canonical_json
from context_engine.work import raise_if_cancelled
from scripts.incident_demo import offline_network
from scripts.longmemeval_demo import write_json
from scripts.longmemeval_review import coverage, digest

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "output/private/longmemeval-review-001"
PROTOCOL = ROOT / "docs/C11_RETRIEVAL_UNION_PROTOCOL.md"
VERSION = "overlap-union-development-v1"
EXPECTED_CORE = "304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2"
EXPECTED_SPLIT = "aab5693329fa716acd05621b4d791e508779c6e80471e22e94021d6537229279"


def coalesce(selected, incoming, originals):
    """Replace intersecting slices by their exact source union, never bridge gaps.

    All selected slices must be valid and nonoverlapping (enforced by selection).
    A union cannot introduce text outside the incoming/previously selected spans.
    """
    incoming.validate_source(originals[incoming.source.turn_id])
    touched = [c for c in selected if overlaps(c, incoming)]
    if not touched:
        return selected + (incoming,)
    for chunk in touched:
        chunk.validate_source(originals[chunk.source.turn_id])
    start = min(c.source.start for c in [incoming, *touched])
    end = max(c.source.end for c in [incoming, *touched])
    if len(touched) == 1 and (start, end) == (
        touched[0].source.start,
        touched[0].source.end,
    ):
        return selected
    source = replace(incoming.source, start=start, end=end)
    merged = Chunk(
        hashlib.sha256(canonical_json([asdict(source), VERSION]).encode()).hexdigest(),
        source,
        source.extract(originals[source.turn_id]),
        VERSION,
    )
    first = selected.index(touched[0])
    return tuple(
        merged if i == first else c
        for i, c in enumerate(selected)
        if i == first or c not in touched
    )


class UnionRetrieveLayer(RetrieveLayer):
    """Same ranking, WINDOW policy and budgets; only overlap selection differs."""

    def apply(self, context):
        if self.chunk_index is not None:
            if not isinstance(self.chunk_index, ChunkIndex):
                raise MemoryIntegrityError("Expected a validated chunk index")
            self.chunk_index.validate(context.original_turns, self.config)
        planned = plan_window(context, self.counter)
        visible = window_messages(planned)
        originals = {t.turn_id: t for t in planned.original_turns}
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
        selected = ()
        if query and old and planned.plan.retrieval_tokens:
            if self.chunk_index is None:
                chunks = chunk_turns(old, self.config, cancellation=context.cancellation)
            else:
                ids = {t.turn_id for t in old}
                chunks = tuple(c for c in self.chunk_index.chunks if c.source.turn_id in ids)
            searchable = []
            for c in chunks:
                raise_if_cancelled(context.cancellation)
                if not represented_in_window(c, visible) and (terms := lexical_tokens(c.content)):
                    searchable.append((c, terms))
            if searchable:
                scores = BM25Plus(
                    [terms for _, terms in searchable],
                    k1=self.config.k1,
                    b=self.config.b,
                    delta=1.0,
                ).get_scores(query)
                ranked = [
                    (float(score), c)
                    for (c, terms), score in zip(searchable, scores, strict=True)
                    if set(query).intersection(terms) and score > self.config.minimum_score
                ]
                ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
                for _, chunk in ranked:
                    raise_if_cancelled(context.cancellation)
                    candidate = coalesce(selected, chunk, originals)
                    if candidate != selected and fits_block(
                        planned,
                        evidence_block(candidate, self.counter),
                        planned.plan.retrieval_tokens,
                        self.counter,
                    ):
                        selected = candidate
                    if len(selected) >= self.config.top_k:
                        break
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


def assemble_candidate(job, budget):
    # This helper is for this offline single-threaded process only. Always restore
    # the original class, including on failure; never mutate package source files.
    with patch("context_engine.pipeline.RetrieveLayer", UnionRetrieveLayer):
        result = job.run(input_cap=budget)
    return replace(
        result,
        diagnostics=replace(
            result.diagnostics,
            config_fingerprint=digest([result.diagnostics.config_fingerprint, identity()]),
        ),
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity():
    return {"candidate": VERSION, "code_sha256": sha(Path(__file__)), "protocol": sha(PROTOCOL)}


def run_case(payload, budget):
    job = parse_job(payload, Settings())
    before = digest(payload)
    start = time.perf_counter()
    result = assemble_candidate(job, budget).to_dict(include_content=True)
    elapsed = time.perf_counter() - start
    if digest(payload) != before:
        raise RuntimeError("Input changed")
    if result["diagnostics"]["estimate"]["estimated_tokens"] > budget:
        raise RuntimeError("Budget violated")
    return result, elapsed


def run(output):
    with offline_network():
        runtime = runtime_identity()
        if runtime["code_hash"] != EXPECTED_CORE:
            raise RuntimeError("Frozen core mismatch")
        split = json.loads((PRIOR / "split.json").read_text(encoding="utf-8"))
        unsigned = {k: v for k, v in split.items() if k != "split_sha256"}
        if split["split_sha256"] != EXPECTED_SPLIT or digest(unsigned) != EXPECTED_SPLIT:
            raise RuntimeError("Frozen split mismatch")
        selected = split["partitions"]["development"]
        if len(selected) != 35:
            raise RuntimeError("Development selection mismatch")
        files = [PRIOR / "split.json", PRIOR / "report.json"]
        for case in selected:
            directory = PRIOR / f"row-{case['row']:03d}"
            files += [directory / f"{kind}-dated.json" for kind in ("input", "labels")]
            files += [directory / f"assembly-dated-{b}.json" for b in (900, 3000)]
        hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
        plan = {
            **identity(),
            "runtime": runtime,
            "input_hashes": hashes,
            "selection": selected,
            "budgets": [900, 3000],
            "arm": "dated",
            "planned": 70,
            "inference_calls": 0,
            "heldout_used": False,
        }
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
        write_json(output / "plan.json", plan)
        rows = []
        for case in selected:
            directory = PRIOR / f"row-{case['row']:03d}"
            payload = json.loads((directory / "input-dated.json").read_text(encoding="utf-8"))
            for budget in (900, 3000):
                record = {**case, "budget": budget}
                try:
                    result, elapsed = run_case(payload, budget)
                except ContextEngineError as exc:
                    record.update(status="REJECTED", error_code=exc.code)
                    rows.append(record)
                    continue
                # Labels enter only this post-assembly measurement boundary.
                labels = json.loads((directory / "labels-dated.json").read_text(encoding="utf-8"))
                baseline = json.loads(
                    (directory / f"assembly-dated-{budget}.json").read_text(encoding="utf-8")
                )
                record.update(
                    status="ASSEMBLED",
                    elapsed_seconds=elapsed,
                    baseline_coverage=coverage(baseline, payload, labels),
                    candidate_coverage=coverage(result, payload, labels),
                    baseline_tokens=baseline["diagnostics"]["estimate"]["estimated_tokens"],
                    candidate_tokens=result["diagnostics"]["estimate"]["estimated_tokens"],
                    baseline_request_sha256=digest(baseline["request"]),
                    candidate_request_sha256=digest(result["request"]),
                    finalizer_drops=result["diagnostics"]["drops"],
                )
                write_json(output / f"row-{case['row']:03d}-{budget}.json", result)
                rows.append(record)
            print(json.dumps({"completed": len(rows), "planned": 70}), flush=True)
        if hashes != {str(p.relative_to(ROOT)): sha(p) for p in files}:
            raise RuntimeError("Saved evidence changed")
        if identity() != {k: plan[k] for k in identity()} or runtime_identity() != runtime:
            raise RuntimeError("Candidate identity changed")
        report = {
            "status": "TEST_ONLY",
            "plan_sha256": digest(plan),
            "planned": 70,
            "answer_quality": "NOT_EVALUATED",
            "inference_calls": 0,
            "heldout_used": False,
            "source_exports_unchanged": True,
            "default_adopted": False,
            "rows": rows,
        }
        write_json(output / "report.json", report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
