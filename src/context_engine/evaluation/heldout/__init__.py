"""Separate synthetic held-out preparation. No provider dispatch or quality claims."""

import hashlib
import json
from collections import Counter
from datetime import datetime
from importlib import resources
from pathlib import Path

from ...config import BudgetConfig
from ...errors import BenchmarkError, RequiredContextTooLarge
from ...models import KeyedPins, Message, Role, Scope, Turn, canonical_json
from ...pipeline import AssemblyOptions, assemble_context
from ...tokens import TiktokenCounter
from ..corpus import strict_json
from ..protocol import runtime_identity

FILES = ("scenarios.json", "ground_truth.json", "protocol.json")
CATEGORIES = (
    "stale",
    "contradictory",
    "paraphrase",
    "multilingual",
    "hostile_tool",
    "no_answer",
    "long_history",
    "cap_middle",
)
SPLITS = ("development", "evaluation")
VARIANTS = ("WINDOW", "CAP_RETRIEVE_WINDOW")


def _root(directory):
    return (
        Path(directory) if directory is not None else resources.files(__package__).joinpath("data")
    )


def load(directory=None):
    """Verify a fixed manifest and validate all fixture contracts; never bless drift."""
    root = _root(directory)
    try:
        manifest = strict_json(root.joinpath("manifest.json").read_text(encoding="utf-8"))
        raw = {name: root.joinpath(name).read_bytes() for name in FILES}
        hashes = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
        if manifest != {"schema_version": 1, "id": "heldout-v1", "files": hashes}:
            raise BenchmarkError("Held-out fixture freeze mismatch")
        # The existing strict parser requires an object root. Wrap the scenario
        # array while retaining its duplicate-key/non-finite-number rejection.
        values = {
            name: strict_json('{"data":' + value.decode("utf-8") + "}")["data"]
            for name, value in raw.items()
        }
        scenarios, truth, protocol = (values[name] for name in FILES)
        validate(scenarios, truth, protocol)
        return scenarios, truth, protocol, manifest
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise BenchmarkError("Invalid held-out resources") from exc


def validate(scenarios, truth, protocol):
    """Fail closed on malformed fixtures; exact identities are additionally hash bound."""
    try:
        if (
            protocol["id"] != "heldout-v1"
            or protocol["status"] != "TEST_ONLY"
            or protocol["provider_calls"] != 0
            or protocol["approval"] != "owner_pending"
            or protocol["splits"] != list(SPLITS)
            or protocol["categories"] != list(CATEGORIES)
            or protocol["budgets"] != [900, 3000]
            or protocol["variants"] != list(VARIANTS)
            or protocol["completion_reservation"] != 256
            or not isinstance(protocol["system"], str)
            or not protocol["system"].strip()
            or datetime.fromisoformat(protocol["evaluated_at"]).utcoffset() is None
        ):
            raise ValueError("protocol")
        fields = {
            "id",
            "split",
            "category",
            "question",
            "messages",
            "filler_turns",
            "middle_padding",
        }
        if len(scenarios) != 16 or len({case["id"] for case in scenarios}) != 16:
            raise ValueError("case count")
        coverage = Counter((case["split"], case["category"]) for case in scenarios)
        if coverage != Counter((split, category) for split in SPLITS for category in CATEGORIES):
            raise ValueError("split/category coverage")
        if set(truth) != {case["id"] for case in scenarios}:
            raise ValueError("truth coverage")
        for case in scenarios:
            if (
                set(case) != fields
                or not isinstance(case["question"], str)
                or not case["question"].strip()
                or len(case["question"]) > 2000
            ):
                raise ValueError("scenario fields")
            for field in ("filler_turns", "middle_padding"):
                if type(case[field]) is not int or not 0 <= case[field] <= 120:
                    raise ValueError("workload bound")
            if not isinstance(case["messages"], list) or not 1 <= len(case["messages"]) <= 8:
                raise ValueError("messages")
            for role, text in case["messages"]:
                if role not in ("user", "tool") or not isinstance(text, str) or len(text) > 2000:
                    raise ValueError("message")
            answer = truth[case["id"]]
            if (
                set(answer) != {"answer", "forbidden", "sources"}
                or not isinstance(answer["answer"], str)
                or not answer["answer"]
            ):
                raise ValueError("answer")
            for field in ("forbidden", "sources"):
                if not isinstance(answer[field], list) or any(
                    not isinstance(item, str) for item in answer[field]
                ):
                    raise ValueError("truth lists")
            available = {f"m{i}" for i in range(len(case["messages"]))}
            if not set(answer["sources"]) <= available:
                raise ValueError("truth source lineage")
            if answer["answer"] != "UNKNOWN" and not any(
                answer["answer"] in text for _, text in case["messages"]
            ):
                raise ValueError("unsupported answer")
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkError("Invalid held-out scenario, truth or protocol") from exc


