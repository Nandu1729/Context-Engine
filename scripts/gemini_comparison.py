#!/usr/bin/env python3
"""One fixed, synthetic A1/A5 diagnostic; not the Groq C06 qualification runner.

Offline prepare is the default. At most two countTokens and two generateContent
attempts over this experiment's entire lifetime, including across restarts/days.
No retries, reset, alternate run directory or model-switch CLI exists.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gemini_preflight import PreflightError, load_key

from context_engine.evaluation.corpus import (
    aliases,
    check_fixture,
    check_leakage,
    digest,
    load_bundle,
    strict_json,
)
from context_engine.evaluation.grading import answer_correct
from context_engine.evaluation.harness import _prepare_validated
from context_engine.evaluation.protocol import code_hash, load_freeze
from context_engine.providers.credentials import private_bytes

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output/private/gemini-comparison-001"
MODEL = "gemini-3.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
GENERATION = {
    "temperature": 0,
    "candidateCount": 1,
    "maxOutputTokens": 512,
    "thinkingConfig": {"thinkingLevel": "MINIMAL", "includeThoughts": False},
}
INPUT_LIMIT = 900
MAX_BODY = 16_000
MAX_RESPONSE = 64_000


class ComparisonError(Exception):
    """Fixed error codes only; provider bodies/exception messages never escape."""


def native_request(wire: dict) -> dict:
    """Narrow text-only mapping; reject unsupported tools/roles, never flatten them.

    This fixture's assembled history is already explicitly labelled user DATA.
    Preserve every message's order/content in separate native text parts.
    """
    if set(wire) != {"messages"} or not isinstance(wire["messages"], list):
        raise ComparisonError("unsupported_request")
    messages = wire["messages"]
    if len(messages) < 2:
        raise ComparisonError("unsupported_request")
    for i, message in enumerate(messages):
        if (
            set(message) != {"role", "content"}
            or message["role"] != ("system" if i == 0 else "user")
            or not isinstance(message["content"], str)
            or not message["content"]
        ):
            raise ComparisonError("unsupported_request")
    result = {
        "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
        "contents": [
            {"role": "user", "parts": [{"text": message["content"]} for message in messages[1:]]}
        ],
        "generationConfig": json.loads(json.dumps(GENERATION)),
    }
    if len(json.dumps(result).encode()) > MAX_BODY:
        raise ComparisonError("request_too_large")
    return result


def build_plan() -> dict:
    if code_hash() != load_freeze()["runtime"]["code_hash"]:
        raise ComparisonError("core_freeze_changed")
    bundle = load_bundle()
    check_fixture(bundle)
    check_leakage(bundle)
    probes = []
    for variant in ("A1", "A5"):
        # Reuse preparation only; do NOT create/validate a Groq manifest or receipt.
        prepared = _prepare_validated(
            bundle,
            {
                "fact_id": "shard",
                "variant": variant,
                "budget": INPUT_LIMIT,
                "model": MODEL,
            },
        )
        if prepared["state"] != "prepared":
            raise ComparisonError("engine_non_fit")
        request = native_request(prepared["request"])
        probes.append(
            {
                "variant": variant,
                "fact_id": "shard",
                "request": request,
                "request_hash": digest(request),
                "engine_estimated_input": prepared["estimate"]["estimated_tokens"],
                "retained_evidence": prepared["retained_evidence"],
            }
        )
    return {
        "experiment": "gemini-comparison-001",
        "schema_version": 1,
        "scope": "Two diagnostic answers to the known synthetic flagship; not held-out quality",
        "model": MODEL,
        "core_hash": code_hash(),
        "fixture_hashes": bundle.hashes,
        "script_hashes": {
            name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
            for name in ("gemini_comparison.py", "gemini_preflight.py")
        },
        "account_alias": "gemini-default-project-context-engine-v1",
        "observed_limits": {
            "rpm": 15,
            "tpm": 250_000,
            "rpd": 500,
            "daily_reset_zone": "America/Los_Angeles",
        },
        "lifetime_caps": {
            "http_attempts": 4,
            "generation_attempts": 2,
            "native_input_per_generation": INPUT_LIMIT,
            "output_per_generation": GENERATION["maxOutputTokens"],
        },
        "billing": "owner-confirmed Free Tier; no paid billing authorized or enabled by this tool",
        "grading": "existing exact-alias-or-json-answer; score only STOP with valid usage",
        "probes": probes,
    }


def write_once(path: Path, value: dict) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_record(path: Path) -> dict:
    try:
        return strict_json(private_bytes(path, 200_000).decode())
    except Exception:
        raise ComparisonError("invalid_private_record") from None


def check_directory(path: Path, *, private: bool = True) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ComparisonError("unsafe_run_directory")
    stat = path.stat()
    # A public-readable parent is fine: this run directory itself is always 0700.
    if stat.st_uid != os.getuid() or stat.st_mode & (0o077 if private else 0o022):
        raise ComparisonError("unsafe_run_directory")


def prepare(plan: dict, run: Path) -> None:
    # Caller validates the private parent. A damaged/partial plan fails closed.
    if not os.path.lexists(run):
        run.mkdir(mode=0o700)
        write_once(run / "plan.json", plan)
    check_directory(run)
    if read_record(run / "plan.json") != plan:
        raise ComparisonError("immutable_plan_changed")


def integer(value, *, positive=False) -> int:
    if type(value) is not int or not int(positive) <= value <= 1_000_000:
        raise ComparisonError("invalid_usage")
    return value


def generation_receipt(data: dict) -> dict:
    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        raise ComparisonError("missing_usage")
    normalized = {
        "input": integer(usage.get("promptTokenCount"), positive=True),
        "output": integer(usage.get("candidatesTokenCount")),
        "thoughts": integer(usage.get("thoughtsTokenCount", 0)),
        "total": integer(usage.get("totalTokenCount"), positive=True),
    }
    if normalized["total"] != sum(normalized[k] for k in ("input", "output", "thoughts")):
        raise ComparisonError("inconsistent_usage")
    if usage.get("toolUsePromptTokenCount", 0) != 0:
        raise ComparisonError("unexpected_tool_usage")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ComparisonError("invalid_candidate")
    candidate = candidates[0]
    if not isinstance(candidate, dict) or candidate.get("finishReason") not in (
        "STOP",
        "MAX_TOKENS",
        "SAFETY",
        "RECITATION",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "OTHER",
    ):
        raise ComparisonError("unknown_finish_reason")
    parts = candidate.get("content", {}).get("parts", [])
    if not isinstance(parts, list):
        raise ComparisonError("invalid_candidate")
    texts = []
    for part in parts:
        if (
            not isinstance(part, dict)
            or set(part) - {"text", "thought", "thoughtSignature"}
            or not isinstance(part.get("text"), str)
            or type(part.get("thought", False)) is not bool
        ):
            raise ComparisonError("invalid_candidate")
        if not part.get("thought", False):
            texts.append(part["text"])
    answer = "".join(texts)
    version = data.get("modelVersion")
    if (
        not isinstance(version, str)
        or not 1 <= len(version) <= 160
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for c in version
        )
    ):
        raise ComparisonError("invalid_model_version")
    valid = (
        candidate["finishReason"] == "STOP"
        and bool(answer.strip())
        and normalized["input"] <= INPUT_LIMIT
        and normalized["output"] + normalized["thoughts"] <= GENERATION["maxOutputTokens"]
    )
    return {
        "usage": normalized,
        "answer": answer,
        "model_version": version,
        "finish_reason": candidate["finishReason"],
        "valid": valid,
    }


async def post(key: str, method: str, payload: dict, *, transport=None) -> dict:
    import httpx

    if method not in ("countTokens", "generateContent"):
        raise ComparisonError("unsupported_method")
    try:
        async with asyncio.timeout(45):
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=False, trust_env=False, transport=transport
            ) as client:
                async with client.stream(
                    "POST", f"{ENDPOINT}:{method}", headers={"x-goog-api-key": key}, json=payload
                ) as response:
                    if response.status_code != 200:
                        # The terminal intent remains: no retry of even a rejected attempt.
                        raise ComparisonError(f"http_{response.status_code}")
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > MAX_RESPONSE:
                            raise ComparisonError("response_too_large")
                        raw.extend(chunk)
                    data = strict_json(raw.decode(), maximum=MAX_RESPONSE)

                    def reflects(value):
                        if isinstance(value, str):
                            return key in value
                        if isinstance(value, dict):
                            return any(reflects(k) or reflects(v) for k, v in value.items())
                        if isinstance(value, list):
                            return any(reflects(v) for v in value)
                        return False

                    if reflects(data):
                        raise ComparisonError("credential_reflection")
                    return data
    except ComparisonError:
        raise
    except Exception:
        raise ComparisonError("uncertain_transport_or_response") from None


async def run_comparison(plan: dict, run: Path, key: str, *, transport=None) -> dict:
    """Caller holds the exclusive directory lock throughout all network operations.

    Lifetime caps are stricter than supplied minute/day limits, so no reset, sleep,
    dynamic quota multiplication, or dependence on the screenshot's zero usage.
    Provider 429/external usage still stops this experiment; this is not a global
    account quota service. Any unfinished intent blocks ALL remaining requests.
    """
    plan_hash = digest(plan)
    for probe in plan["probes"]:
        variant = probe["variant"]
        for method in ("countTokens", "generateContent"):
            stem = f"{variant}-{method}"
            intent_path, receipt_path = run / f"{stem}.intent.json", run / f"{stem}.receipt.json"
            binding = {
                "plan_hash": plan_hash,
                "request_hash": probe["request_hash"],
                "variant": variant,
                "method": method,
            }
            if os.path.lexists(receipt_path):
                receipt = read_record(receipt_path)
                intent = read_record(intent_path)
                if any(intent.get(k) != v or receipt.get(k) != v for k, v in binding.items()):
                    raise ComparisonError("receipt_binding_mismatch")
                if receipt.get("state") != "completed":
                    return summary(plan, run)
                if method == "generateContent" and not receipt.get("valid"):
                    return summary(plan, run)
                continue
            if os.path.lexists(intent_path):
                raise ComparisonError("unfinished_intent_no_resend")
            if method == "generateContent":
                count = read_record(run / f"{variant}-countTokens.receipt.json")["tokens"]
                if count > INPUT_LIMIT:
                    return summary(plan, run)
                payload = probe["request"]
            else:
                payload = {
                    "generateContentRequest": {"model": f"models/{MODEL}", **probe["request"]}
                }
            now = datetime.now(UTC)
            write_once(
                intent_path,
                {
                    **binding,
                    "state": "dispatch_intent",
                    "at": now.isoformat(),
                    "pacific_day": now.astimezone(ZoneInfo("America/Los_Angeles"))
                    .date()
                    .isoformat(),
                },
            )
            try:
                data = await post(key, method, payload, transport=transport)
                if method == "countTokens":
                    result = {"tokens": integer(data.get("totalTokens"), positive=True)}
                else:
                    result = generation_receipt(data)
                    result["answer_correct"] = (
                        answer_correct(
                            result["answer"], aliases(load_bundle().fact(probe["fact_id"]))
                        )
                        if result["valid"]
                        else None
                    )
                write_once(receipt_path, {**binding, "state": "completed", **result})
                if method == "generateContent" and not result["valid"]:
                    return summary(plan, run)
            except ComparisonError as error:
                write_once(receipt_path, {**binding, "state": "stopped", "error": error.args[0]})
                return summary(plan, run)
    return summary(plan, run)


def summary(plan: dict, run: Path) -> dict:
    rows = []
    attempts = 0
    for probe in plan["probes"]:
        row = {
            k: probe[k]
            for k in ("variant", "fact_id", "retained_evidence", "engine_estimated_input")
        }
        for method in ("countTokens", "generateContent"):
            attempts += int(os.path.lexists(run / f"{probe['variant']}-{method}.intent.json"))
            path = run / f"{probe['variant']}-{method}.receipt.json"
            if os.path.lexists(path):
                row[method] = read_record(path)
        rows.append(row)
    completed = sum(r.get("generateContent", {}).get("state") == "completed" for r in rows)
    return {
        "experiment": plan["experiment"],
        "model": MODEL,
        "plan_hash": digest(plan),
        "http_attempts": attempts,
        "completed_generation_calls": completed,
        "status": "complete" if completed == 2 else "incomplete",
        "qualification": "diagnostic only; Groq C06 unchanged",
        "probes": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.allow_live and args.env_file is None:
            raise ComparisonError("explicit_credential_file_required")
        check_directory(RUN.parent, private=False)
        plan = build_plan()
        prepare(plan, RUN)
        lock_path = RUN / "lock"
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = (
                asyncio.run(run_comparison(plan, RUN, load_key(args.env_file)))
                if args.allow_live
                else summary(plan, RUN)
            )
        print(json.dumps(result, indent=2))
        return int(args.allow_live and result["status"] != "complete")
    except (ComparisonError, PreflightError) as error:
        print(json.dumps({"status": "stopped", "error": error.args[0]}))
        return 1
    except Exception:
        print('{"status":"stopped","error":"comparison_failed_no_automatic_retry"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
