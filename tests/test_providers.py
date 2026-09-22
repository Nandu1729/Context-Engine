"""C05 offline transport, replay, crash uncertainty and concurrent ledger admission."""

import asyncio
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import httpx
import pytest

from context_engine.config import BudgetConfig
from context_engine.errors import ContractError, PromptTooLarge, QuotaError, StorageError
from context_engine.models import ChatRequest, Message, Role, Scope, ToolDefinition
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    Completion,
    GenerationConfig,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    RetryConfig,
    TransportFailure,
    Usage,
)
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import GroqTransport, parse_completion, retry_after
from context_engine.tokens import TiktokenCounter

NOW = 1788825600.0
SCOPE = Scope("tenant-a", "session-a")
PRICES = PriceCard("synthetic-v1", 1_000_000, 500_000, 2_000_000)
QUOTA = QuotaPolicy("synthetic-account", 10000, rpm=100, tpm=100000, rpd=100, tpd=100000)
BUDGET = BudgetConfig(input_cap=900)
REQUEST = ChatRequest(
    (Message("s", Role.SYSTEM, "Use supplied facts."), Message("q", Role.USER, "PRIVATE_QUESTION?"))
)


def response(**overrides):
    result = {
        "id": "completion-1",
        "object": "chat.completion",
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "PRIVATE_ANSWER",
                    "reasoning": "PRIVATE_THOUGHT",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 5,
            "total_tokens": 45,
            "prompt_tokens_details": {"cached_tokens": 4},
            "completion_tokens_details": {"reasoning_tokens": 2},
        },
        "system_fingerprint": "fp-test",
    }
    result.update(overrides)
    return result


class FakeTransport:
    namespace = "synthetic-transport-v1"

    def __init__(self, actions=None):
        self.actions = list(
            actions or [parse_completion(json.dumps(response()).encode(), "openai/gpt-oss-120b")]
        )
        self.calls = []

    async def send(self, payload, api_key, timeout):
        self.calls.append((deepcopy(payload), timeout))
        value = self.actions.pop(0) if len(self.actions) > 1 else self.actions[0]
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            return await value()
        return replace(value, model=payload["model"])


@pytest.fixture(scope="module")
def counter():
    return TiktokenCounter()


@pytest.fixture
def store(tmp_path):
    return RuntimeStore(tmp_path / "ledger.sqlite")


def client(store, counter, **kwargs):
    defaults = dict(
        store=store,
        quota=QUOTA,
        prices=PRICES,
        api_key="PRIVATE_TEST_KEY",
        transport=FakeTransport(),
        counter=counter,
        clock=lambda: NOW,
    )
    defaults.update(kwargs)
    return ProviderClient(**defaults)


def call(instance, request=REQUEST, **kwargs):
    options = dict(scope=SCOPE, security_scope="principal-v1", snapshot_revision="history-v1")
    options.update(kwargs)
    return asyncio.run(instance.complete(request, BUDGET, **options))


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (GenerationConfig, {"model": "unsupported"}),
        (GenerationConfig, {"temperature": float("nan")}),
        (GenerationConfig, {"temperature": True}),
        (GenerationConfig, {"reasoning_effort": "max"}),
        (GenerationConfig, {"max_completion_tokens": 65537}),
        (GenerationConfig, {"tool_choice": "required"}),
        (RetryConfig, {"max_attempts": 6}),
        (RetryConfig, {"total_timeout": 0}),
        (RetryConfig, {"attempt_timeout": float("inf")}),
        (ReplayPolicy, {"enabled": "yes"}),
        (ReplayPolicy, {"ttl_seconds": 86401}),
        (QuotaPolicy, {"account_id": "a", "daily_budget_microusd": -1}),
        (QuotaPolicy, {"account_id": "a", "rpm": True}),
    ],
)
def test_invalid_provider_configuration(cls, kwargs):
    with pytest.raises(ContractError):
        cls(**kwargs)


