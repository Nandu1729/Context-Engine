"""Provider/accounting contracts; monetary amounts are integer micro-US dollars."""

import hashlib
import math
import re
from dataclasses import asdict, dataclass

from ..errors import ContractError
from ..models import ToolCall, canonical_json, freeze_sequence, integer_value, text_value

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
ADAPTER_VERSION = "groq-chat-v1"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")


def fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def positive_number(name, value, maximum=300):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ContractError("Expected a positive finite bounded duration", field=name)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", value):
        raise ContractError("Invalid opaque provider identifier")
    return value


@dataclass(frozen=True)
class GenerationConfig:
    model: str = MODELS[0]
    max_completion_tokens: int = 256
    temperature: float = 0.0
    reasoning_effort: str = "low"
    tool_choice: str = "none"

    def __post_init__(self):
        if self.model not in MODELS or self.reasoning_effort not in ("low", "medium", "high"):
            raise ContractError("Unsupported C05 model or reasoning setting")
        integer_value("max_completion_tokens", self.max_completion_tokens, minimum=1)
        if self.max_completion_tokens > 65536:
            raise ContractError("Completion request exceeds model profile")
        if (
            type(self.temperature) not in (int, float)
            or not math.isfinite(self.temperature)
            or not 0 <= self.temperature <= 2
        ):
            raise ContractError("Invalid generation temperature")
        if self.tool_choice not in ("none", "auto"):
            raise ContractError("Unsupported tool choice")

    def to_wire(self, request):
        payload = {
            **request.to_wire(),
            **asdict(self),
            "stream": False,
            "n": 1,
            "include_reasoning": False,
            "service_tier": "on_demand",
        }
        if not request.tools:
            payload.pop("tool_choice")
        return payload


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    attempt_timeout: float = 20.0
    total_timeout: float = 45.0
    max_backoff: float = 10.0

    def __post_init__(self):
        integer_value("max_attempts", self.max_attempts, minimum=1)
        if self.max_attempts > 5:
            raise ContractError("Retry attempt limit is five")
        for name in ("attempt_timeout", "total_timeout", "max_backoff"):
            positive_number(name, getattr(self, name))


@dataclass(frozen=True)
class QuotaPolicy:
    account_id: str
    daily_budget_microusd: int = 0
    rpm: int = 30
    tpm: int = 8000
    rpd: int = 1000
    tpd: int = 200000
    billing_mode: str = "metered"

    def __post_init__(self):
        identifier(self.account_id)
        if self.billing_mode not in ("metered", "free_tier"):
            raise ContractError("Billing mode must be metered or explicitly confirmed free_tier")
        if self.billing_mode == "free_tier" and self.daily_budget_microusd != 0:
            raise ContractError("Free-tier mode requires a zero daily paid-spending cap")
        for name in ("daily_budget_microusd", "rpm", "tpm", "rpd", "tpd"):
            integer_value(name, getattr(self, name))
            if getattr(self, name) > 10**12:
                raise ContractError("Quota exceeds local integer accounting range")

    def validate_prices(self, prices):
        if not isinstance(prices, PriceCard):
            raise ContractError("A validated price card is required")
        if self.billing_mode == "free_tier" and prices.reserve_cost(1_000_000, 1_000_000) != 0:
            raise ContractError("Free-tier mode requires zero configured token prices")


