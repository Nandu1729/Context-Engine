"""Scoped provider execution, final token admission, quota reservations and local replay."""

import asyncio
import time
from dataclasses import asdict

from ..budget import validate_request
from ..config import BudgetConfig
from ..errors import ContextEngineError, ContractError, StorageError
from ..models import ChatRequest, Scope, canonical_json, text_value
from ..tokens import TiktokenCounter
from .contracts import (
    ADAPTER_VERSION,
    ENDPOINT,
    Completion,
    GenerationConfig,
    ModelResult,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    RetryConfig,
    TransportFailure,
    fingerprint,
)
from .store import RuntimeStore
from .transport import GroqTransport


class ProviderClient:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        quota: QuotaPolicy,
        prices: PriceCard,
        api_key: str | None = None,
        generation: GenerationConfig | None = None,
        retries: RetryConfig | None = None,
        replay: ReplayPolicy | None = None,
        transport=None,
        counter=None,
        clock=time.time,
        monotonic=time.monotonic,
        sleep=asyncio.sleep,
    ):
        self.store, self.quota, self.prices = store, quota, prices
        self._api_key = api_key  # Never exported, represented or persisted.
        self.generation = generation or GenerationConfig()
        self.retries, self.replay = retries or RetryConfig(), replay or ReplayPolicy()
        self.transport = transport if transport is not None else GroqTransport()
        self.counter = counter if counter is not None else TiktokenCounter()
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        for value, cls in (
            (store, RuntimeStore),
            (quota, QuotaPolicy),
            (prices, PriceCard),
            (self.generation, GenerationConfig),
            (self.retries, RetryConfig),
            (self.replay, ReplayPolicy),
        ):
            if not isinstance(value, cls):
                raise ContractError("Provider client requires validated configuration")
        quota.validate_prices(prices)

    async def complete(
        self,
        request: ChatRequest,
        budget: BudgetConfig,
        *,
        scope: Scope,
        security_scope: str,
        snapshot_revision: str,
        policy_version="v1",
    ) -> ModelResult:
        """Caller authorizes scope. Task cancellation preserves uncertain accounting."""
        start = self.monotonic()
        generation = self.generation
        if (
            not isinstance(request, ChatRequest)
            or not isinstance(budget, BudgetConfig)
            or not isinstance(scope, Scope)
        ):
            raise ContractError("Provider call requires validated request, budget and scope")
        for name, value in (
            ("security_scope", security_scope),
            ("snapshot_revision", snapshot_revision),
            ("policy_version", policy_version),
        ):
            text_value(name, value)
        if (
            budget.completion_reservation != generation.max_completion_tokens
            or budget.model_capacity > 131072
        ):
            raise ContractError("Assembly and provider completion/context budgets must agree")
        estimate = validate_request(request=request, config=budget, counter=self.counter)
        payload = generation.to_wire(request)
        if len(canonical_json(payload).encode()) > 2_000_000:
            raise ContractError("Provider request exceeds the byte limit")
        key = fingerprint(
            {
                "adapter": ADAPTER_VERSION,
                "endpoint": ENDPOINT,
                "payload": payload,
                "account": self.quota.account_id,
                "scope": asdict(scope),
                "security_scope": security_scope,
                "snapshot_revision": snapshot_revision,
                "policy_version": policy_version,
                "budget": asdict(budget),
                "counting": estimate.to_dict(),
                "prices": asdict(self.prices),
                "transport": getattr(
                    self.transport, "namespace", type(self.transport).__qualname__
                ),
            }
        )
        key_error = None
        if not isinstance(self._api_key, str) or not self._api_key.strip():
            key_error = "missing_api_key"
        elif any(ord(c) < 33 or ord(c) > 126 for c in self._api_key):
            key_error = "invalid_api_key"
        attempts, known_cost = [], 0
        reserved_tokens = estimate.estimated_tokens + generation.max_completion_tokens
        reserve_cost = self.prices.reserve_cost(
            estimate.estimated_tokens, generation.max_completion_tokens
        )
        for number in range(self.retries.max_attempts):
            remaining = self.retries.total_timeout - (self.monotonic() - start)
            if remaining <= 0:
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code="deadline",
                    new_cost_microusd=known_cost,
                )
            try:
                admission = self.store.admit(
                    policy=self.quota,
                    key=key,
                    model=generation.model,
                    reserved_tokens=reserved_tokens,
                    reserved_cost=reserve_cost,
                    prices=self.prices,
                    replay=self.replay,
                    now=self.clock(),
                    send_allowed=key_error is None,
                )
            except ContextEngineError as error:
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code=key_error or error.code,
                    new_cost_microusd=known_cost,
                )
            if admission.completion is not None:
                return ModelResult(
                    "replay",
                    key,
                    tuple(attempts),
                    admission.completion,
                    replay_of=admission.source_attempt,
                    new_cost_microusd=known_cost,
                    original_cost_microusd=admission.original_cost,
                )
            attempt = admission.attempt_id
            attempts.append(attempt)
            try:
                self.store.mark_inflight(attempt)
            except StorageError:
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code="runtime_storage_error",
                    new_cost_microusd=known_cost,
                    warning="reservation_held_no_dispatch",
                )
            try:
                remaining = self.retries.total_timeout - (self.monotonic() - start)
                if remaining <= 0:
                    raise TransportFailure("deadline_not_sent", uncertain=False)
                timeout = min(remaining, self.retries.attempt_timeout)
                async with asyncio.timeout(timeout):
                    completion = await self.transport.send(payload, self._api_key, timeout)
                if not isinstance(completion, Completion) or completion.model != generation.model:
                    raise TransportFailure("invalid_response", uncertain=True)
                if completion.tool_calls:
                    names = {tool.name for tool in request.tools}
                    if generation.tool_choice != "auto" or any(
                        call.name not in names for call in completion.tool_calls
                    ):
                        raise TransportFailure(
                            "unexpected_tool_call", uncertain=True, usage=completion.usage
                        )
            except asyncio.CancelledError:
                # A cancelled task may already have reached the provider. No automatic release.
                try:
                    self.store.settle(attempt, now=self.clock(), uncertain=True, reason="cancelled")
                except StorageError:
                    pass  # Existing inflight reservation remains conservatively held.
                raise
            except TimeoutError:
                failure = TransportFailure("timeout", uncertain=True)
            except TransportFailure as error:
                failure = error
            except Exception:
                failure = TransportFailure("transport", uncertain=True)
            else:
                try:
                    cost, warning = self.store.settle(
                        attempt, now=self.clock(), completion=completion, replay=self.replay
                    )
                except StorageError:
                    return ModelResult(
                        "error",
                        key,
                        tuple(attempts),
                        error_code="runtime_storage_error",
                        new_cost_microusd=None,
                        warning="provider_may_have_charged_reservation_held",
                    )
                return ModelResult(
                    {
                        "stop": "success",
                        "length": "truncated",
                        "tool_calls": "tool_calls",
                        "content_filter": "filtered",
                    }[completion.finish_reason],
                    key,
                    tuple(attempts),
                    completion,
                    new_cost_microusd=known_cost + cost,
                    original_cost_microusd=cost,
                    warning=warning,
                )
            try:
                cost, warning = self.store.settle(
                    attempt,
                    now=self.clock(),
                    usage=failure.usage,
                    uncertain=failure.uncertain,
                    reason=failure.code,
                    sent=failure.code
                    not in ("connection_not_sent", "deadline_not_sent", "provider_extra_missing"),
                )
            except StorageError:
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code="runtime_storage_error",
                    new_cost_microusd=None,
                    warning="reservation_held",
                )
            if cost is None:
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code=failure.code,
                    new_cost_microusd=None,
                    warning=warning,
                )
            known_cost += cost
            delay = (
                failure.retry_after
                if failure.retry_after is not None
                else min(0.25 * 2**number, self.retries.max_backoff)
            )
            remaining = self.retries.total_timeout - (self.monotonic() - start)
            if (
                not failure.retryable
                or failure.uncertain
                or number + 1 >= self.retries.max_attempts
                or delay > self.retries.max_backoff
                or delay >= remaining
            ):
                return ModelResult(
                    "error",
                    key,
                    tuple(attempts),
                    error_code=failure.code,
                    new_cost_microusd=known_cost,
                    warning=warning,
                )
            await self.sleep(delay)
        raise AssertionError("Bounded provider loop exhausted unexpectedly")