def test_usage_details_and_integer_cached_pricing():
    usage = Usage(100, 20, 40, 10)
    assert usage.total_tokens == 120 and usage.visible_output_tokens == 10
    assert PRICES.observed_cost(usage) == 120
    assert PRICES.observed_cost(Usage(100, 20)) == 140
    assert Usage(100, 20).visible_output_tokens is None
    assert PriceCard("tiny", 1, 1, 1).cost(1, 0) == 1  # Conservative micro-dollar rounding.
    premium = PriceCard("premium-cache", 1_000_000, 2_000_000, 1_000_000)
    assert premium.observed_cost(Usage(10, 1)) == 21
    for kwargs in (
        {"input_tokens": True, "output_tokens": 1},
        {"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 2},
        {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 2},
    ):
        with pytest.raises(ContractError):
            Usage(**kwargs)


def test_transport_exact_payload_hidden_reasoning_and_no_secret_output(store, counter):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response())

    provider = client(
        store, counter, transport=GroqTransport(http_transport=httpx.MockTransport(handler))
    )
    result = call(provider)
    payload = json.loads(seen[0].content)
    assert payload["messages"] == REQUEST.to_wire()["messages"]
    assert payload["include_reasoning"] is False and payload["stream"] is False
    assert payload["max_completion_tokens"] == 256 and payload["reasoning_effort"] == "low"
    assert "reasoning_format" not in payload and "metadata" not in payload
    assert str(seen[0].url) == "https://api.groq.com/openai/v1/chat/completions"
    assert result.status == "success" and result.completion.content == "PRIVATE_ANSWER"
    assert result.new_cost_microusd == 48
    assert result.completion.usage.reasoning_tokens == 2
    serialized = json.dumps(result.to_dict())
    assert "PRIVATE" not in serialized
    assert "PRIVATE_ANSWER" in json.dumps(result.to_dict(include_content=True))
    assert "PRIVATE_TEST_KEY" not in repr(provider)
    assert all(
        token not in store.path.read_bytes()
        for token in (
            b"PRIVATE_QUESTION",
            b"PRIVATE_ANSWER",
            b"PRIVATE_TEST_KEY",
            b"PRIVATE_THOUGHT",
        )
    )


def test_missing_key_zero_spend_and_mismatched_budgets_never_send(store, counter):
    provider = client(store, counter, api_key=None)
    assert call(provider).error_code == "missing_api_key" and not provider.transport.calls
    assert store.snapshot(QUOTA)["attempts"] == []
    assert call(client(store, counter, api_key="bad\nkey")).error_code == "invalid_api_key"
    disabled = client(store, counter, quota=replace(QUOTA, daily_budget_microusd=0))
    assert call(disabled).error_code == "quota_exhausted" and not disabled.transport.calls
    with pytest.raises(ContractError):
        call(client(store, counter, generation=GenerationConfig(max_completion_tokens=512)))
    huge = ChatRequest((Message("q", Role.USER, "long " * 2000),))
    with pytest.raises(PromptTooLarge) as caught:
        call(provider, huge)
    assert caught.value.code == "prompt_too_large"


def test_replay_has_zero_new_spend_works_without_key_and_keeps_source_usage(store, counter):
    replay = ReplayPolicy(enabled=True)
    provider = client(store, counter, replay=replay)
    first, second = call(provider), call(provider)
    assert first.status == "success" and second.status == "replay"
    assert len(provider.transport.calls) == 1 and not second.attempt_ids
    assert (
        second.new_cost_microusd == 0 and second.original_cost_microusd == first.new_cost_microusd
    )
    assert second.completion.usage == first.completion.usage
    assert second.replay_of == first.attempt_ids[0]
    offline = call(client(store, counter, api_key=None, replay=replay))
    assert offline.status == "replay"
    snapshot = store.snapshot(QUOTA)
    assert snapshot["known_cost_microusd"] == first.new_cost_microusd
    assert len(snapshot["attempts"]) == 1 and len(snapshot["events"]) == 2
    assert all(event["new_cost"] == 0 for event in snapshot["events"])