def engine_inputs(case, at):
    """Allowlisted scenario-only builder: has no ground-truth parameter or resource read."""
    scope = Scope("c09-synthetic", case["id"])
    turns = []
    for index, (role, text) in enumerate(case["messages"]):
        padding = "Routine tool telemetry; no incident change. " * case["middle_padding"]
        message = Message(
            f"m{index}",
            Role(role),
            padding + text + padding,
            tool_call_id=f"call-{index}" if role == "tool" else None,
        )
        turns.append(Turn(f"t{index}", scope, (message,), timestamp=at))
    for index in range(case["filler_turns"]):
        text = (
            f"Routine observation {index}. " + "Telemetry is normal; no configuration update. " * 8
        )
        turns.append(
            Turn(f"f{index}", scope, (Message(f"fm{index}", Role.USER, text),), timestamp=at)
        )
    return tuple(turns), KeyedPins(scope), case["question"]


def prepare(directory=None, *, split="all", retention=False):
    """Pure local assembly evidence; no response recording or live mode exists."""
    if split not in ("all", *SPLITS):
        raise BenchmarkError("Unknown held-out split")
    scenarios, _truth, protocol, manifest = load(directory)
    if type(retention) is not bool:
        raise BenchmarkError("Retention selection must be boolean")
    if retention:
        from .scoring import retained, scoring_freeze

        score_freeze = scoring_freeze()
    counter = TiktokenCounter()
    at = datetime.fromisoformat(protocol["evaluated_at"])
    rows = []
    for case in scenarios:
        if split != "all" and case["split"] != split:
            continue
        history, pins, question = engine_inputs(case, at)
        for budget in protocol["budgets"]:
            for variant in protocol["variants"]:
                row = {
                    "case": case["id"],
                    "category": case["category"],
                    "split": case["split"],
                    "variant": variant,
                    "budget": budget,
                }
                try:
                    result = assemble_context(
                        history,
                        question,
                        pins,
                        BudgetConfig(input_cap=budget, completion_reservation=256),
                        system=protocol["system"],
                        at=at,
                        token_counter=counter,
                        options=AssemblyOptions(
                            cap=variant != "WINDOW",
                            retrieve=variant != "WINDOW",
                            summarize=False,
                        ),
                    )
                except RequiredContextTooLarge:
                    row.update(status="REQUIRED_NON_FIT", estimated_tokens=None)
                    if retention:
                        row["retained"] = None if case["category"] == "no_answer" else False
                else:
                    messages = result.messages
                    structure = [m["content"] for m in messages if m["role"] == "system"] == [
                        protocol["system"]
                    ] and messages[-1] == {"role": "user", "content": question}
                    if not structure or result.diagnostics.estimate.estimated_tokens > budget:
                        raise BenchmarkError("Held-out structural or estimated-budget failure")
                    row.update(
                        status="PREPARED",
                        estimated_tokens=result.diagnostics.estimate.estimated_tokens,
                        request_hash=hashlib.sha256(
                            canonical_json(result.request.to_wire()).encode()
                        ).hexdigest(),
                        selected_messages=sorted(
                            {s.message_id for b in result.blocks for s in b.sources}
                        ),
                        structure="PASS",
                    )
                    if retention:
                        row["retained"] = retained(case, _truth[case["id"]], result)
                rows.append(row)
    report = {
        "schema_version": 1,
        "protocol": protocol["id"],
        "status": "TEST_ONLY",
        "approval": "owner_pending",
        "split": split,
        "fixture_manifest": manifest,
        "runtime": runtime_identity(),
        "provider_calls": 0,
        "planned_slots": len(rows),
        "dispositions": dict(sorted(Counter(r["status"] for r in rows).items())),
        "answer_quality": "NOT_EVALUATED",
        "content_retention": "SYNTHETIC_LITERAL_CHECK" if retention else "NOT_SCORED",
        "provider_calibration": "NOT_EVALUATED",
        "provider_cost": "NOT_EVALUATED",
        "rows": rows,
    }
    if retention:
        report["scoring_freeze"] = score_freeze
    return report


def export(report, destination):
    """Exclusive synthetic report export; existing destinations are never replaced."""
    if report.get("status") != "TEST_ONLY" or report.get("provider_calls") != 0:
        raise BenchmarkError("Only offline TEST_ONLY reports are supported")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    with (destination / "README.md").open("x", encoding="utf-8") as stream:
        stream.write(
            "# C09 offline preparation\n\nTEST_ONLY; no provider calls.\n\n"
            f"Slots: {report['planned_slots']}; kind: {report.get('kind', 'preparation')}.\n\n"
            "Answer quality and provider calibration: NOT_EVALUATED.\n"
            "Synthetic literal retention and scorer checks are not model-quality evidence.\n"
        )
