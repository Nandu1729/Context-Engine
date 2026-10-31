"""One offline local milestone check using existing SDK and synthetic memory demo.

Run from the repository: python -m scripts.local_demo
No API credentials, provider, original dataset or persistent project database used.
"""

import argparse
import json
from pathlib import Path

from context_engine import __version__, assemble_context
from context_engine.config import Settings
from context_engine.errors import ContextEngineError, ContractError
from context_engine.inspection import load_job
from context_engine.layers.common import history_digest
from context_engine.memory.demo import memory_demo
from context_engine.tokens import TiktokenCounter
from scripts.incident_demo import SAMPLE, offline_network


def run():
    with offline_network():
        job = load_job(SAMPLE, Settings())
        before = history_digest(job.arguments["history"])
        # The actual public SDK call, not a fake answer or saved result.
        result = assemble_context(**job.arguments, token_counter=TiktokenCounter(job.tokenizer))
        checks = {
            "within_estimated_budget": result.diagnostics.remaining_tokens >= 0,
            "original_history_unchanged": before == history_digest(job.arguments["history"]),
            "system_policy_preserved": result.messages[0]["content"] == job.arguments["system"],
            "question_preserved": result.messages[-1]["content"] == job.arguments["question"],
            "deployment_record_retrieved": "t01" in result.diagnostics.retrieved_turn_ids,
            "rollback_version_present": "checkout-v41" in str(result.messages),
        }
        if not all(checks.values()):
            raise ContractError("Synthetic SDK demo failed")
        lifecycle = memory_demo()
        if lifecycle["status"] != "PASS" or not all(lifecycle["checks"].values()):
            raise ContractError("Synthetic lifecycle demo failed")
        return {
            "status": "PASS",
            "milestone": "LOCAL_DEMO_ONLY",
            "package_version": __version__,
            "synthetic": True,
            "inference_calls": 0,
            "answer_quality": "NOT_EVALUATED",
            "enterprise_approved": False,
            "content_included": False,
            "sdk": {
                "source_turns": len(job.arguments["history"]),
                "estimated_input_tokens": result.diagnostics.estimate.estimated_tokens,
                "input_allowance": result.diagnostics.input_allowance,
                "sample_cap_tokens": job.arguments["cap_config"].max_tokens,
                "checks": checks,
            },
            "memory": lifecycle,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional NEW metadata-only JSON file")
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error("Choose a new output path; existing reports are never overwritten")
    try:
        report = run()
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, indent=2)
                stream.write("\n")
    except (ContextEngineError, OSError, RuntimeError):
        print("DEMO FAILED: check local dependencies, cached tokenizer and output permissions.")
        print("No model calls were made; do not add an API key to fix this demo.")
        return 1
    print("PASS: local synthetic demo (not production qualification)")
    print(
        f"SDK: {report['sdk']['source_turns']} sample turns -> "
        f"{report['sdk']['estimated_input_tokens']}/{report['sdk']['input_allowance']} "
        "estimated input tokens; deployment and rollback evidence retained."
    )
    print("Memory: restart, index reuse, deletion and deletion-safe restore checks passed.")
    print("No AI answer generated. No API key needed. No model calls made.")
    print("Next: open output/local-demo-001/index.html and follow docs/LOCAL_QUICKSTART.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
