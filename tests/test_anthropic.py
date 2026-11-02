"""Offline Anthropic (Claude Messages API) provider tests. No network; live use PENDING."""

import asyncio
import json

import httpx
import pytest

from context_engine.config import BudgetConfig
from context_engine.errors import ContractError
from context_engine.models import ChatRequest, Message, Role, Scope, ToolDefinition
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    ANTHROPIC_ENDPOINT,
    AnthropicGenerationConfig,
    GenerationConfig,
    InceptionGenerationConfig,
    PriceCard,
    QuotaPolicy,
    RetryConfig,
    TransportFailure,
)
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import (
    AnthropicTransport,
    GroqTransport,
    InceptionTransport,
    parse_anthropic_message,
)

NOW = 1788825600.0
SCOPE = Scope("tenant-a", "session-a")
# Published Claude Haiku 5.5 prices (USD/1M, prompts up to 100k): input 0.10,
# cache hits 0.01, output 0.50 (platform.claude.com pricing, read 2026-11-02).
PRICES = PriceCard("anthropic-claude-haiku-5-5-2026-11-02", 100_000, 10_000, 500_000)
QUOTA = QuotaPolicy("anthropic-synthetic", 1000, rpm=100, tpm=1_000_000, rpd=100, tpd=1_000_000)
BUDGET = BudgetConfig(input_cap=900)
REQUEST = ChatRequest(
    (Message("s", Role.SYSTEM, "Use supplied facts."), Message("q", Role.USER, "PRIVATE_QUESTION?"))
)
GENERATION = AnthropicGenerationConfig()
MODEL = "claude-haiku-5-5"


def body(model=MODEL, content=None, stop_reason="end_turn", **usage):
    return {
        "id": "msg_01TEST",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": "A"}] if content is None else content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": 40,
            "output_tokens": 6,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens_details": {"thinking_tokens": 2},
            **usage,
        },
    }


