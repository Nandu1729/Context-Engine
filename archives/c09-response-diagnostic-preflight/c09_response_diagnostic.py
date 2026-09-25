"""D082: two separately accounted response-shape diagnostics, never benchmark retries."""

import hashlib
import importlib.util
import json
from pathlib import Path

from context_engine.providers import transport as transport_module

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "scripts/c09_qualification_live.py"
PARENT_HASH = "6b1d8df257d8cac21adb758018c5e958821d2d216e119e2023cd1781c48b0a9f"
if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_HASH:
    raise ValueError("Diagnostic parent changed")
spec = importlib.util.spec_from_file_location("diagnostic_parent", PARENT)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
live = parent.live
live.RUN = ROOT / "output/private/c09-response-diagnostic-001"
live.PROTOCOL = ROOT / "docs/C09_RESPONSE_DIAGNOSTIC_PROTOCOL.md"
live.SCOPE_VERSION = "c09-response-diagnostic-001"
SHAPES = ROOT / "output/private/c09-response-shapes-001"
base_identity, base_report, base_emit = live.identity, live.report, live.emit
native_parse = transport_module.parse_completion


def identity():
    live.require(hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_HASH)
    value = base_identity()
    rows = value["preparation"]["rows"]
    selected = [
        next(
            r for r in rows if r["case"] == case and r["variant"] == variant and r["budget"] == 900
        )
        for case, variant in (("q2-long", "PRIMARY"), ("q2-conflict", "CONTROL"))
    ]
    value["preparation"] = {**value["preparation"], "rows": selected, "planned_slots": 2}
    value.update(
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualification_runner_sha256=PARENT_HASH,
        max_calls=2,
        approval="D082",
    )
    return value


def field_shape(message, name):
    value = message.get(name)
    return {
        "present": name in message,
        "type": "string" if isinstance(value, str) else "null" if value is None else "other",
        "characters": len(value) if isinstance(value, str) else None,
        "blank": not value.strip() if isinstance(value, str) else None,
    }


def response_shape(raw):
    """Strict allowlist; no text, headers, arbitrary keys, credentials or reasoning."""
    shape = {"body_sha256": hashlib.sha256(raw).hexdigest(), "body_bytes": len(raw)}
    try:
        data = json.loads(raw)
        choice = data["choices"][0]
        message = choice["message"]
        if not isinstance(message, dict):
            raise ValueError
        shape.update(
            content=field_shape(message, "content"),
            reasoning=field_shape(message, "reasoning"),
            refusal=field_shape(message, "refusal"),
            tool_calls_present=bool(message.get("tool_calls")),
            finish_reason=choice["finish_reason"]
            if choice["finish_reason"] in ("stop", "length", "content_filter", "tool_calls")
            else "other",
        )
    except (ValueError, TypeError, KeyError, IndexError):
        shape["unrecognized_shape"] = True
    return shape


def observed_parse(raw, model):
    claims = sorted(live.RUN.glob("claim-*.json"))
    live.require(1 <= len(claims) <= 2)
    slot = len(claims) - 1
    shape = response_shape(raw)
    shape["claim_hash"] = live.fingerprint(live.read(claims[-1]))
    try:
        completion = native_parse(raw, model)
    except Exception:
        shape["parse_status"] = "rejected"
        live.save(SHAPES / f"shape-{slot:02d}.json", shape)
        raise
    shape.update(parse_status="accepted", completion_hash=live.fingerprint(completion.to_dict()))
    live.save(SHAPES / f"shape-{slot:02d}.json", shape)
    return completion


def report(manifest, rows):
    value = base_report(manifest, rows)
    value.update(answer_quality="DIAGNOSTIC_ONLY", quality_target="NOT_EVALUATED")
    shapes = {}
    for i, receipt in value["receipts"].items():
        path = SHAPES / f"shape-{i:02d}.json"
        if not path.exists():
            live.require(receipt["result"]["completion"] is None)
            continue
        shape = live.read(path)
        live.require(shape["claim_hash"] == receipt["claim_hash"])
        completion = receipt["result"]["completion"]
        if completion is not None:
            live.require(shape["completion_hash"] == live.fingerprint(completion))
            live.require(shape["content"]["characters"] == len(completion["content"]))
        shapes[i] = shape
    value["response_shapes"] = shapes
    value["caveat"] = "Two authorized diagnostic reissues, never replacement benchmark evidence."
    return value


def emit(value):
    if "planned" in value:
        value = {**value, "planned": 2}
    base_emit(value)


live.identity, live.report, live.emit = identity, report, emit

if __name__ == "__main__":
    import sys

    if "run" in sys.argv:
        SHAPES.mkdir(mode=0o700, parents=True, exist_ok=True)
        transport_module.parse_completion = observed_parse
    raise SystemExit(live.main())
