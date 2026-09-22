"""Request/result validity, explicit denominators and immutable resume snapshots."""

import json
from dataclasses import asdict
from pathlib import Path
from statistics import median

from ..errors import BenchmarkError, ContextEngineError
from ..inspection import save_inspection
from ..models import canonical_json
from .corpus import Bundle, aliases, strict_json
from .grading import answer_correct, normalize, proportion
from .harness import _prepare_validated
from .protocol import Gate, Manifest, check_manifest, preflight

RESPONSE_FIELDS = {
    "answer",
    "answer_correct",
    "finish_reason",
    "error_code",
    "response_origin",
    "provider_request_id",
    "replay_of",
    "provider_usage",
}
TERMINAL = {"success", "error", "truncated", "non_fit"}
MAX_RUN_BYTES = 32_000_000


def record_response(
    bundle: Bundle,
    prepared: dict,
    *,
    answer: str | None,
    finish_reason: str,
    origin: str,
    error_code: str | None = None,
    provider_request_id: str | None = None,
    replay_of: str | None = None,
    provider_usage: dict | None = None,
) -> dict:
    """Record supplied evidence of a response; this function never performs inference."""
    if prepared["state"] != "prepared":
        raise BenchmarkError("Only an admitted, unanswered probe can receive a response")
    result = strict_json(canonical_json(prepared))
    if finish_reason not in ("stop", "length", "error") or origin not in ("test", "live", "replay"):
        raise BenchmarkError("Unsupported response disposition")
    if finish_reason != "error" and not isinstance(answer, str):
        raise BenchmarkError("Completed response requires answer text")
    result.update(
        state={"stop": "success", "length": "truncated", "error": "error"}[finish_reason],
        answer=answer,
        finish_reason=finish_reason,
        response_origin=origin,
        error_code=error_code,
        provider_request_id=provider_request_id,
        replay_of=replay_of,
        provider_usage=provider_usage,
        answer_correct=answer_correct(answer, aliases(bundle.fact(result["fact_id"])))
        if finish_reason == "stop"
        else None,
    )
    _check_response(bundle, result)
    return result


def _check_response(bundle: Bundle, row: dict) -> None:
    state = row["state"]
    if state in ("prepared", "non_fit"):
        if any(row[key] is not None for key in RESPONSE_FIELDS):
            raise BenchmarkError("Unsent probe contains fabricated generation metadata")
        return
    expected_finish = {"success": "stop", "truncated": "length", "error": "error"}
    if state not in expected_finish or row["finish_reason"] != expected_finish[state]:
        raise BenchmarkError("Inconsistent generation disposition")
    if row["response_origin"] not in ("test", "live", "replay"):
        raise BenchmarkError("Missing response provenance")
    if (
        row["response_origin"] in ("live", "replay")
        and (
            not isinstance(row["provider_request_id"], str)
            or not row["provider_request_id"].strip()
        )
        and state != "error"
    ):
        raise BenchmarkError("Completed provider response lacks a request identifier")
    if row["response_origin"] == "replay":
        if not isinstance(row["replay_of"], str) or not row["replay_of"].strip():
            raise BenchmarkError("Replay lacks an original response reference")
    elif row["replay_of"] is not None:
        raise BenchmarkError("Non-replay response claims replay ancestry")
    if state == "error":
        if (
            not isinstance(row["error_code"], str)
            or row["error_code"]
            not in (
                "timeout",
                "quota",
                "transport",
                "rate_limit",
                "provider_error",
                "invalid_response",
            )
            or row["answer"] is not None
            or row["answer_correct"] is not None
        ):
            raise BenchmarkError("Invalid structured provider error")
    else:
        if row["error_code"] is not None or not isinstance(row["answer"], str):
            raise BenchmarkError("Inconsistent completed response")
        expected = (
            answer_correct(row["answer"], aliases(bundle.fact(row["fact_id"])))
            if state == "success"
            else None
        )
        if type(row["answer_correct"]) is not type(expected) or row["answer_correct"] != expected:
            raise BenchmarkError("Stored answer grade does not match response")
    usage = row["provider_usage"]
    if usage is not None:
        if not isinstance(usage, dict) or set(usage) != {
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
        }:
            raise BenchmarkError("Malformed provider usage")
        if (
            any(type(n) is not int or n < 0 for n in usage.values())
            or usage["cached_input_tokens"] > usage["input_tokens"]
        ):
            raise BenchmarkError("Inconsistent provider token usage")