@pytest.mark.parametrize(
    "change",
    [
        "question",
        "scope",
        "security",
        "snapshot",
        "policy",
        "model",
        "generation",
        "prices",
        "transport",
        "tools",
    ],
)
def test_full_request_and_security_identity_invalidate_replay(store, counter, change):
    provider = client(store, counter, replay=ReplayPolicy(True))
    first = call(provider)
    kwargs, request = {}, REQUEST
    if change == "question":
        request = replace(REQUEST, messages=(Message("q2", Role.USER, "different"),))
    elif change == "scope":
        kwargs["scope"] = Scope("tenant-other", "session-a")
    elif change == "security":
        kwargs["security_scope"] = "principal-v2"
    elif change == "snapshot":
        kwargs["snapshot_revision"] = "history-v2"
    elif change == "policy":
        kwargs["policy_version"] = "v2"
    elif change == "model":
        provider.generation = GenerationConfig(model="openai/gpt-oss-20b")
    elif change == "generation":
        provider.generation = GenerationConfig(temperature=0.2)
    elif change == "prices":
        provider.prices = replace(PRICES, version="new-rate-card")
    elif change == "transport":
        provider.transport.namespace = "other-transport"
    else:
        request = replace(REQUEST, tools=(ToolDefinition("lookup", "", '{"type":"object"}'),))
    second = call(provider, request, **kwargs)
    assert second.status == "success" and second.request_key != first.request_key
    assert len(provider.transport.calls) == 2


def test_cache_expiry_corruption_and_cross_entry_copy_fail_closed(store, counter):
    provider = client(store, counter, replay=ReplayPolicy(True, 1))
    first = call(provider)
    provider.clock = lambda: NOW + 1
    second = call(provider)
    assert second.status == "success" and len(provider.transport.calls) == 2
    with store.transaction() as db:
        db.execute("UPDATE replay SET payload='broken' WHERE request_key=?", (first.request_key,))
    failed = call(provider)
    assert failed.error_code == "invalid_replay_cache" and len(provider.transport.calls) == 2
    snapshot = store.snapshot(QUOTA)
    assert snapshot["unresolved_attempts"] == 0


def test_rate_limit_retry_after_and_attempt_accounting(store, counter):
    delays = []

    async def sleep(delay):
        delays.append(delay)

    transport = FakeTransport(
        [
            TransportFailure("rate_limit", uncertain=False, retryable=True, retry_after=2),
            parse_completion(json.dumps(response()).encode(), "openai/gpt-oss-120b"),
        ]
    )
    result = call(client(store, counter, transport=transport, sleep=sleep))
    assert result.status == "success" and len(transport.calls) == 2 and delays == [2]
    attempts = store.snapshot(QUOTA)["attempts"]
    assert [r["state"] for r in attempts] == ["rejected", "completed"]
    assert attempts[0]["charged_tokens"] == 0 and attempts[0]["cost"] == 0
    assert attempts[0]["request_count"] == 1


@pytest.mark.parametrize("delay", [46, 11])
def test_retry_after_exceeding_deadline_or_backoff_is_not_shortened(store, counter, delay):
    transport = FakeTransport(
        [TransportFailure("rate_limit", uncertain=False, retryable=True, retry_after=delay)]
    )
    result = call(client(store, counter, transport=transport))
    assert result.error_code == "rate_limit" and len(transport.calls) == 1


def test_retry_budget_and_quota_rechecked_for_every_attempt(store, counter):
    async def sleep(_):
        pass

    transport = FakeTransport([TransportFailure("rate_limit", uncertain=False, retryable=True)])
    result = call(
        client(store, counter, transport=transport, sleep=sleep, quota=replace(QUOTA, rpd=2))
    )
    assert result.error_code == "quota_exhausted" and len(transport.calls) == 2
    other = RuntimeStore(store.path.parent / "other.sqlite")
    transport = FakeTransport(
        [TransportFailure("connection_not_sent", uncertain=False, retryable=True)]
    )
    result = call(
        client(
            other, counter, transport=transport, sleep=sleep, retries=RetryConfig(max_attempts=2)
        )
    )
    assert result.error_code == "connection_not_sent" and len(transport.calls) == 2
    assert all(row["request_count"] == 0 for row in other.snapshot(QUOTA)["attempts"])


