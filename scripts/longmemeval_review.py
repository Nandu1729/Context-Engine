"""Bounded offline development review; no provider client or held-out execution.

Run as a module. Writes an immutable split before any new assemblies. Public
dataset content stays in an ignored private directory. Never changes core defaults.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from context_engine.config import MAX_INSPECTION_BYTES, Settings
from context_engine.errors import ContextEngineError
from context_engine.evaluation.protocol import runtime_identity
from context_engine.inspection import parse_job
from scripts import longmemeval_demo as demo
from scripts.incident_demo import escaped, offline_network

CATEGORIES = tuple(sorted(demo.TYPES | {"abstention"}))
ARMS = {
    "baseline": (False, False),
    "recovery": (False, True),
    "dated": (True, False),
    "dated_recovery": (True, True),
}
SPLIT_SEED = "longmemeval-local-review-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def groups(rows):
    """Keep question families and shared answer-source sessions in one split.

    Evidence IDs are used only by the split controller, never assembly. Distractor
    session reuse is measured separately: this is not a session-disjoint corpus.
    """
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        keys = ["q:" + row["question_id"].removesuffix("_abs")]
        keys += ["e:" + sid for sid in row["answer_session_ids"]]
        for key in keys:
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    members = defaultdict(list)
    for i in range(len(rows)):
        members[find(i)].append(i)
    return list(members.values())


def make_split(rows, exposed, *, development_per_category=5, heldout_per_category=10):
    grouped = groups(rows)
    ordered = sorted(
        grouped,
        key=lambda g: digest([SPLIT_SEED, sorted(rows[i]["question_id"] for i in g)]),
    )
    used = {i for g in grouped if set(g) & set(exposed) for i in g}
    prior = sorted(used)

    def take(count):
        chosen = []
        counts = Counter()
        for cat in CATEGORIES:
            for group in ordered:
                if counts[cat] >= count:
                    break
                if set(group) & used or not any(demo.category(rows[i]) == cat for i in group):
                    continue
                chosen.extend(group)
                used.update(group)
                counts.update(demo.category(rows[i]) for i in group)
            demo.require(counts[cat] >= count, "insufficient_split_category")
        return sorted(chosen)

    heldout = take(heldout_per_category)
    development = take(development_per_category)
    partitions = {
        "previously_exposed": prior,
        "development": development,
        "heldout": heldout,
        "unused": sorted(set(range(len(rows))) - used),
    }
    split = {
        "seed": SPLIT_SEED,
        "rule": "group by question family/shared answer-session ID; hash order; heldout first",
        "minimum_per_category": {
            "development": development_per_category,
            "heldout": heldout_per_category,
        },
        "partitions": {
            name: [
                {
                    "row": i,
                    "question_id": rows[i]["question_id"],
                    "category": demo.category(rows[i]),
                }
                for i in indices
            ]
            for name, indices in partitions.items()
        },
        "counts": {
            name: dict(Counter(demo.category(rows[i]) for i in ids))
            for name, ids in partitions.items()
        },
        "heldout_status": "METADATA_ONLY_NOT_ASSEMBLED_OR_SCORED",
        "blindness": "Public data already structurally validated; not independently blind",
    }
    # Even grouped evidence IDs can appear as distractors in the other partition.
    used_for_review = prior + development
    reviewed_sessions = {s for i in used_for_review for s in rows[i]["haystack_session_ids"]}
    heldout_sessions = {s for i in heldout for s in rows[i]["haystack_session_ids"]}
    heldout_evidence = {s for i in heldout for s in rows[i]["answer_session_ids"]}
    split["shared_history_session_ids"] = len(reviewed_sessions & heldout_sessions)
    split["heldout_evidence_ids_present_in_review_histories"] = len(
        heldout_evidence & reviewed_sessions
    )
    split["split_sha256"] = digest(split)
    return split


def mapped_input(row, *, dated=False, recovery=False):
    payload, labels = demo.convert(row)
    if dated:
        # Dates in turn IDs survive CAP and accompany every retrieved chunk.
        # Message bodies and the question stay byte-for-byte unchanged. Metadata
        # is counted in serialization and can therefore reduce available evidence.
        for turn, mapping in zip(payload["history"], labels["message_mapping"], strict=True):
            date = demo.timestamp(mapping["source_date"]).strftime("%Y-%m-%dT%H:%M")
            turn["turn_id"] += "|session_date=" + date
            mapping["turn_id"] = turn["turn_id"]
        at = demo.timestamp(row["question_date"]).strftime("%Y-%m-%dT%H:%M")
        payload["system"] += (
            " Turn IDs carry source session_date metadata. These are session dates,"
            " not necessarily event dates; their timezone is unspecified."
            " File order need not be chronological. Question date: " + at + "."
        )
    payload["retrieval"] = {"recover_capped_window": recovery}
    demo.require(
        len(json.dumps(payload, ensure_ascii=False, indent=2).encode()) <= MAX_INSPECTION_BYTES,
        "inspection_input_too_large",
    )
    return payload, labels


def coverage(assembly, payload, labels):
    """Validate emitted slices and report full original-message coverage only."""
    originals = {t["turn_id"]: t["messages"][0] for t in payload["history"]}
    spans = defaultdict(list)
    window = {}
    retrieved = Counter()
    for wire in assembly["request"]["messages"]:
        content = wire["content"]
        if content.startswith("[WINDOW DATA]\n"):
            for turn in json.loads(content.split("\n", 1)[1]):
                tid = turn["turn"]
                demo.require(tid in originals and len(turn["messages"]) == 1, "invalid_window")
                message = turn["messages"][0]
                original = originals[tid]
                demo.require(message["role"] == original["role"], "invalid_window_role")
                window[tid] = message["content"]
                if message["content"] == original["content"]:
                    spans[tid].append((0, len(original["content"])))
        elif content.startswith("[RETRIEVED DATA]\n"):
            for chunk in json.loads(content.split("\n", 1)[1]):
                tid = chunk["turn"]
                demo.require(tid in originals, "unknown_retrieved_source")
                original = originals[tid]
                start, end = chunk["start"], chunk["end"]
                demo.require(
                    chunk["message"] == original["message_id"]
                    and type(start) is int
                    and type(end) is int
                    and 0 <= start < end <= len(original["content"])
                    and original["content"][start:end] == chunk["text"],
                    "invalid_retrieved_slice",
                )
                spans[tid].append((start, end))
                retrieved[tid] += 1
    details = []
    planned = set(assembly["diagnostics"]["planned_window_turn_ids"])
    for mapping in labels["message_mapping"]:
        if mapping["has_answer"] is not True:
            continue
        tid = mapping["turn_id"]
        length = len(originals[tid]["content"])
        covered = 0
        for start, end in sorted(spans[tid]):
            if start > covered:
                break
            covered = max(covered, end)
        details.append(
            {
                "turn_id": tid,
                "original_characters": length,
                "full_text_retained": bool(length) and covered == length,
                "planned_window": tid in planned,
                "emitted_window": tid in window,
                "window_is_capped": tid in window and window[tid] != originals[tid]["content"],
                "retrieved_chunks": retrieved[tid],
            }
        )
    return {
        "marked_messages": len(details),
        "full_marked_messages": sum(d["full_text_retained"] for d in details),
        "all_marked_messages": all(d["full_text_retained"] for d in details) if details else None,
        "details": details,
    }


def prior_diagnosis(directory):
    report = json.loads((directory / "report.json").read_text())
    cases = []
    for case in report["cases"]:
        root = directory / case["case"]
        payload = json.loads((root / "input.json").read_text())
        labels = json.loads((root / "labels.json").read_text())
        budgets = {}
        for budget in demo.BUDGETS:
            assembly = json.loads((root / f"assembly-{budget}.json").read_text())
            budgets[str(budget)] = {
                "coverage": coverage(assembly, payload, labels),
                "window_messages": len(assembly["diagnostics"]["planned_window_turn_ids"]),
                "finalizer_drops": len(assembly["diagnostics"]["drops"]),
            }
        low = {d["turn_id"]: d for d in budgets["900"]["coverage"]["details"]}
        high = budgets["3000"]["coverage"]["details"]
        losses = [
            d["turn_id"]
            for d in high
            if low[d["turn_id"]]["full_text_retained"] and not d["full_text_retained"]
        ]
        cases.append({"case": case["case"], "budgets": budgets, "lost_full_messages": losses})
    return {"source_sha256": report["source_sha256"], "cases": cases}


def summarize(runs):
    output = []
    for arm in ARMS:
        for budget in demo.BUDGETS:
            chosen = [r for r in runs if r["arm"] == arm and r["budget"] == budget]
            passed = [r for r in chosen if r["status"] == "ASSEMBLED"]
            output.append(
                {
                    "arm": arm,
                    "budget": budget,
                    "planned": len(chosen),
                    "assembled": len(passed),
                    "rejected": len(chosen) - len(passed),
                    "marked_messages": sum(r["coverage"]["marked_messages"] for r in passed),
                    "full_marked_messages": sum(
                        r["coverage"]["full_marked_messages"] for r in passed
                    ),
                    "cases_all_marked": sum(
                        r["coverage"]["all_marked_messages"] is True for r in passed
                    ),
                    "cases_without_marks": sum(
                        r["coverage"]["all_marked_messages"] is None for r in passed
                    ),
                    "cases_with_future_sessions": sum(
                        r["source_flags"]["sessions_after_question"] for r in chosen
                    ),
                }
            )
    return output


def paired_comparison(runs, left, right):
    by_key = {(r["row"], r["budget"], r["arm"]): r for r in runs}
    outcomes = Counter()
    for record in runs:
        if record["arm"] != left:
            continue
        other = by_key[(record["row"], record["budget"], right)]
        if record["status"] != "ASSEMBLED" or other["status"] != "ASSEMBLED":
            outcomes["rejected_pair"] += 1
            continue
        if record["coverage"]["marked_messages"] == 0:
            outcomes["no_annotations"] += 1
            continue
        delta = (
            other["coverage"]["full_marked_messages"] - record["coverage"]["full_marked_messages"]
        )
        outcomes["improved" if delta > 0 else "regressed" if delta < 0 else "unchanged"] += 1
    return {"left": left, "right": right, "outcomes": dict(outcomes)}


def html_report(report):
    table = "".join(
        f"<tr><td>{s['arm']}</td><td>{s['budget']}</td><td>{s['assembled']}/{s['planned']}</td>"
        f"<td>{s['full_marked_messages']}/{s['marked_messages']}</td><td>{s['cases_all_marked']}</td></tr>"
        for s in report["development_summary"]
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none';style-src 'unsafe-inline';base-uri 'none'">
<title>LongMemEval development review</title><style>
body{{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:20px;
color:#172b40;background:#edf2f7}}
table{{width:100%;border-collapse:collapse;background:white}}
td,th{{padding:12px;text-align:left;border-bottom:1px solid #ccd6df}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>LongMemEval · offline development review</h1>
<p>TEST_ONLY · No generated answers · Held-out rows not assembled or scored.</p>
<p>Full annotated-message coverage is not answer accuracy or answer-span recall.
Rejected conditions remain in the planned denominator;
annotation counts below cover assembled conditions only.</p>
<table><tr><th>Arm</th><th>Budget</th><th>Assembled</th><th>Complete marked messages</th>
<th>Cases with all marks</th></tr>{table}</table>
<h2>Paired development comparisons</h2><pre>{escaped(json.dumps(report["paired"], indent=2))}</pre>
<h2>Interpretation</h2><p>Recovery and date-aware mapping are experimental arms,
not adopted defaults.
Dates in source IDs are counted toward the budget. Source text/order and the question are unchanged;
dates are session dates with unknown timezone, not event dates. Future-session cases remain flagged,
not silently filtered or valid historical evaluation.
Larger budgets need not retain more complete evidence.</p>
<p>See report.json, split.json, prior-diagnosis.json and per-case private exports for details.
No inference authority is granted by these files.</p></html>"""


