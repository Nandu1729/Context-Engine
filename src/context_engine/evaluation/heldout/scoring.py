"""Evaluator-only retention and strictly TEST_ONLY response validation/scoring."""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict

from ...errors import BenchmarkError
from ...models import canonical_json
from ..corpus import strict_json
from . import _root, load, prepare


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def scoring_freeze():
    root = _root(None)
    raw = root.joinpath("scoring_protocol.json").read_bytes()
    frozen = strict_json(root.joinpath("scoring_manifest.json").read_text())
    if frozen != {"id": "heldout-scoring-v1", "sha256": hashlib.sha256(raw).hexdigest()}:
        raise BenchmarkError("Scoring protocol freeze mismatch")
    return frozen


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def contains(text, literal):
    return (
        re.search(r"(?<!\w)" + re.escape(normalize(literal)) + r"(?!\w)", normalize(text))
        is not None
    )


def retained(case, truth, result):
    """Inspect actual rendered data, not mere presence of original source IDs."""
    if case["category"] == "no_answer":
        return None
    fragments = defaultdict(list)
    for block in result.blocks:
        if not block.content:
            continue
        if block.kind.value == "window":
            for turn in json.loads(block.content):
                for index, message in enumerate(turn["messages"]):
                    # Fixture tN contains exactly one message mN; filler IDs never qualify.
                    if index == 0 and turn["turn"].startswith("t"):
                        fragments["m" + turn["turn"][1:]].append(message["content"])
        elif block.kind.value == "retrieved":
            for chunk in json.loads(block.content):
                fragments[chunk["message"]].append(chunk["text"])
    if case["category"] == "contradictory":
        return all(
            any(normalize(text) in normalize(fragment) for fragment in fragments[f"m{i}"])
            for i, (_, text) in enumerate(case["messages"])
        )
    return all(
        any(contains(fragment, truth["answer"]) for fragment in fragments[source])
        for source in truth["sources"]
    )


def empty_responses(preparation):
    return {
        "schema_version": 1,
        "provenance": "TEST_ONLY",
        "preparation_hash": fingerprint(preparation),
        "responses": [],
    }


def score_test(preparation, recorded):
    """Reject forged/stale plans, duplicate/mismatched answers and all live labels."""
    freeze = scoring_freeze()
    try:
        if preparation != prepare(split=preparation["split"], retention=True):
            raise ValueError("preparation does not reproduce")
        if (
            set(recorded) != {"schema_version", "provenance", "preparation_hash", "responses"}
            or type(recorded["schema_version"]) is not int
            or recorded["schema_version"] != 1
            or recorded["provenance"] != "TEST_ONLY"
            or recorded["preparation_hash"] != fingerprint(preparation)
            or not isinstance(recorded["responses"], list)
            or len(recorded["responses"]) > preparation["planned_slots"]
        ):
            raise ValueError("recording envelope")

        def key(row):
            return row["case"], row["variant"], row["budget"]

        planned = {key(row): row for row in preparation["rows"]}
        answers = {}
        for row in recorded["responses"]:
            if (
                set(row) != {"case", "variant", "budget", "request_hash", "status", "answer"}
                or type(row["budget"]) is not int
                or key(row) not in planned
                or key(row) in answers
                or planned[key(row)]["status"] != "PREPARED"
                or row["request_hash"] != planned[key(row)]["request_hash"]
                or row["status"] not in ("response", "error")
                or (
                    row["status"] == "response"
                    and (not isinstance(row["answer"], str) or len(row["answer"]) > 16000)
                )
                or (row["status"] == "error" and row["answer"] is not None)
            ):
                raise ValueError("response binding")
            answers[key(row)] = row
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkError("Invalid TEST_ONLY response evidence") from exc
    _, truth, _, _ = load()
    rows = []
    groups = defaultdict(
        lambda: {
            "planned": 0,
            "responded": 0,
            "correct": 0,
            "forbidden": 0,
            "retention_eligible": 0,
            "retained": 0,
        }
    )
    for plan in preparation["rows"]:
        answer = answers.get(key(plan))
        status = (
            "required_non_fit"
            if plan["status"] != "PREPARED"
            else answer["status"]
            if answer
            else "missing"
        )
        expected = truth[plan["case"]]
        responded = status == "response"
        correct = responded and normalize(answer["answer"]) == normalize(expected["answer"])
        forbidden = responded and any(
            contains(answer["answer"], word) for word in expected["forbidden"]
        )
        row = {k: plan[k] for k in ("case", "split", "variant", "budget", "category", "retained")}
        row.update(status=status, correct=correct, forbidden=forbidden)
        rows.append(row)
        grouping = tuple(plan[k] for k in ("split", "variant", "budget", "category"))
        group = groups[grouping]
        group["planned"] += 1
        group["responded"] += responded
        group["correct"] += correct
        group["forbidden"] += forbidden
        group["retention_eligible"] += plan["retained"] is not None
        group["retained"] += plan["retained"] is True
    return {
        "schema_version": 1,
        "status": "TEST_ONLY",
        "kind": "scorer_verification",
        "provider_calls": 0,
        "answer_quality": "NOT_EVALUATED",
        "provider_calibration": "NOT_EVALUATED",
        "provider_cost": "NOT_EVALUATED",
        "scoring_freeze": freeze,
        "preparation_hash": fingerprint(preparation),
        "recording_hash": fingerprint(recorded),
        "planned_slots": len(rows),
        "synthetic_correct": sum(r["correct"] for r in rows),
        "synthetic_responded": sum(r["status"] == "response" for r in rows),
        "missing": sum(r["status"] == "missing" for r in rows),
        "errors": sum(r["status"] == "error" for r in rows),
        "groups": [
            dict(zip(("split", "variant", "budget", "category"), k, strict=True), **v)
            for k, v in sorted(groups.items())
        ],
        "rows": rows,
    }