@pytest.mark.parametrize("code", ["timeout", "transport", "provider_error", "invalid_response"])
def test_ambiguous_failures_hold_quota_across_days_and_never_auto_retry(store, counter, code):
    transport = FakeTransport([TransportFailure(code, uncertain=True, retryable=True)])
    provider = client(store, counter, transport=transport)
    result = call(provider)
    assert result.error_code == code and result.new_cost_microusd is None
    assert len(transport.calls) == 1
    snapshot = store.snapshot(QUOTA)
    assert snapshot["held_cost_microusd"] > 0 and snapshot["attempts"][0]["state"] == "uncertain"
    provider.clock = lambda: NOW + 86401
    assert call(provider).error_code == "quota_exhausted"
    assert len(transport.calls) == 1
    store.resolve_uncertain(
        result.attempt_ids[0],
        evidence_ref="operator-confirmation",
        now=NOW + 86401,
        confirmed_not_processed=True,
    )
    assert store.snapshot(QUOTA)["held_cost_microusd"] == 0
    with pytest.raises(StorageError):
        store.resolve_uncertain(
            result.attempt_ids[0],
            evidence_ref="duplicate",
            now=NOW + 86401,
            confirmed_not_processed=True,
        )


def test_async_timeout_and_cancellation_preserve_uncertainty(store, counter):
    async def slow():
        await asyncio.sleep(10)

    provider = client(
        store, counter, transport=FakeTransport([slow]), retries=RetryConfig(attempt_timeout=0.01)
    )
    assert call(provider).error_code == "timeout"
    other = RuntimeStore(store.path.parent / "cancel.sqlite")
    entered = asyncio.Event()

    async def blocking():
        entered.set()
        await asyncio.sleep(10)

    async def exercise():
        provider = client(other, counter, transport=FakeTransport([blocking]))
        task = asyncio.create_task(
            provider.complete(
                REQUEST, BUDGET, scope=SCOPE, security_scope="p", snapshot_revision="v1"
            )
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert other.snapshot(QUOTA)["attempts"][0]["reason"] == "cancelled"
    assert other.snapshot(QUOTA)["unresolved_attempts"] == 1


@pytest.mark.parametrize("finish,status", [("length", "truncated"), ("content_filter", "filtered")])
def test_partial_generations_are_charged_but_not_cached(store, counter, finish, status):
    raw = response()
    raw["choices"][0]["finish_reason"] = finish
    raw["choices"][0]["message"]["content"] = None
    completion = parse_completion(json.dumps(raw).encode(), "openai/gpt-oss-120b")
    provider = client(
        store, counter, transport=FakeTransport([completion]), replay=ReplayPolicy(True)
    )
    first, second = call(provider), call(provider)
    assert first.status == second.status == status and len(provider.transport.calls) == 2
    assert store.snapshot(QUOTA)["known_cost_microusd"] == 96


def test_tool_calls_are_validated_and_never_executed_or_replayed(store, counter):
    raw = response()
    raw["choices"][0]["finish_reason"] = "tool_calls"
    raw["choices"][0]["message"].update(
        content=None,
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{ "q": "x" }'},
            }
        ],
    )
    completion = parse_completion(json.dumps(raw).encode(), "openai/gpt-oss-120b")
    request = replace(REQUEST, tools=(ToolDefinition("lookup", "", '{"type":"object"}'),))
    provider = client(
        store,
        counter,
        generation=GenerationConfig(tool_choice="auto"),
        transport=FakeTransport([completion]),
        replay=ReplayPolicy(True),
    )
    result = call(provider, request)
    assert (
        result.status == "tool_calls"
        and result.completion.tool_calls[0].arguments_json == '{ "q": "x" }'
    )
    assert call(provider, request).status == "tool_calls" and len(provider.transport.calls) == 2
    provider.generation = GenerationConfig(tool_choice="none")
    assert call(provider, request).error_code == "unexpected_tool_call"