def run(source, prior, output):
    demo.require(not output.exists() and not output.is_symlink(), "output_exists")
    with offline_network():
        rows, source_hash, size = demo.read_source(source)
        demo.require(source_hash == demo.PUBLISHER_SHA256, "unexpected_source_identity")
        audit, _ = demo.audit_source(rows)
        prior_report = json.loads((prior / "report.json").read_text())
        demo.require(prior_report["source_sha256"] == source_hash, "prior_source_mismatch")
        prior_hashes = {
            p.relative_to(prior).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in prior.rglob("*")
            if p.is_file()
        }
        exposed = [c["source_row"] for c in prior_report["cases"]]
        split = make_split(rows, exposed)
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        demo.write_json(output / "split.json", split)
        plan = {
            "status": "TEST_ONLY",
            "source_sha256": source_hash,
            "source_bytes": size,
            "split_sha256": split["split_sha256"],
            "runtime": runtime_identity(),
            "scripts": {
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("longmemeval_review.py", "longmemeval_demo.py", "incident_demo.py")
            },
            "arms": {
                name: {"dated": values[0], "recover_capped_window": values[1]}
                for name, values in ARMS.items()
            },
            "budgets": list(demo.BUDGETS),
            "cap": 35,
            "retrieval_reserve": 280,
            "summary_reserve": 0,
            "inference_calls": 0,
            "heldout_authorized": False,
            "date_mapping": "turn-id-session-date-v1",
            "prior_file_hashes": prior_hashes,
        }
        demo.write_json(output / "plan.json", plan)
        demo.write_json(output / "prior-diagnosis.json", prior_diagnosis(prior))
        runs = []
        selections = [("prior_demo", i) for i in exposed] + [
            ("development", r["row"]) for r in split["partitions"]["development"]
        ]
        for position, (partition, index) in enumerate(selections, 1):
            row = rows[index]
            directory = output / f"row-{index:03d}"
            directory.mkdir(mode=0o700)
            for arm, (dated, recovery) in ARMS.items():
                base = {
                    "row": index,
                    "partition": partition,
                    "category": demo.category(row),
                    "arm": arm,
                    "source_flags": demo.validate_row(row),
                }
                try:
                    payload, labels = mapped_input(row, dated=dated, recovery=recovery)
                    demo.write_json(directory / f"input-{arm}.json", payload)
                    demo.write_json(directory / f"labels-{arm}.json", labels)
                    job = parse_job(payload, Settings())
                except (demo.DataError, ContextEngineError):
                    runs.extend(
                        {**base, "budget": b, "status": "INPUT_REJECTED"} for b in demo.BUDGETS
                    )
                    continue
                for budget in demo.BUDGETS:
                    record = {**base, "budget": budget}
                    try:
                        result = job.run(input_cap=budget)
                        assembly = result.to_dict(include_content=True)
                        record.update(
                            {
                                "status": "ASSEMBLED",
                                "estimated_tokens": result.diagnostics.estimate.estimated_tokens,
                                "request_sha256": digest(assembly["request"]),
                                "coverage": coverage(assembly, payload, labels),
                                "planned_window_messages": len(
                                    result.diagnostics.planned_window_turn_ids
                                ),
                                "finalizer_drops": len(result.diagnostics.drops),
                            }
                        )
                        demo.require(record["estimated_tokens"] <= budget, "budget_violation")
                        demo.write_json(directory / f"assembly-{arm}-{budget}.json", assembly)
                        # Original demo baseline must reproduce exactly before comparing arms.
                        if partition == "prior_demo" and arm == "baseline":
                            original_case = next(
                                c for c in prior_report["cases"] if c["source_row"] == index
                            )
                            old = json.loads(
                                (
                                    prior / original_case["case"] / f"assembly-{budget}.json"
                                ).read_text()
                            )
                            demo.require(
                                old["request"] == assembly["request"], "prior_baseline_drift"
                            )
                    except ContextEngineError:
                        record["status"] = "ASSEMBLY_REJECTED"
                    runs.append(record)
            print(
                json.dumps({"completed_cases": position, "planned_cases": len(selections)}),
                flush=True,
            )
        with source.open("rb") as handle:
            demo.require(
                hashlib.file_digest(handle, "sha256").hexdigest() == source_hash, "source_changed"
            )
        demo.require(
            prior_hashes
            == {
                p.relative_to(prior).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in prior.rglob("*")
                if p.is_file()
            },
            "prior_changed",
        )
        development = [r for r in runs if r["partition"] == "development"]
        report = {
            "status": "TEST_ONLY",
            "answer_quality": "NOT_EVALUATED",
            "inference_calls": 0,
            "source_unchanged": True,
            "prior_unchanged": True,
            "audit": audit,
            "plan_sha256": digest(plan),
            "split_sha256": split["split_sha256"],
            "planned_runs": len(selections) * len(ARMS) * len(demo.BUDGETS),
            "heldout_assembled": 0,
            "heldout_scored": 0,
            "development_summary": summarize(development),
            "prior_demo_summary": summarize([r for r in runs if r["partition"] == "prior_demo"]),
            "paired": [
                paired_comparison(development, a, b)
                for a, b in (
                    ("baseline", "recovery"),
                    ("baseline", "dated"),
                    ("dated", "dated_recovery"),
                )
            ],
            "runs": runs,
        }
        demo.require(len(runs) == report["planned_runs"], "missing_run_slots")
        demo.write_json(output / "report.json", report)
        with (output / "index.html").open("x", encoding="utf-8") as handle:
            handle.write(html_report(report))
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--prior-demo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.input, args.prior_demo, args.output)
    except (demo.DataError, ContextEngineError, OSError, RuntimeError, ValueError, KeyError):
        print("Review failed; inspect source identity, prior demo, limits and new output path.")
        return 1
    print(
        json.dumps(
            {
                "planned_runs": report["planned_runs"],
                "assembled": sum(r["status"] == "ASSEMBLED" for r in report["runs"]),
                "inference_calls": 0,
            }
        )
    )
    return 0 if all(r["status"] == "ASSEMBLED" for r in report["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
