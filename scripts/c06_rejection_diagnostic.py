#!/usr/bin/env python3
"""One separately metered reproduction of batch144's HTTP400; never repairs C06."""

import argparse
import asyncio
import fcntl
import json
import os
import sys
from unittest.mock import patch

import c06_recovery as recovery


def classify(raw):
    """Return fixed categories only, never provider messages or generated content."""
    try:
        error = json.loads(raw)["error"]
        code = error.get("code")
        allowed = {
            "tool_use_failed",
            "json_validate_failed",
            "context_length_exceeded",
            "invalid_api_key",
            "rate_limit_exceeded",
            "model_decommissioned",
        }
        message = error.get("message", "")
        return {
            "code": code if isinstance(code, str) and code in allowed else "unclassified",
            "tool_generation_reported": isinstance(message, str)
            and any(
                phrase in message.lower()
                for phrase in ("tool choice", "tool call", "call a function")
            ),
        }
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"code": "unclassified", "tool_generation_reported": False}


async def run(snapshot, row, observation):
    import httpx

    from context_engine.config import BudgetConfig, TokenizerConfig
    from context_engine.evaluation.corpus import load_bundle
    from context_engine.evaluation.execution import request_from_wire
    from context_engine.providers.client import ProviderClient
    from context_engine.providers.contracts import (
        GenerationConfig,
        PriceCard,
        QuotaPolicy,
        RetryConfig,
    )
    from context_engine.providers.credentials import load_api_key
    from context_engine.tokens import TiktokenCounter

    config = snapshot["profile"]["clients"][row["model"]]
    protocol = snapshot["manifest"]["protocol"]
    original = httpx.AsyncClient

    async def observe(response):
        observation["http_status"] = int(response.status_code)
        if response.status_code == 400:
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                if len(raw) + len(chunk) > 16384:
                    observation["error_classification"] = "body_over_limit"
                    return
                raw.extend(chunk)
            observation["error_classification"] = classify(raw)

    class ObservedClient(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, event_hooks={"response": [observe]})

    os.environ.pop("GROQ_API_KEY", None)
    client = ProviderClient(
        store=recovery.cache.CachedQuotaStore(recovery.base.LEDGER),
        quota=QuotaPolicy(**config["quota"]),
        prices=PriceCard(**config["prices"]),
        generation=GenerationConfig(**config["generation"]),
        retries=RetryConfig(max_attempts=1),
        counter=TiktokenCounter(TokenizerConfig(**protocol["tokenizer"])),
        api_key=load_api_key(recovery.base.ROOT / ".env"),
    )
    bundle = load_bundle()
    scope = bundle.job(bundle.fact(row["fact_id"])["question"]).arguments["pinned_facts"].scope
    with patch.object(httpx, "AsyncClient", ObservedClient):
        result = await client.complete(
            request_from_wire(row["request"]),
            BudgetConfig(input_cap=row["budget"], completion_reservation=256, **protocol["budget"]),
            scope=scope,
            security_scope="c06-rejection-diagnostic-001",
            snapshot_revision="diagnostic-001",
            policy_version="separate-not-benchmark",
        )
    # Do not publish even successful diagnostic content as benchmark evidence.
    return {
        "status": result.status,
        "attempt_ids": list(result.attempt_ids),
        "error_code": result.error_code,
        "configured_cost_microusd": result.new_cost_microusd,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_live:
        print('{"status":"requires_explicit_live_optin","max_attempts":1}')
        return 0
    try:
        recovery.verify()
        root = recovery.base.ROOT
        path = root / "output/c06-live-batch-144.json"
        snapshot = json.loads(path.read_text())
        row = next(
            e["record"]
            for e in snapshot["entries"]
            if e["record"]["fact_id"] == "region_backup"
            and e["record"]["model"] == "openai/gpt-oss-20b"
            and e["record"]["budget"] == 3000
            and e["record"]["variant"] == "A2"
        )
        if row["state"] != "error":
            raise ValueError("Expected confirmed error")
        fd = os.open(root / "output/private/c06-completion.lock", os.O_RDWR | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observation = {
                "source_sha256": recovery.digest(__file__),
                "snapshot_sha256": recovery.digest(path),
                "diagnostic": "c06-rejection-001",
                "max_attempts": 1,
                "benchmark_substitution": False,
            }
            intent = root / "output/c06-rejection-diagnostic-001.intent.json"
            result_path = root / "output/c06-rejection-diagnostic-001.json"
            if result_path.exists():
                raise ValueError("Diagnostic already complete")
            recovery.exclusive_json(intent, observation)
            result = asyncio.run(run(snapshot, row, observation))
            recovery.exclusive_json(result_path, {**observation, **result})
            print(json.dumps({**observation, **result}, sort_keys=True))
        return 0
    except Exception:
        print('{"status":"diagnostic_stopped_preserve_intent_and_ledger"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