@dataclass(frozen=True)
class PriceCard:
    version: str
    input_per_million_microusd: int
    cached_input_per_million_microusd: int
    output_per_million_microusd: int

    def __post_init__(self):
        identifier(self.version)
        for name in (
            "input_per_million_microusd",
            "cached_input_per_million_microusd",
            "output_per_million_microusd",
        ):
            integer_value(name, getattr(self, name))
            if getattr(self, name) > 10**12:
                raise ContractError("Price exceeds local integer accounting range")

    def cost(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> int:
        for value in (input_tokens, output_tokens, cached_tokens):
            integer_value("tokens", value)
        if cached_tokens > input_tokens:
            raise ContractError("Cached input exceeds total input")
        numerator = (
            (input_tokens - cached_tokens) * self.input_per_million_microusd
            + cached_tokens * self.cached_input_per_million_microusd
            + output_tokens * self.output_per_million_microusd
        )
        return (numerator + 999999) // 1000000

    def reserve_cost(self, input_tokens: int, output_tokens: int) -> int:
        for value in (input_tokens, output_tokens):
            integer_value("tokens", value)
        # Never assume that caching is discounted in an arbitrary caller-supplied price card.
        numerator = input_tokens * max(
            self.input_per_million_microusd, self.cached_input_per_million_microusd
        )
        return (numerator + output_tokens * self.output_per_million_microusd + 999999) // 1000000

    def observed_cost(self, usage) -> int:
        if usage.cached_input_tokens is None:
            return self.reserve_cost(usage.input_tokens, usage.output_tokens)
        return self.cost(usage.input_tokens, usage.output_tokens, usage.cached_input_tokens)


@dataclass(frozen=True)
class ReplayPolicy:
    enabled: bool = False
    ttl_seconds: int = 3600

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ContractError("Replay must be explicitly enabled with a boolean")
        integer_value("ttl_seconds", self.ttl_seconds, minimum=1)
        if self.ttl_seconds > 86400:
            raise ContractError("C05 replay TTL is limited to one day")


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None

    def __post_init__(self):
        for name in ("input_tokens", "output_tokens"):
            integer_value(name, getattr(self, name))
        for name, maximum in (
            ("cached_input_tokens", self.input_tokens),
            ("reasoning_tokens", self.output_tokens),
        ):
            value = getattr(self, name)
            if value is not None:
                integer_value(name, value)
                if value > maximum:
                    raise ContractError("Usage detail exceeds its containing total")
        if self.input_tokens + self.output_tokens > 10**9:
            raise ContractError("Usage exceeds supported accounting range")

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @property
    def visible_output_tokens(self):
        return None if self.reasoning_tokens is None else self.output_tokens - self.reasoning_tokens


@dataclass(frozen=True)
class Completion:
    model: str
    response_id: str
    content: str
    finish_reason: str
    usage: Usage
    tool_calls: tuple[ToolCall, ...] = ()
    system_fingerprint: str | None = None

    def __post_init__(self):
        identifier(self.response_id)
        if self.model not in MODELS or self.finish_reason not in (
            "stop",
            "length",
            "tool_calls",
            "content_filter",
        ):
            raise ContractError("Unsupported provider completion")
        text_value("content", self.content, nonempty=False)
        if not isinstance(self.usage, Usage):
            raise ContractError("Completion requires validated usage")
        calls = freeze_sequence(self, "tool_calls", ToolCall)
        if bool(calls) != (self.finish_reason == "tool_calls") or len(
            {c.call_id for c in calls}
        ) != len(calls):
            raise ContractError("Tool-call finish reason disagrees with response")
        if self.system_fingerprint is not None:
            identifier(self.system_fingerprint)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data["usage"] = Usage(**data["usage"])
        data["tool_calls"] = tuple(ToolCall(**c) for c in data["tool_calls"])
        return cls(**data)


class TransportFailure(Exception):
    """Only controlled metadata crosses the network/ledger boundary."""

    def __init__(
        self, code: str, *, uncertain: bool, retryable=False, retry_after=None, usage=None
    ):
        identifier(code)
        if type(uncertain) is not bool or type(retryable) is not bool:
            raise ContractError("Failure flags must be booleans")
        if retry_after is not None and (
            type(retry_after) not in (int, float)
            or not math.isfinite(retry_after)
            or retry_after < 0
        ):
            raise ContractError("Invalid retry delay")
        if usage is not None and not isinstance(usage, Usage):
            raise ContractError("Failure usage must be validated")
        super().__init__(code)
        self.code, self.uncertain, self.retryable = code, uncertain, retryable
        self.retry_after, self.usage = retry_after, usage


@dataclass(frozen=True)
class ModelResult:
    status: str
    request_key: str
    attempt_ids: tuple[str, ...] = ()
    completion: Completion | None = None
    error_code: str | None = None
    replay_of: str | None = None
    new_cost_microusd: int | None = 0
    original_cost_microusd: int | None = None
    warning: str | None = None

    def to_dict(self, *, include_content=False):
        if type(include_content) is not bool:
            raise ContractError("Content export requires an explicit boolean")
        result = asdict(self)
        if self.completion is not None and not include_content:
            result["completion"].pop("content")
            result["completion"].pop("tool_calls")
        result["content_included"] = include_content
        return result