def provider(tmp_path, handler, **kwargs):
    return ProviderClient(
        store=RuntimeStore(tmp_path / "ledger.sqlite"),
        quota=kwargs.pop("quota", QUOTA),
        prices=PRICES,
        api_key="TEST_ONLY_KEY",
        generation=kwargs.pop("generation", GENERATION),
        retries=RetryConfig(max_attempts=1),
        transport=AnthropicTransport(http_transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
        **kwargs,
    )


def call(client):
    return asyncio.run(
        client.complete(REQUEST, BUDGET, scope=SCOPE, security_scope="t", snapshot_revision="r")
    )


def parse(raw):
    return parse_anthropic_message(json.dumps(raw).encode(), MODEL)


@pytest.mark.parametrize(
    "settings",
    [
        {"model": "claude-opus-5-5"},  # Always thinks: "off" is refused.
        {"model": "claude-fable-5-1"},
        {"model": "mercury-3"},
        {"thinking": "enabled"},
        {"effort": "max"},  # Rejected by the API with thinking off.
        {"effort": "xhigh"},
        {"effort": "maximum"},
        {"max_completion_tokens": 0},
        {"max_completion_tokens": 128001},
        {"tool_choice": "auto"},
    ],
)
def test_generation_config_enforces_limits(settings):
    with pytest.raises(ContractError):
        AnthropicGenerationConfig(**settings)


def test_wire_payload_uses_messages_api_fields():
    payload = GENERATION.to_wire(REQUEST)
    assert payload["model"] == MODEL and payload["max_tokens"] == 256
    assert payload["system"] == "Use supplied facts."
    assert payload["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "PRIVATE_QUESTION?"}]}
    ]
    assert payload["thinking"] == {"type": "disabled"} and payload["stream"] is False
    assert "temperature" not in payload and "output_config" not in payload
    assert "max_completion_tokens" not in payload and "tool_choice" not in payload


def test_wire_thinking_settings_per_model():
    sonnet = AnthropicGenerationConfig(model="claude-sonnet-5-5")
    assert sonnet.to_wire(REQUEST)["thinking"] == {"type": "between_tools"}
    adaptive = AnthropicGenerationConfig(thinking="adaptive", effort="low")
    payload = adaptive.to_wire(REQUEST)
    assert payload["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert payload["output_config"] == {"effort": "low"}


def test_wire_omits_empty_system_and_refuses_tools():
    user_only = ChatRequest((Message("q", Role.USER, "Q?"),))
    assert "system" not in GENERATION.to_wire(user_only)
    tools = ChatRequest(REQUEST.messages, tools=(ToolDefinition("f", "", '{"type":"object"}'),))
    with pytest.raises(ContractError):
        GENERATION.to_wire(tools)


def test_transport_posts_with_api_key_header_and_meters_cost(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=body())

    result = call(provider(tmp_path, handler))
    assert str(seen[0].url) == ANTHROPIC_ENDPOINT
    assert seen[0].headers["x-api-key"] == "TEST_ONLY_KEY"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in seen[0].headers
    assert result.status == "success" and result.completion.content == "A"
    assert result.completion.finish_reason == "stop"
    assert result.completion.usage.reasoning_tokens == 2
    # 40 input x 0.10 + 6 output x 0.50 USD per million = 7.0 micro-dollars.
    assert result.new_cost_microusd == 7
    assert "TEST_ONLY_KEY" not in json.dumps(result.to_dict(include_content=True))


def test_thinking_blocks_are_dropped_and_text_joined():
    content = [
        {"type": "thinking", "thinking": "PRIVATE_THOUGHT", "signature": "sig"},
        {"type": "redacted_thinking", "data": "opaque"},
        {"type": "text", "text": "node"},
        {"type": "text", "text": "-52"},
    ]
    completion = parse(body(content=content))
    assert completion.content == "node-52" and "PRIVATE" not in completion.content


def test_cache_reads_count_as_cached_input():
    usage = parse(body(input_tokens=10, cache_read_input_tokens=30)).usage
    assert usage.input_tokens == 40 and usage.cached_input_tokens == 30


@pytest.mark.parametrize(
    "stop_reason,status",
    [("max_tokens", "truncated"), ("model_context_window_exceeded", "truncated")]
    + [("refusal", "filtered")],
)
def test_partial_stops_map_to_chat_finish_reasons(tmp_path, stop_reason, status):
    raw = body(content=[], stop_reason=stop_reason)
    result = call(provider(tmp_path, lambda request: httpx.Response(200, json=raw)))
    assert result.status == status and result.completion.content == ""
    assert result.new_cost_microusd == 7


def test_no_text_with_end_turn_is_a_certain_empty_response(tmp_path):
    with pytest.raises(TransportFailure) as caught:
        parse(body(content=[{"type": "thinking", "thinking": "", "signature": "s"}]))
    assert caught.value.code == "empty_response" and not caught.value.uncertain
    raw = body(content=[])
    result = call(provider(tmp_path, lambda request: httpx.Response(200, json=raw)))
    assert result.status == "error" and result.error_code == "empty_response"
    assert result.new_cost_microusd == 7 and result.warning is None


@pytest.mark.parametrize(
    "raw",
    [
        body(model="claude-sonnet-5-5"),
        body(content=[{"type": "tool_use", "id": "t", "name": "f", "input": {}}]),
        body(stop_reason="pause_turn"),
        body(stop_reason="tool_use"),
        body(cache_creation_input_tokens=5),  # Never requested: cost would be wrong.
        {**body(), "type": "error"},
        body(output_tokens_details=[]),
    ],
)
def test_unexpected_responses_are_uncertain(raw):
    with pytest.raises(TransportFailure) as caught:
        parse(raw)
    assert caught.value.code == "invalid_response" and caught.value.uncertain


@pytest.mark.parametrize(
    "status,code,uncertain",
    [
        (400, "provider_rejected", False),
        (401, "authentication", False),
        (402, "billing_or_quota", False),
        (429, "rate_limit", False),
        (529, "provider_error", True),
    ],
)
def test_http_errors_stop_without_retry(tmp_path, status, code, uncertain):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"type": "error", "error": {"message": "PRIVATE"}})

    client = provider(tmp_path, handler)
    result = call(client)
    assert result.status == "error" and result.error_code == code and len(calls) == 1
    assert "PRIVATE" not in json.dumps(result.to_dict())
    held = client.store.snapshot(QUOTA)["unresolved_attempts"]
    assert held == int(uncertain)


def test_generation_and_transport_must_match(tmp_path):
    store = RuntimeStore(tmp_path / "ledger.sqlite")
    common = dict(store=store, quota=QUOTA, prices=PRICES, api_key="k")
    for generation, transport in (
        (GENERATION, GroqTransport()),
        (GENERATION, InceptionTransport()),
        (GenerationConfig(), AnthropicTransport()),
        (InceptionGenerationConfig(), AnthropicTransport()),
    ):
        with pytest.raises(ContractError):
            ProviderClient(**common, generation=generation, transport=transport)
    assert type(ProviderClient(**common, generation=GENERATION).transport) is AnthropicTransport
    assert AnthropicTransport().namespace.startswith("anthropic-live-httpx-")


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-fable-5-1"])
def test_always_thinking_models_use_adaptive_thinking(tmp_path, model):
    generation = AnthropicGenerationConfig(
        model=model, max_completion_tokens=8192, thinking="adaptive", effort="high"
    )
    payload = generation.to_wire(REQUEST)
    assert payload["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert payload["output_config"] == {"effort": "high"} and payload["max_tokens"] == 8192
    raw = body(model=model)
    budget = BudgetConfig(input_cap=9000, completion_reservation=8192)
    roomy = QuotaPolicy("anthropic-roomy", 100_000, rpm=100, tpm=1_000_000, rpd=100, tpd=10**6)
    client = provider(
        tmp_path, lambda request: httpx.Response(200, json=raw), generation=generation, quota=roomy
    )
    result = asyncio.run(
        client.complete(REQUEST, budget, scope=SCOPE, security_scope="t", snapshot_revision="r")
    )
    assert result.status == "success" and result.completion.model == model
    assert AnthropicGenerationConfig(model=model, thinking="adaptive", effort="max")
