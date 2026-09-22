"""Groq HTTPS transport with bounded body reads, no redirects and no automatic retries."""

import json
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib import metadata

from ..errors import ContractError
from ..models import ToolCall
from .contracts import ENDPOINT, Completion, TransportFailure, Usage, identifier


def retry_after(value: str | None, now: float) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            seconds = date.timestamp() - now
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def parse_completion(raw: bytes, expected_model: str) -> Completion:
    usage = None

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("nonfinite")

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject)
        if data["model"] != expected_model or data["object"] != "chat.completion":
            raise ValueError("response identity mismatch")
        response_id = identifier(data["id"])
        raw_usage = data["usage"]
        for name in ("prompt_tokens_details", "completion_tokens_details"):
            if raw_usage.get(name) is not None and not isinstance(raw_usage[name], dict):
                raise ValueError("invalid usage details")
        usage = Usage(
            raw_usage["prompt_tokens"],
            raw_usage["completion_tokens"],
            (raw_usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            (raw_usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        )
        if (
            type(raw_usage["total_tokens"]) is not int
            or raw_usage["total_tokens"] != usage.total_tokens
        ):
            usage = None
            raise ValueError("inconsistent total")
        if (
            len(data["choices"]) != 1
            or type(data["choices"][0]["index"]) is not int
            or data["choices"][0]["index"] != 0
        ):
            raise ValueError("invalid choices")
        choice = data["choices"][0]
        message = choice["message"]
        if message["role"] != "assistant":
            raise ValueError("invalid response role")
        calls = []
        for call in message.get("tool_calls") or ():
            if call["type"] != "function":
                raise ValueError("unknown tool kind")
            calls.append(
                ToolCall(call["id"], call["function"]["name"], call["function"]["arguments"])
            )
        content = message.get("content")
        if content is None and choice["finish_reason"] in (
            "tool_calls",
            "length",
            "content_filter",
        ):
            content = ""
        return Completion(
            expected_model,
            response_id,
            content,
            choice["finish_reason"],
            usage,
            tuple(calls),
            data.get("system_fingerprint"),
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        ContractError,
    ):
        raise TransportFailure("invalid_response", uncertain=True, usage=usage) from None


class GroqTransport:
    """A custom HTTP transport is for offline testing, not an authorization boundary."""

    def __init__(self, *, http_transport=None):
        self.http_transport = http_transport
        try:
            version = metadata.version("httpx")
        except metadata.PackageNotFoundError:
            version = "unavailable"
        mode = "live" if http_transport is None else "test-http"
        self.namespace = f"groq-{mode}-httpx-{version}-v1"

    async def send(self, payload: dict, api_key: str, timeout: float) -> Completion:
        try:
            import httpx
        except ImportError:
            raise TransportFailure("provider_extra_missing", uncertain=False) from None
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST",
                    ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": "Bearer " + api_key,
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status_code == 429:
                        delay = retry_after(
                            response.headers.get("retry-after"), datetime.now(UTC).timestamp()
                        )
                        raise TransportFailure(
                            "rate_limit", uncertain=False, retryable=True, retry_after=delay
                        )
                    if 400 <= response.status_code < 500 and response.status_code != 408:
                        code = {
                            401: "authentication",
                            403: "permission",
                            404: "model_unavailable",
                        }.get(response.status_code, "provider_rejected")
                        raise TransportFailure(code, uncertain=False)
                    if response.status_code != 200:
                        raise TransportFailure("provider_error", uncertain=True)
                    body = bytearray()
                    async for part in response.aiter_bytes():
                        body.extend(part)
                        if len(body) > 2_000_000:
                            raise TransportFailure("response_too_large", uncertain=True)
                    return parse_completion(bytes(body), payload["model"])
        except TransportFailure:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise TransportFailure("connection_not_sent", uncertain=False, retryable=True) from None
        except httpx.TimeoutException:
            raise TransportFailure("timeout", uncertain=True) from None
        except httpx.HTTPError:
            raise TransportFailure("transport", uncertain=True) from None
