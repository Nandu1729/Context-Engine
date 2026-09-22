"""Frozen, packaged synthetic resources; ground truth never enters an inspection job."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path

from ..config import Settings
from ..errors import BenchmarkError, ContextEngineError
from ..inspection import parse_job
from ..models import canonical_json
from .grading import normalize, present

PARTS = ("scenario", "ground_truth", "summary_fixture", "protocol", "pin_retention")
MAX_BYTES = 2_000_000


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def strict_json(raw: str, *, maximum: int = MAX_BYTES) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BenchmarkError("Duplicate benchmark JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise BenchmarkError("Nonfinite benchmark JSON number")

    try:
        if len(raw.encode("utf-8")) > maximum:
            raise BenchmarkError("Benchmark document exceeds byte limit")
        parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
        if not isinstance(parsed, dict):
            raise BenchmarkError("Benchmark document must be an object")
        canonical_json(parsed)
        return parsed
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise BenchmarkError("Malformed benchmark JSON") from None


@dataclass(frozen=True)
class Bundle:
    parts: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if not isinstance(self.parts, tuple) or tuple(name for name, _ in self.parts) != PARTS:
            raise BenchmarkError("Incomplete benchmark bundle")
        for _, raw in self.parts:
            strict_json(raw)

    def get(self, name: str) -> dict:
        return strict_json(dict(self.parts)[name])  # Fresh objects, no mutable shared fixtures.

    @property
    def hashes(self) -> dict:
        return {name: hashlib.sha256(raw.encode("utf-8")).hexdigest() for name, raw in self.parts}

    def job(self, question: str):
        scenario = self.get("scenario")
        scenario.pop("scenario_id")
        scenario["question"] = question
        return parse_job(scenario, Settings.from_env({}))

    @property
    def facts(self) -> tuple[dict, ...]:
        return tuple(self.get("ground_truth")["facts"])

    def fact(self, identifier: str) -> dict:
        for fact in self.facts:
            if fact["fact_id"] == identifier:
                return fact
        raise BenchmarkError("Unknown benchmark fact")


def read_resource(name: str, directory: Path | None = None) -> str:
    path = directory / name if directory else resources.files(__package__).joinpath("data", name)
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise BenchmarkError("Benchmark document exceeds byte limit")
        return raw.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        raise BenchmarkError("Cannot read benchmark resource") from None


def load_bundle(directory: Path | None = None) -> Bundle:
    return Bundle(tuple((name, read_resource(name + ".json", directory)) for name in PARTS))


def aliases(fact: dict) -> tuple[str, ...]:
    return (fact["expected"], *fact["aliases"])


def check_fixture(bundle: Bundle) -> None:
    """V1 schema, cardinality, relationships, plant locations and unique metadata."""
    try:
        scenario, truth = bundle.get("scenario"), bundle.get("ground_truth")
        summary, protocol = bundle.get("summary_fixture"), bundle.get("protocol")
        if any(
            type(part["schema_version"]) is not int or part["schema_version"] != 1
            for part in (scenario, truth, summary, protocol, bundle.get("pin_retention"))
        ):
            raise BenchmarkError("Unsupported benchmark schema")
        if set(truth) != {"schema_version", "scenario_id", "facts"}:
            raise BenchmarkError("Unexpected ground-truth fields")
        if any(
            part["scenario_id"] != scenario["scenario_id"] for part in (truth, summary, protocol)
        ):
            raise BenchmarkError("Scenario identity mismatch")
        job = bundle.job("Fixture validation")
        from ..layers.summarize import SummarySnapshot
        from ..models import Pin

        if set(summary) != {
            "schema_version",
            "scenario_id",
            "policy_version",
            "created_at",
            "content",
        }:
            raise BenchmarkError("Unexpected summary fields")
        snapshot = SummarySnapshot.from_history(
            scope=job.arguments["pinned_facts"].scope,
            content=summary["content"],
            history=job.arguments["history"],
            policy_version=summary["policy_version"],
            created_at=datetime.fromisoformat(summary["created_at"]),
        )
        if snapshot.created_at > job.arguments["at"]:
            raise BenchmarkError("Frozen summary is not available at evaluation time")
        fixture = bundle.get("pin_retention")
        if set(fixture) != {"schema_version", "fixture_id", "question", "key", "value", "origin"}:
            raise BenchmarkError("Unexpected separate pin fixture fields")
        Pin(
            scope=job.arguments["pinned_facts"].scope,
            key=fixture["key"],
            value=fixture["value"],
            origin=fixture["origin"],
            effective_at=job.arguments["at"],
        )
        if (
            not isinstance(fixture["question"], str)
            or not fixture["question"].strip()
            or present(fixture["question"], (fixture["value"],))
        ):
            raise BenchmarkError("Invalid separate pin question")
        # Constructed carrier validation catches duplicate/mixed source identity without inference.
        from ..context import ContextCarrier
        from ..models import Message, Role

        history = job.arguments["history"]
        ContextCarrier(
            job.arguments["pinned_facts"].scope,
            history,
            history,
            job.arguments["pinned_facts"],
            Message("fixture-question", Role.USER, "Q"),
        )
        if len(history) != 100 or [t.turn_id for t in history] != [f"t{i}" for i in range(1, 101)]:
            raise BenchmarkError("Expected ordered 100-turn fixture")
        if len(bundle.facts) != 31 or len({f["fact_id"] for f in bundle.facts}) != 31:
            raise BenchmarkError("Expected exactly 31 unique facts")
        turns = {t.turn_id: t for t in history}
        seen_answers, seen_questions = set(), set()
        fields = {
            "fact_id",
            "expected",
            "aliases",
            "source_turn_id",
            "source_message_id",
            "question",
            "zone",
        }
        for fact in bundle.facts:
            if set(fact) != fields or not isinstance(fact["aliases"], list):
                raise BenchmarkError("Unexpected fact fields")
            if any(
                not isinstance(fact[k], str) or not fact[k].strip() for k in fields - {"aliases"}
            ):
                raise BenchmarkError("Invalid fact text")
            values = aliases(fact)
            if any(not isinstance(value, str) or not normalize(value) for value in values):
                raise BenchmarkError("Invalid answer alias")
            normalized = {normalize(value) for value in values}
            if len(normalized) != len(values) or seen_answers & normalized:
                raise BenchmarkError("Ambiguous answer aliases")
            seen_answers |= normalized
            if normalize(fact["question"]) in seen_questions:
                raise BenchmarkError("Duplicate probe question")
            seen_questions.add(normalize(fact["question"]))
            turn = turns[fact["source_turn_id"]]
            message = next(m for m in turn.messages if m.message_id == fact["source_message_id"])
            if not present(message.content, (fact["expected"],)):
                raise BenchmarkError("Planted value missing from declared source")
            locations = [
                (t.turn_id, m.message_id)
                for t in history
                for m in t.messages
                if present(m.content, values)
            ]
            if locations != [(turn.turn_id, message.message_id)]:
                raise BenchmarkError("Fact appears outside its declared source")
            number = int(turn.turn_id[1:])
            if fact["zone"] != ("early" if number <= 33 else "middle" if number <= 66 else "late"):
                raise BenchmarkError("Incorrect source age zone")
        flagship = bundle.fact("shard")
        if (flagship["source_turn_id"], flagship["expected"], flagship["question"]) != (
            "t82",
            "shard-19",
            "Which partition ended up carrying the blame?",
        ):
            raise BenchmarkError("Flagship source contract changed")
    except BenchmarkError:
        raise
    except (ContextEngineError, KeyError, TypeError, ValueError, StopIteration, OverflowError):
        raise BenchmarkError("Malformed benchmark fixture") from None


def check_leakage(bundle: Bundle) -> None:
    """V2 primary input has no evaluator fields, answer pins, question/summary leakage."""
    from ..layers.summarize import SummarySnapshot
    from .fixtures import validate_frozen_summary

    job = bundle.job("Leakage validation")
    scenario, summary = bundle.get("scenario"), bundle.get("summary_fixture")
    values = tuple(value for fact in bundle.facts for value in aliases(fact))
    if scenario["pins"] or bundle.get("protocol")["primary_pins"] != "empty":
        raise BenchmarkError("Primary corpus must have no answer pins")
    for content in [scenario["system"], *(fact["question"] for fact in bundle.facts)]:
        if present(content, values):
            raise BenchmarkError("Answer leakage in system or probe question")
    snapshot = SummarySnapshot.from_history(
        scope=job.arguments["pinned_facts"].scope,
        content=summary["content"],
        history=job.arguments["history"],
        policy_version=summary["policy_version"],
        created_at=job.arguments["at"],
    )
    validate_frozen_summary(snapshot, values)
