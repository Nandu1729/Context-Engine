"""Fixed offline development review;never a new model-answer run."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from context_engine.config import Settings
from context_engine.inspection import parse_job
from context_engine.tokens import TiktokenCounter
from scripts import retrieval_diversity_candidate as candidate
from scripts import retrieval_quality_probe as probe
from scripts.incident_demo import offline_network
from scripts.longmemeval_demo import write_json
from scripts.longmemeval_review import coverage

ROOT = candidate.ROOT
PRIOR = ROOT / "output/private/longmemeval-review-001"
PROTOCOL = ROOT / "docs/C11_DIVERSITY_DEVELOPMENT_PROTOCOL.md"
SPLIT = "aab5693329fa716acd05621b4d791e508779c6e80471e22e94021d6537229279"


def run(output):
    with offline_network():
        synthetic = json.loads((ROOT / "output/retrieval-diversity-001.json").read_text())
        if (
            synthetic["continuation_gate"] != "PASS"
            or synthetic["identity"] != candidate.identity()
        ):
            raise ValueError("Synthetic continuation gate or identity mismatch")
        if probe.runtime_identity() != synthetic["runtime"]:
            raise ValueError("Runtime changed")
        split = json.loads((PRIOR / "split.json").read_text())
        if candidate.digest({k: v for k, v in split.items() if k != "split_sha256"}) != SPLIT:
            raise ValueError("Split changed")
        cases = split["partitions"]["development"]
        if len(cases) != 35:
            raise ValueError("Unexpected development partition")
        paths = [
            PRIOR / "split.json",
            Path(__file__),
            PROTOCOL,
            ROOT / "scripts/longmemeval_review.py",
            ROOT / "scripts/longmemeval_demo.py",
            ROOT / "scripts/incident_demo.py",
        ]
        for case in cases:
            directory = PRIOR / f"row-{case['row']:03d}"
            paths += [
                directory / name
                for name in (
                    "input-dated.json",
                    "labels-dated.json",
                    "assembly-dated-900.json",
                    "assembly-dated-3000.json",
                )
            ]
        hashes = {str(p.relative_to(ROOT)): candidate.sha(p) for p in paths}
        plan = {
            "candidate": candidate.identity(),
            "runtime": synthetic["runtime"],
            "hashes": hashes,
            "cases": cases,
            "budgets": [900, 3000],
            "inference_calls": 0,
            "heldout_used": False,
        }
        output.mkdir(mode=0o700, exist_ok=False)
        write_json(output / "plan.json", plan)
        rows = []
        for case in cases:
            directory = PRIOR / f"row-{case['row']:03d}"
            payload = json.loads((directory / "input-dated.json").read_text())
            job = parse_job(payload, Settings())
            for budget in (900, 3000):
                arguments = dict(job.arguments)
                arguments["budget"] = replace(arguments["budget"], input_cap=budget)
                result = candidate.candidate_assemble(
                    **arguments, token_counter=TiktokenCounter(job.tokenizer)
                ).to_dict(include_content=True)
                baseline = json.loads((directory / f"assembly-dated-{budget}.json").read_text())
                new_messages, old_messages = (
                    result["request"]["messages"],
                    baseline["request"]["messages"],
                )
                if (
                    new_messages[0] != old_messages[0]
                    or new_messages[-1] != old_messages[-1]
                    or candidate.data(new_messages, "[WINDOW DATA]")
                    != candidate.data(old_messages, "[WINDOW DATA]")
                ):
                    raise ValueError("Required content or WINDOW changed")
                if result["diagnostics"]["estimate"]["estimated_tokens"] > budget:
                    raise ValueError("Candidate over budget")
                # Post-assembly scoring boundary;labels never enter the candidate.
                labels = json.loads((directory / "labels-dated.json").read_text())
                rows.append(
                    {
                        **case,
                        "budget": budget,
                        "baseline_coverage": coverage(baseline, payload, labels),
                        "candidate_coverage": coverage(result, payload, labels),
                        "lost_retrieved_spans": candidate.lost_spans(old_messages, new_messages),
                        "baseline_tokens": baseline["diagnostics"]["estimate"]["estimated_tokens"],
                        "candidate_tokens": result["diagnostics"]["estimate"]["estimated_tokens"],
                        "candidate_request_sha256": candidate.digest(result["request"]),
                        "candidate_config_fingerprint": result["diagnostics"]["config_fingerprint"],
                        "finalizer_drops": result["diagnostics"]["drops"],
                    }
                )
            print(json.dumps({"completed": len(rows), "planned": 70}), flush=True)
        if hashes != {str(p.relative_to(ROOT)): candidate.sha(p) for p in paths}:
            raise ValueError("Source files changed")
        if candidate.identity() != plan["candidate"] or probe.runtime_identity() != plan["runtime"]:
            raise ValueError("Candidate/runtime changed")
        report = {
            "status": "DIAGNOSTIC_ONLY",
            "plan_sha256": candidate.digest(plan),
            "rows": rows,
            "inference_calls": 0,
            "heldout_used": False,
            "answer_quality": "NOT_EVALUATED",
            "default_adopted": False,
            "source_exports_unchanged": True,
        }
        write_json(output / "report.json", report)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.output)


if __name__ == "__main__":
    main()