def validate_run(
    bundle: Bundle, frozen: dict, manifest: Manifest, records: list[dict] | tuple[dict, ...]
) -> dict:
    gates = list(preflight(bundle, frozen))
    try:
        check_manifest(bundle, frozen, manifest)
    except ContextEngineError:
        gates = [g for g in gates if g.gate != "V5"] + [Gate("V5", "FAIL", "manifest_drift")]
    if any(g.status == "FAIL" for g in gates):
        gates += [
            Gate("V3", "NOT_RUN", "preflight_failed"),
            Gate("V4", "NOT_RUN", "preflight_failed"),
        ]
        return _validation_result("INVALID", gates, [])
    slots = {slot["probe_id"]: slot for slot in manifest.slots}
    seen = set()
    prepared_cache = {}
    try:
        if not isinstance(records, (list, tuple)):
            raise BenchmarkError("Records must be an array")
        for row in records:
            if not isinstance(row, dict) or row["probe_id"] in seen or row["probe_id"] not in slots:
                raise BenchmarkError("Duplicate or unknown probe disposition")
            seen.add(row["probe_id"])
            slot = slots[row["probe_id"]]
            key = (slot["budget"], slot["variant"], slot["fact_id"])
            if key not in prepared_cache:
                prepared_cache[key] = _prepare_validated(bundle, slot)
            prepared = {**prepared_cache[key], **slot}
            if set(row) != set(prepared):
                raise BenchmarkError("Malformed result fields")
            unchanged = set(prepared) - RESPONSE_FIELDS - {"state"}
            if canonical_json({k: row[k] for k in unchanged}) != canonical_json(
                {k: prepared[k] for k in unchanged}
            ):
                raise BenchmarkError(
                    "Saved request, accounting or evidence differs from measured assembly"
                )
            if prepared["state"] == "non_fit" and row["state"] != "non_fit":
                raise BenchmarkError("Oversized request was admitted")
            if prepared["state"] != "non_fit" and row["state"] == "non_fit":
                raise BenchmarkError("Fitting request mislabeled as oversized")
            _check_response(bundle, row)
        gates.append(Gate("V3", "PASS", "requests_reassembled_and_recounted"))
    except (ContextEngineError, KeyError, TypeError, ValueError, IndexError):
        gates += [
            Gate("V3", "FAIL", "request_or_result_integrity"),
            Gate("V4", "NOT_RUN", "request_check_failed"),
        ]
        return _validation_result("INVALID", gates, [])
    terminal = {row["probe_id"] for row in records if row["state"] in TERMINAL}
    pending = [identifier for identifier in slots if identifier not in terminal]
    if any(row["state"] == "truncated" for row in records):
        gates.append(Gate("V4", "FAIL", "generation_truncated"))
        status = "INVALID"
    elif pending:
        any_response = any(row["state"] in ("success", "error") for row in records)
        status = "INTERRUPTED" if any_response or len(seen) < len(slots) else "PREPARED"
        gates.append(Gate("V4", "NOT_RUN", "pending_probe_dispositions"))
    else:
        gates.append(Gate("V4", "PASS", "all_probes_have_terminal_dispositions"))
        status = (
            "TEST_ONLY" if any(row["response_origin"] == "test" for row in records) else "VALID"
        )
    return _validation_result(status, gates, pending)


def _validation_result(status, gates, pending):
    return {
        "status": status,
        "gates": [asdict(g) for g in sorted(gates, key=lambda g: g.gate)],
        "pending_probe_ids": pending,
    }