@pytest.mark.parametrize(
    "mutation,known_usage",
    [
        ("missing_usage", False),
        ("bad_total", False),
        ("boolean_input", False),
        ("bad_cached", False),
        ("bad_reasoning", False),
        ("wrong_model", False),
        ("missing_choices", True),
        ("bad_content", True),
        ("unknown_finish", True),
    ],
)
def test_malformed_responses_do_not_invent_usage(mutation, known_usage):
    raw = response()
    if mutation == "missing_usage":
        raw.pop("usage")
    elif mutation == "bad_total":
        raw["usage"]["total_tokens"] += 1
    elif mutation == "boolean_input":
        raw["usage"]["prompt_tokens"] = True
    elif mutation == "bad_cached":
        raw["usage"]["prompt_tokens_details"]["cached_tokens"] = 50
    elif mutation == "bad_reasoning":
        raw["usage"]["completion_tokens_details"]["reasoning_tokens"] = 10
    elif mutation == "wrong_model":
        raw["model"] = "different"
    elif mutation == "missing_choices":
        raw.pop("choices")
    elif mutation == "bad_content":
        raw["choices"][0]["message"]["content"] = []
    else:
        raw["choices"][0]["finish_reason"] = "unexpected"
    with pytest.raises(TransportFailure) as caught:
        parse_completion(json.dumps(raw).encode(), "openai/gpt-oss-120b")
    assert caught.value.code == "invalid_response" and caught.value.uncertain
    assert (caught.value.usage is not None) is known_usage


@pytest.mark.parametrize("raw", [b'{"model":NaN}', b'{"model":1,"model":2}', b"\xff", b"{}", b"[]"])
def test_bad_response_json_is_redacted(raw):
    with pytest.raises(TransportFailure):
        parse_completion(raw, "openai/gpt-oss-120b")


@pytest.mark.parametrize(
    "http_status,code,uncertain",
    [
        (400, "provider_rejected", False),
        (401, "authentication", False),
        (403, "permission", False),
        (404, "model_unavailable", False),
        (408, "provider_error", True),
        (500, "provider_error", True),
        (302, "provider_error", True),
    ],
)
def test_http_failures_never_echo_body_or_follow_redirect(http_status, code, uncertain):
    count = []

    def handler(request):
        count.append(request)
        return httpx.Response(
            http_status, text="PRIVATE_ERROR_KEY", headers={"location": "https://evil.example"}
        )

    transport = GroqTransport(http_transport=httpx.MockTransport(handler))
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(transport.send({"model": "openai/gpt-oss-120b"}, "PRIVATE_KEY", 1))
    assert caught.value.code == code and caught.value.uncertain is uncertain
    assert len(count) == 1 and "PRIVATE" not in str(caught.value)


def test_retry_after_parsing_and_transport_429():
    assert retry_after("2", NOW) == 2
    assert retry_after("nan", NOW) is None
    assert retry_after("nonsense", NOW) is None
    assert retry_after("Tue, 08 Sep 2026 00:00:03 GMT", NOW) == 3
    transport = GroqTransport(
        http_transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": "2"})
        )
    )
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(transport.send({}, "PRIVATE", 1))
    assert caught.value.retryable and caught.value.retry_after == 2 and not caught.value.uncertain


def admission(store, policy=QUOTA, key="k", now=NOW, tokens=10, cost=10):
    return store.admit(
        policy=policy,
        key=key,
        model="openai/gpt-oss-120b",
        reserved_tokens=tokens,
        reserved_cost=cost,
        prices=PRICES,
        replay=ReplayPolicy(),
        now=now,
    )


