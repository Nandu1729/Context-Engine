#!/usr/bin/env python3
"""Re-grade completed live runs with strict-v1 and lenient-v2 grading (offline, T8).

Reads each run's private receipts and writes a content-free `grading.json` next to
its public report. Receipts and the frozen strict grader are never modified.
"""

import json
from pathlib import Path

from context_engine.evaluation.corpus import aliases, load_bundle
from context_engine.evaluation.grading import GRADERS

ROOT = Path(__file__).resolve().parents[1]
RUNS = ("strategy-accuracy-900-001", "semantic-accuracy-900-001")


def regrade(run: str, facts: dict) -> dict:
    report = json.loads((ROOT / "output" / run / "report.json").read_text())
    private = ROOT / "output/private" / run
    groups, rows = {}, []
    for row in report["rows"]:
        result = json.loads((private / f"receipt-{row['slot']:03d}.json").read_text())["result"]
        group = groups.setdefault(row["strategy"], {"answered": 0} | dict.fromkeys(GRADERS, 0))
        graded = dict.fromkeys(GRADERS)
        if result["completion"] is not None:
            group["answered"] += 1
            for name, grader in GRADERS.items():
                graded[name] = result["status"] == "success" and grader(
                    result["completion"]["content"], aliases(facts[row["fact_id"]])
                )
                group[name] += graded[name]
        # The strict result must reproduce the original report exactly.
        if graded["strict-v1"] != row["correct"]:
            raise ValueError(f"strict-v1 differs from the saved report at slot {row['slot']}")
        rows.append({k: row[k] for k in ("slot", "fact_id", "strategy")} | graded)
    return {"run": run, "graders": list(GRADERS), "strategies": groups, "rows": rows}


def main():
    facts = {f["fact_id"]: f for f in load_bundle().facts}
    for run in RUNS:
        value = regrade(run, facts)
        path = ROOT / "output" / run / "grading.json"
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        print(run, json.dumps(value["strategies"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