def statistics(manifest: Manifest, records) -> list[dict]:
    """After integrity validation, report separate model/budget/variant groups."""
    rows = {r["probe_id"]: r for r in records}
    result = []
    for model in manifest.data["models"]:
        for budget in manifest.data["budgets"]:
            for variant in manifest.data["variants"]:
                planned = [
                    s
                    for s in manifest.slots
                    if (s["model"], s["budget"], s["variant"]) == (model, budget, variant)
                ]
                measured = [rows[s["probe_id"]] for s in planned if s["probe_id"] in rows]
                fitting = [r for r in measured if r["state"] != "non_fit"]
                completed = [r for r in measured if r["state"] == "success"]
                correct = sum(r["answer_correct"] for r in completed)
                attempted = [r for r in measured if r["state"] in ("success", "error", "truncated")]
                result.append(
                    {
                        "model": model,
                        "budget": budget,
                        "variant": variant,
                        "planned": len(planned),
                        "measured": len(measured),
                        "fit_all_planned": proportion(len(fitting), len(planned)),
                        "literal_fact_present_measured": proportion(
                            sum(r["fact_present"] for r in measured), len(measured)
                        ),
                        "retained_fitting_all_planned": proportion(
                            sum(r["retained_evidence"] for r in fitting), len(planned)
                        ),
                        "answer_correct_all_planned": proportion(correct, len(planned))
                        if attempted
                        else {
                            "count": None,
                            "denominator": len(planned),
                            "rate": None,
                            "wilson95": None,
                        },
                        "answer_correct_completed": proportion(correct, len(completed)),
                        "errors": sum(r["state"] == "error" for r in measured),
                        "truncated": sum(r["state"] == "truncated" for r in measured),
                        "non_fit": len(measured) - len(fitting),
                        "pending": len(planned) - sum(r["state"] in TERMINAL for r in measured),
                        "abstentions": sum(normalize(r["answer"]) == "unknown" for r in completed),
                        "provider_usage_unknown": sum(
                            r["provider_usage"] is None for r in attempted
                        ),
                        "test_responses": sum(r["response_origin"] == "test" for r in measured),
                        "cost": None,
                    }
                )
    return result


def assess_targets(manifest: Manifest, records, validation: dict) -> dict:
    """Quality cannot pass on a partial run, mock responses or unapproved registration."""
    p = manifest.data["protocol"]
    if validation["status"] != "VALID" or p["approval"] != "owner_approved":
        return {
            "status": "NOT_EVALUATED",
            "reason": "requires_valid_real_run_and_owner_registration",
        }
    primary = [
        r
        for r in records
        if r["variant"] == "A5" and r["budget"] == 900 and r["model"] == p["models"][0]
    ]
    if len(primary) != 31 or len({r["fact_id"] for r in primary}) != 31:
        return {"status": "NOT_EVALUATED", "reason": "requires_all_primary_probes"}
    observed = {
        "fit": sum(r["state"] != "non_fit" for r in primary),
        "retained": sum(r["state"] != "non_fit" and r["retained_evidence"] for r in primary),
        "correct": sum(r["answer_correct"] is True for r in primary),
        "median_input_reduction": median(
            1 - r["estimate"]["estimated_tokens"] / r["raw_estimated_tokens"] for r in primary
        ),
    }
    passed = all(observed[key] >= p["targets"][key] for key in observed)
    return {"status": "PASS" if passed else "FAIL", "observed": observed}


def save_run(path: Path, bundle: Bundle, frozen: dict, manifest: Manifest, records) -> None:
    validation = validate_run(bundle, frozen, manifest, records)
    if validation["status"] == "INVALID":
        raise BenchmarkError("Cannot export an invalid resume snapshot")
    payload = {
        "schema_version": 1,
        "run_id": manifest.run_id,
        "manifest": manifest.data,
        "records": records,
    }
    if (
        len((json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())
        > MAX_RUN_BYTES
    ):
        raise BenchmarkError("Run snapshot exceeds byte limit")
    save_inspection(path, payload)


def load_run(path: Path, bundle: Bundle, frozen: dict):
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_RUN_BYTES + 1)
        if len(raw) > MAX_RUN_BYTES:
            raise BenchmarkError("Run snapshot exceeds byte limit")
        payload = strict_json(raw.decode("utf-8"), maximum=MAX_RUN_BYTES)
        if (
            set(payload) != {"schema_version", "run_id", "manifest", "records"}
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1
        ):
            raise BenchmarkError("Unsupported run snapshot schema")
        manifest = Manifest(canonical_json(payload["manifest"]))
        if payload["run_id"] != manifest.run_id:
            raise BenchmarkError("Run identity mismatch")
        validation = validate_run(bundle, frozen, manifest, payload["records"])
        if validation["status"] == "INVALID":
            raise BenchmarkError("Resume snapshot failed validity gates")
        return manifest, payload["records"], validation
    except BenchmarkError:
        raise
    except (OSError, UnicodeError, KeyError, TypeError, ValueError):
        raise BenchmarkError("Cannot read a valid resume snapshot") from None