def test_concurrent_reservations_cannot_overspend_and_survive_reopen(store):
    policy = replace(QUOTA, daily_budget_microusd=30)

    def reserve(index):
        try:
            return admission(RuntimeStore(store.path), policy, key=f"k{index}")
        except QuotaError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(16)))
    assert sum(r is not None for r in results) == 3
    snapshot = RuntimeStore(store.path).snapshot(policy)
    assert snapshot["held_cost_microusd"] == 30 and snapshot["unresolved_attempts"] == 3
    with pytest.raises(QuotaError):
        admission(store, policy, key="tomorrow", now=NOW + 86401)


@pytest.mark.parametrize("dimension", ["rpm", "tpm", "rpd", "tpd"])
def test_each_quota_dimension_and_shared_policy_conflict(store, dimension):
    policy = replace(QUOTA, **{dimension: 1 if dimension in ("rpm", "rpd") else 10})
    admission(store, policy)
    with pytest.raises(QuotaError) as caught:
        admission(store, policy, key="other")
    assert caught.value.details["dimension"] == dimension
    with pytest.raises(QuotaError, match="policy changed"):
        admission(store, replace(policy, daily_budget_microusd=20000), key="change")


def test_minute_day_rollover_clock_rollback_and_external_reconciliation(store):
    policy = replace(QUOTA, rpm=1, rpd=2)
    a = admission(store, policy)
    store.mark_inflight(a.attempt_id)
    store.settle(a.attempt_id, now=NOW, reason="provider_rejected")
    with pytest.raises(QuotaError):
        admission(store, policy, key="early", now=NOW + 59)
    b = admission(store, policy, key="later", now=NOW + 60)
    store.mark_inflight(b.attempt_id)
    store.settle(b.attempt_id, now=NOW + 60, uncertain=True, reason="timeout")
    store.resolve_uncertain(
        b.attempt_id, now=NOW + 61, evidence_ref="billing-receipt", usage=Usage(5, 1, 0)
    )
    assert store.snapshot(policy)["known_cost_microusd"] == 7
    with pytest.raises(QuotaError):
        admission(store, policy, key="third", now=NOW + 121)
    assert admission(store, policy, key="next-day", now=NOW + 86401).attempt_id
    with pytest.raises(QuotaError, match="clock"):
        admission(store, policy, key="past", now=NOW)


def test_reconcile_double_charge_corrupt_ledger_and_unrelated_database(store, tmp_path):
    a = admission(store)
    store.mark_inflight(a.attempt_id)
    store.settle(a.attempt_id, now=NOW, reason="provider_rejected")
    with pytest.raises(StorageError):
        store.settle(a.attempt_id, now=NOW, reason="again")
    with store.transaction() as db:
        db.execute("UPDATE attempts SET cost=-100")
    with pytest.raises(StorageError):
        admission(store, key="corrupt")
    unrelated = tmp_path / "unrelated.sqlite"
    connection = sqlite3.connect(unrelated)
    connection.execute("CREATE TABLE user_data(id INTEGER)")
    connection.close()
    os.chmod(unrelated, 0o600)
    with pytest.raises(StorageError, match="unrelated"):
        RuntimeStore(unrelated)
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"not-a-database")
    os.chmod(bad, 0o600)
    with pytest.raises(StorageError):
        RuntimeStore(bad)


def test_private_files_symlinks_and_estimate_overrun(store, counter, tmp_path):
    if os.name == "posix":
        assert store.path.stat().st_mode & 0o777 == 0o600
        broad = tmp_path / "broad.sqlite"
        broad.touch(mode=0o644)
        os.chmod(broad, 0o644)
        with pytest.raises(StorageError, match="private"):
            RuntimeStore(broad)
    link = tmp_path / "link.sqlite"
    link.symlink_to(store.path)
    with pytest.raises(StorageError, match="symlink"):
        RuntimeStore(link)
    completion = Completion("openai/gpt-oss-120b", "oversize", "done", "stop", Usage(4000, 2000, 0))
    result = call(client(store, counter, transport=FakeTransport([completion])))
    assert (
        result.warning == "provider_usage_exceeded_reservation" and result.new_cost_microusd == 8000
    )
    assert store.snapshot(QUOTA)["known_cost_microusd"] == 8000


