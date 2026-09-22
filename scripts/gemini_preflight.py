#!/usr/bin/env python3
"""Explicit Gemini credential/model discovery only; no generation or billing operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from context_engine.providers.credentials import private_bytes

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_RESPONSE_BYTES = 1_000_000
MODEL_NAME = re.compile(r"models/[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}\Z")
METHODS = {"generateContent", "countTokens", "createCachedContent", "batchGenerateContent"}


class PreflightError(Exception):
    """Only fixed, content-free error codes cross the CLI boundary."""


def load_key(path: Path) -> str:
    try:
        text = private_bytes(path, 8192).decode("ascii")
        rows = [line.strip() for line in text.splitlines() if line.strip()]
        rows = [line for line in rows if not line.startswith("#")]
        if len(rows) != 1:
            raise ValueError
        name, separator, key = rows[0].partition("=")
        key = key.strip()
        if len(key) >= 2 and key[0] in "\"'" and key[-1] == key[0]:
            key = key[1:-1]
        if name.strip() != "GEMINI_API_KEY" or not separator:
            raise ValueError
        # Keys are opaque HTTP header values, not Groq identifiers or shell programs.
        # In particular, current authorization keys can contain a period.
        if not 1 <= len(key) <= 4096 or any(not 33 <= ord(c) <= 126 for c in key):
            raise ValueError
        return key
    except Exception:
        raise PreflightError("private_credential_invalid") from None


def summarize_models(data: object) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise PreflightError("invalid_model_metadata")
    if len(data["models"]) > 1000:
        raise PreflightError("invalid_model_metadata")
    models = []
    names = set()
    for row in data["models"]:
        if not isinstance(row, dict):
            raise PreflightError("invalid_model_metadata")
        methods = row.get("supportedGenerationMethods", [])
        if not isinstance(methods, list) or any(not isinstance(m, str) for m in methods):
            raise PreflightError("invalid_model_metadata")
        if "generateContent" not in methods:
            continue
        name = row.get("name")
        if not isinstance(name, str) or not MODEL_NAME.fullmatch(name) or name in names:
            raise PreflightError("invalid_model_metadata")
        names.add(name)
        limits = {}
        for field in ("inputTokenLimit", "outputTokenLimit"):
            value = row.get(field)
            if type(value) is not int or not 0 < value <= 1_000_000_000:
                raise PreflightError("invalid_model_metadata")
            limits[field] = value
        models.append({"name": name, **limits, "methods": sorted(set(methods) & METHODS)})
    return {
        "models": sorted(models, key=lambda m: m["name"]),
        "more_pages": bool(data.get("nextPageToken")),
    }


async def discover(key: str, *, transport=None) -> dict:
    # Optional dependency; local key checks never import an HTTP client or use the network.
    import httpx

    try:
        async with asyncio.timeout(30):
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False, transport=transport
            ) as client:
                async with client.stream(
                    "GET", ENDPOINT, params={"pageSize": 1000}, headers={"x-goog-api-key": key}
                ) as response:
                    if response.status_code != 200:
                        return {"status": "api_rejected", "http_status": response.status_code}
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise PreflightError("model_response_too_large")
                        raw.extend(chunk)
                    result = summarize_models(json.loads(raw))
                    # Do not echo a reflected credential in even an otherwise valid field.
                    if key in json.dumps(result):
                        raise PreflightError("invalid_model_metadata")
                    return {"status": "authenticated", "http_status": 200, **result}
    except PreflightError:
        raise
    except Exception:
        raise PreflightError("model_discovery_failed") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true", help="One read-only model-list GET")
    parser.add_argument(
        "--output", type=Path, help="New metadata-only JSON artifact; never overwrite"
    )
    args = parser.parse_args(argv)
    try:
        if args.output is not None and (
            os.path.lexists(args.output) or not args.output.parent.is_dir()
        ):
            raise PreflightError("output_path_unavailable")
        key = load_key(args.env_file)
        result = (
            asyncio.run(discover(key)) if args.allow_network else {"status": "local_key_present"}
        )
        result.update(
            schema_version=1,
            checked_at=datetime.now(UTC).isoformat(),
            network_requests=int(args.allow_network),
            inference_calls=0,
            billing_tier="unverified",
            account_quotas="unverified",
            warning="Discovery does not verify free quota, inference access or benchmark quality.",
        )
        payload = json.dumps(result, indent=2) + "\n"
        if args.output is not None:
            # Exclusive creation, including refusal of existing files and leaf symlinks.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
        print(payload, end="")
        return int(result["status"] == "api_rejected")
    except PreflightError as error:
        print(
            json.dumps({"status": "error", "error": error.args[0], "inference_calls": 0}),
            file=sys.stderr,
        )
        return 1
    except Exception:
        print('{"status":"error","error":"preflight_failed","inference_calls":0}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
