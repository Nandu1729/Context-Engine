"""Offline-only C09 CLI. Test response import is never live quality evidence."""

import argparse
from pathlib import Path

from ..corpus import strict_json
from . import export, load, prepare
from .scoring import score_test, scoring_freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "prepare", "score-test"))
    parser.add_argument("--split", choices=("all", "development", "evaluation"), default="all")
    parser.add_argument("--output")
    parser.add_argument("--retention", action="store_true")
    parser.add_argument("--responses", type=Path)
    args = parser.parse_args()
    if args.command == "check":
        load()
        scoring_freeze()
        print("heldout-v1: fixture hashes and contracts PASS; live approval pending")
    else:
        if not args.output:
            parser.error("prepare requires a fresh --output directory")
        report = prepare(split=args.split, retention=args.retention or args.command == "score-test")
        if args.command == "score-test":
            if not args.responses:
                parser.error("score-test requires a TEST_ONLY --responses file")
            with args.responses.open("rb") as stream:
                raw = stream.read(2_000_001)
            if len(raw) > 2_000_000:
                parser.error("response file exceeds limit")
            report = score_test(report, strict_json(raw.decode("utf-8")))
        export(report, args.output)
        print(f"TEST_ONLY: {report['planned_slots']} slots; zero provider calls")


if __name__ == "__main__":
    main()