@pytest.mark.parametrize(
    "kind,uncertain",
    [
        (httpx.ConnectTimeout, False),
        (httpx.ConnectError, False),
        (httpx.PoolTimeout, False),
        (httpx.ReadTimeout, True),
        (httpx.WriteTimeout, True),
        (httpx.ReadError, True),
    ],
)
def test_httpx_failure_classification(kind, uncertain):
    def handler(request):
        raise kind("PRIVATE_RAW_EXCEPTION", request=request)

    transport = GroqTransport(http_transport=httpx.MockTransport(handler))
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(transport.send(GenerationConfig().to_wire(REQUEST), "PRIVATE_KEY", 1))
    assert caught.value.uncertain is uncertain
    assert "PRIVATE" not in str(caught.value)


def test_settlement_failure_holds_inflight_reservation(store, counter, monkeypatch):
    provider = client(store, counter, replay=ReplayPolicy(True))

    def broken(*args, **kwargs):
        raise StorageError("synthetic write failure")

    monkeypatch.setattr(store, "settle", broken)
    result = call(provider)
    assert result.error_code == "runtime_storage_error" and result.new_cost_microusd is None
    assert store.snapshot(QUOTA)["unresolved_attempts"] == 1
    assert call(provider).error_code == "quota_exhausted"
    assert len(provider.transport.calls) == 1
    with store.transaction() as db:
        assert db.execute("SELECT count(*) FROM replay").fetchone()[0] == 0


def test_racing_identical_requests_dispatch_only_once(store, counter):
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()

        async def blocking():
            started.set()
            await finish.wait()
            return parse_completion(json.dumps(response()).encode(), GenerationConfig().model)

        provider = client(store, counter, transport=FakeTransport([blocking]))
        options = dict(scope=SCOPE, security_scope="s", snapshot_revision="r")
        first = asyncio.create_task(provider.complete(REQUEST, BUDGET, **options))
        await started.wait()
        second = await provider.complete(REQUEST, BUDGET, **options)
        assert second.error_code == "quota_exhausted"
        finish.set()
        assert (await first).status == "success"
        assert len(provider.transport.calls) == 1

    asyncio.run(run())


def test_cache_source_cannot_be_rebound_across_security_scope(store, counter):
    provider = client(store, counter, replay=ReplayPolicy(True))
    first = call(provider)
    second = call(provider, security_scope="other-principal")
    with store.transaction() as db:
        db.execute(
            "UPDATE replay SET source_attempt=? WHERE request_key=?",
            (first.attempt_ids[0], second.request_key),
        )
    result = call(provider, security_scope="other-principal")
    assert result.error_code == "invalid_replay_cache" and len(provider.transport.calls) == 2


@pytest.mark.parametrize("details", [[], "", 0, False])
def test_malformed_usage_details_are_unknown(details):
    payload = response()
    payload["usage"]["prompt_tokens_details"] = details
    with pytest.raises(TransportFailure) as caught:
        parse_completion(json.dumps(payload).encode(), GenerationConfig().model)
    assert caught.value.usage is None


def test_unknown_cached_usage_uses_conservative_price_card():
    assert PRICES.observed_cost(Usage(40, 5)) == 50
    assert Usage(40, 5).visible_output_tokens is None
    with pytest.raises(ContractError):
        PRICES.reserve_cost(-1, 5)
    with pytest.raises(ContractError):
        TransportFailure("rate_limit", uncertain=False, retry_after=float("nan"))


def test_retry_attempt_limit_is_enforced(store, counter):
    transport = FakeTransport([TransportFailure("rate_limit", uncertain=False, retryable=True)])

    async def no_wait(_):
        pass

    result = call(client(store, counter, transport=transport, sleep=no_wait))
    assert result.error_code == "rate_limit" and len(transport.calls) == 3
    assert len(result.attempt_ids) == 3 and result.new_cost_microusd == 0
