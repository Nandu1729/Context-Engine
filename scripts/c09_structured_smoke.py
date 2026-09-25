"""D084: two schema-accounted smoke calls; never replacement benchmark evidence."""

import hashlib
import importlib.util
from pathlib import Path

from context_engine.answers import AnswerContract
from context_engine.config import BudgetConfig
from context_engine.models import Scope
from context_engine.providers.contracts import Completion, ModelResult, RetryConfig
from context_engine.tokens import TiktokenCounter

ROOT = Path(__file__).resolve().parents[1]
FROZEN = {
    "scripts/c09_response_diagnostic.py":
        "801c799bc7975f0f578c2266a2d61e8c75976f02d2116953ad52df843213f5bf",
    "examples/structured_answers.py":
        "796fa5dc66e78c26214793faba19bc5f3f669e892c0c2b4ca86ed21bdec4df43",
    "examples/validated_answer.py":
        "4ac5486705011594138a8175529e611ff39d1c9d1ab9a8db39d4d320f0f21670",
}


def verify():
    for filename, expected in FROZEN.items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Structured smoke dependency changed")


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


verify()
diagnostic = module("structured_diagnostic", "scripts/c09_response_diagnostic.py")
structured = module("smoke_structured", "examples/structured_answers.py")
boundary = module("smoke_boundary", "examples/validated_answer.py")
live = diagnostic.live
qualification = diagnostic.parent.qualification
live.RUN = ROOT / "output/private/c09-structured-smoke-001"
live.PROTOCOL = ROOT / "docs/C09_STRUCTURED_SMOKE_PROTOCOL.md"
live.SCOPE_VERSION = "c09-structured-smoke-001"
diagnostic.SHAPES = ROOT / "output/private/c09-structured-shapes-001"
live.GENERATION = structured.StructuredGeneration(
    model=live.MODEL, max_completion_tokens=256, contract=AnswerContract("ascii_identifier")
)
live.RETRIES = RetryConfig(max_attempts=1)


def counter():
    return TiktokenCounter(serializer=structured.StructuredSerializer(live.GENERATION))


def assembled(row):
    cases, truth, _ = qualification.load()
    case = next(c for c in cases if c["id"] == row["case"])
    result = qualification.assemble(case, row["budget"], row["variant"], counter())
    return case, truth, result


def identity():
    verify()
    value = diagnostic.identity()
    selected = []
    for row in value["preparation"]["rows"]:
        case, truth, result = assembled(row)
        selected.append({
            **row,
            "request_hash": live.fingerprint(result.request.to_wire()),
            "estimated_tokens": result.diagnostics.estimate.estimated_tokens,
            "retained": qualification.retained(case, truth[case["id"]], result),
        })
    value["preparation"] = {**value["preparation"], "rows": selected}
    value.update(
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        frozen_dependencies=FROZEN,
        approval="D084",
        counting_serializer=counter().serializer.name,
    )
    return value


def reconstruct(row):
    case, _, result = assembled(row)
    live.require(live.fingerprint(result.request.to_wire()) == row["request_hash"])
    live.require(result.diagnostics.estimate.estimated_tokens == row["estimated_tokens"])
    return result.request, BudgetConfig(input_cap=row["budget"], completion_reservation=256), Scope(
        "c09-synthetic", case["id"]
    )


def client_factory(*, retries, **kwargs):
    live.require(retries == RetryConfig(max_attempts=1))
    return structured.StructuredAnswerClient(**kwargs)


def report(manifest, rows):
    value = diagnostic.report(manifest, rows)
    _, truth, _ = qualification.load()
    outcomes = []
    for i, receipt in value["receipts"].items():
        plan = manifest["preparation"]["rows"][i]
        saved = dict(receipt["result"])
        saved.pop("content_included")
        saved["attempt_ids"] = tuple(saved["attempt_ids"])
        if saved["completion"] is not None:
            saved["completion"] = Completion.from_dict(saved["completion"])
        result = ModelResult(**saved)
        parsed = None
        try:
            parsed = boundary.validate_answer(result, live.GENERATION.contract)
        except boundary.UnusableAnswer:
            pass
        usage = result.completion.usage if result.completion else None
        outcomes.append({
            "case": plan["case"], "variant": plan["variant"], "budget": plan["budget"],
            "conforming": parsed is not None,
            "correct": parsed == truth[plan["case"]]["answer"],
            "provider_input_overrun": usage is not None and usage.input_tokens > plan["budget"],
            "input_ratio": usage.input_tokens / plan["estimated_tokens"] if usage else None,
        })
    value.update(answer_quality="SMOKE_ONLY", outcomes=outcomes)
    value["caveat"] = (
        "Two schema-accounted synthetic smoke calls, not qualification or replacement answers. "
        "Schema overhead may change context selection; original benchmark remains unchanged."
    )
    return value


live.identity, live.reconstruct, live.report = identity, reconstruct, report
live.TiktokenCounter, live.ProviderClient = counter, client_factory

if __name__ == "__main__":
    import sys

    if "run" in sys.argv:
        diagnostic.SHAPES.mkdir(mode=0o700, parents=True, exist_ok=True)
        diagnostic.transport_module.parse_completion = diagnostic.observed_parse
    raise SystemExit(live.main())
