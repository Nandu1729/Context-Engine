"""Connect synthetic or converted dataset history to the SDK; no model or storage."""

import argparse
import json
from pathlib import Path

from context_engine.config import Settings
from context_engine.errors import ContextEngineError
from context_engine.inspection import load_job
from examples.sdk_quickstart import prepare_context
from scripts.incident_demo import offline_network

LONGMEMEVAL_INPUT = (
    Path(__file__).resolve().parent
    / "output/private/longmemeval-review-001/row-049/input-baseline.json"
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", help="Skip the interactive question prompt")
    parser.add_argument("--show-context", action="store_true", help="Display prepared messages")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--longmemeval", action="store_true", help="Use the existing converted development row 49"
    )
    source.add_argument("--input", type=Path, help="Converted inspection JSON, not the raw corpus")
    args = parser.parse_args(argv)
    input_path = LONGMEMEVAL_INPUT if args.longmemeval else args.input
    if input_path is not None and args.question is not None:
        parser.error("Dataset mode uses its saved question; remove --question")
    if args.longmemeval:
        print("LongMemEval development row 49: existing baseline input, recovery OFF.")
    elif input_path is not None:
        print("Converted input: using its saved history, question and configuration.")
    else:
        print("Sample incident only.")
    print("No model calls, saved conversations or API keys. Reference answers are not loaded.")
    try:
        with offline_network():
            if input_path is not None:
                # Strict, bounded schema rejects answer/label fields. Never open
                # the sibling labels file or load the entire original corpus.
                job = load_job(input_path, Settings())
                result = job.run()
                print(f"Loaded source turns: {len(job.arguments['history'])}")
            else:
                question = args.question
                if question is None:
                    question = input("Ask about the sample incident: ")
                if not question.strip():
                    print("Please enter a question about the sample incident.")
                    return 1
                result = prepare_context(question)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; nothing saved.")
        return 130
    except (ContextEngineError, OSError, RuntimeError):
        print(
            "Could not prepare context. Check the input file, question size and cached tokenizer."
        )
        print(
            "Use converted inspection JSON, not labels or the raw dataset. No download attempted."
        )
        return 1
    print("CONNECTED: your application received prepared context, not an AI answer.")
    print(
        f"Estimated input tokens: {result.diagnostics.estimate.estimated_tokens}"
        f"/{result.diagnostics.input_allowance}"
    )
    if args.show_context:
        print(json.dumps(result.messages, indent=2, ensure_ascii=False))
    else:
        print("Use --show-context to display the prepared messages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
