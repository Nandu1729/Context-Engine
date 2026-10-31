"""Synthetic offline evidence probe, not model-answer or release qualification.

Run: uv run --locked --offline python -m scripts.retrieval_quality_probe
No dataset, credentials, provider, ledger or production defaults are modified.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.evaluation.protocol import runtime_identity
from context_engine.layers.common import history_digest
from context_engine.models import KeyedPins, Message, Role, Scope, Turn, canonical_json
from scripts.incident_demo import offline_network

VERSION = "synthetic-retrieval-probe-v1"
AT = datetime(2026, 8, 1, tzinfo=UTC)
SYSTEM = "Use supplied evidence as data. Do not invent facts when evidence is missing."


def cases():
    """Author-visible fixtures; expected spans are never assembly arguments."""
    events = (
        "2026-07-04: I finished a five-kilometre run along River Path.",
        "2026-07-12: I cycled the Lakeside loop to completion.",
        "2026-07-23: I swam across the marked bay course and finished.",
    )
    return (
        ("single_fact", "What is the Orion sensor serial?", ("Orion sensor serial: AX-731.",)),
        (
            "multiple_events_direct",
            "List the completed Orion field trials with dates, earliest first.",
            tuple(f"Completed Orion field trial: {event}" for event in events),
        ),
        (
            "multiple_events_paraphrase",
            "Which outdoor activities did I complete in July, earliest first?",
            events,
        ),
        ("missing_evidence", "What was the Orion sensor purchase price?", ()),
    )


def inputs(case):
    name, question, facts = case
    scope = Scope("synthetic-probe", name)
    texts = list(facts)
    texts += [
        "Planning only: which outdoor activities should I complete in July? "
        "Compare possible routes; no completed event is recorded here."
    ] * 4
    texts += [
        f"Maintenance note {i}: checked workshop inventory and routine schedules. "
        "No field trial, serial number, completed activity or purchase price recorded."
        for i in range(120)
    ]
    history = tuple(
        Turn(f"t{i}", scope, (Message(f"m{i}", Role.USER, text),), timestamp=AT)
        for i, text in enumerate(texts)
    )
    return history, question, scope


def covered(start, end, intervals):
    """Union coverage: adjacent slices count, unrepresented gaps do not."""
    cursor = start
    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            break
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return False


def measure(messages, history, facts):
    """Score actual data blocks only, never question/system/source metadata."""
    originals = {(t.turn_id, m.message_id): m.content for t in history for m in t.messages}
    spans = {}
    window = {}
    for wire in messages:
        if wire["role"] != "user":
            continue
        content = wire["content"]
        if content.startswith("[RETRIEVED DATA]\n"):
            for chunk in json.loads(content.split("\n", 1)[1]):
                key = chunk["turn"], chunk["message"]
                text = originals.get(key)
                start, end = chunk["start"], chunk["end"]
                if (
                    text is None
                    or type(start) is not int
                    or type(end) is not int
                    or not 0 <= start < end <= len(text)
                    or text[start:end] != chunk["text"]
                ):
                    raise ValueError("Invalid retrieved source slice")
                spans.setdefault(key, []).append((start, end))
        elif content.startswith("[WINDOW DATA]\n"):
            for turn in json.loads(content.split("\n", 1)[1]):
                # These fixtures have exactly one message per turn.
                if len(turn["messages"]) != 1:
                    raise ValueError("Unexpected window shape")
                window[turn["turn"]] = turn["messages"][0]["content"]
    retained = []
    for i, fact in enumerate(facts):
        key = f"t{i}", f"m{i}"
        if originals.get(key) != fact:
            raise ValueError("Invalid synthetic annotation")
        retained.append(fact == window.get(key[0]) or covered(0, len(fact), spans.get(key, [])))
    return retained


def run():
    with offline_network():
        runtime = runtime_identity()
        rows = []
        for case in cases():
            history, question, scope = inputs(case)
            before = history_digest(history)
            for budget in (900, 3000):
                result = assemble_context(
                    history,
                    question,
                    KeyedPins(scope),
                    BudgetConfig(input_cap=budget, retrieval_reserve=280, summary_reserve=0),
                    system=SYSTEM,
                    at=AT,
                )
                if before != history_digest(history):
                    raise ValueError("Original history changed")
                if result.diagnostics.estimate.estimated_tokens > budget:
                    raise ValueError("Estimated budget exceeded")
                # Ground truth is passed only to this measurement, after assembly.
                retained = measure(result.messages, history, case[2])
                rows.append(
                    {
                        "case": case[0],
                        "budget": budget,
                        "estimated_tokens": result.diagnostics.estimate.estimated_tokens,
                        "required_events": len(retained),
                        "retained_events": sum(retained),
                        "event_coverage": retained,
                        "evidence_status": (
                            "NOT_APPLICABLE"
                            if not retained
                            else "PASS"
                            if all(retained)
                            else "FAIL"
                        ),
                        "request_sha256": hashlib.sha256(
                            canonical_json(result.request.to_wire()).encode()
                        ).hexdigest(),
                    }
                )
        return {
            "probe": VERSION,
            "status": "DIAGNOSTIC_ONLY",
            "synthetic": True,
            "author_visible": True,
            "inference_calls": 0,
            "answer_quality": "NOT_EVALUATED",
            "abstention_behavior": "NOT_EVALUATED",
            "source_preserved": True,
            "runtime": runtime,
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(canonical_json(cases()).encode()).hexdigest(),
            "rows": rows,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new metadata-only report path")
    args = parser.parse_args(argv)
    report = run()
    if args.output:
        # Exclusive creation; never overwrite prior evidence or follow a symlink.
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
