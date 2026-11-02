"""Offline Inception (Mercury) provider tests. No network; live verification is PENDING."""

import asyncio
import json

import httpx
import pytest

from context_engine.config import BudgetConfig
from context_engine.errors import ContractError
from context_engine.models import ChatRequest, Message, Role, Scope
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    ADAPTER_VERSION,
    ENDPOINT,
    INCEPTION_ENDPOINT,
    GenerationConfig,
    InceptionGenerationConfig,
    PriceCard,
    QuotaPolicy,
    RetryConfig,
)
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import GroqTransport, InceptionTransport

NOW = 1788825600.0
SCOPE = Scope("tenant-a", "session-a")
# Published mercury-3 launch prices (USD/1M): input 0.10, cached 0.01, output 0.35.
PRICES = PriceCard("inception-mercury-3-2026-10-31", 100_000, 10_000, 350_000)
QUOTA = QuotaPolicy("inception-synthetic", 1000, rpm=100, tpm=1_000_000, rpd=100, tpd=1_000_000)
BUDGET = BudgetConfig(input_cap=900)
REQUEST = ChatRequest(
    (Message("s", Role.SYSTEM, "Use supplied facts."), Message("q", Role.USER, "PRIVATE_QUESTION?"))
)
GENERATION = InceptionGenerationConfig()


def body(model="mercury-3", **usage):
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "A"}}
        ],
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 6,
            "total_tokens": 46,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 2},
            **usage,
        },
        "warning": None,
    }


def provider(tmp_path, handler, **kwargs):
    return ProviderClient(
        store=RuntimeStore(tmp_path / "ledger.sqlite"),
        quota=kwargs.pop("quota", QUOTA),
        prices=PRICES,
        api_key="TEST_ONLY_KEY",
        generation=GENERATION,
        retries=RetryConfig(max_attempts=1),
        transport=InceptionTransport(http_transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
        **kwargs,
    )


def call(client):
    return asyncio.run(
        client.complete(REQUEST, BUDGET, scope=SCOPE, security_scope="t", snapshot_revision="r")
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"temperature": 0.0},
        {"temperature": 1.5},
        {"model": "openai/gpt-oss-20b"},
        {"reasoning_effort": "none"},
        {"max_completion_tokens": 50001},
    ],
)
def test_generation_config_enforces_documented_limits(settings):
    with pytest.raises(ContractError):
        InceptionGenerationConfig(**settings)


def test_wire_payload_has_only_openai_compatible_fields():
    payload = GENERATION.to_wire(REQUEST)
    assert payload["model"] == "mercury-3" and payload["max_completion_tokens"] == 256
    assert payload["temperature"] == 0.5 and payload["reasoning_effort"] == "low"
    assert payload["stream"] is False and "tool_choice" not in payload
    assert "include_reasoning" not in payload and "service_tier" not in payload


def test_transport_posts_to_inception_with_bearer_key_and_meters_cost(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=body())

    result = call(provider(tmp_path, handler))
    assert str(seen[0].url) == INCEPTION_ENDPOINT
    assert seen[0].headers["authorization"] == "Bearer TEST_ONLY_KEY"
    assert json.loads(seen[0].content)["messages"] == REQUEST.to_wire()["messages"]
    assert result.status == "success" and result.completion.content == "A"
    assert result.completion.usage.reasoning_tokens == 2
    # 40 input x 0.10 + 6 output x 0.35 USD per million, rounded up to micro-dollars.
    assert result.new_cost_microusd == 7
    assert "TEST_ONLY_KEY" not in json.dumps(result.to_dict(include_content=True))


@pytest.mark.parametrize(
    "status,code", [(402, "billing_or_quota"), (429, "rate_limit"), (400, "provider_rejected")]
)
def test_http_errors_stop_without_retry(tmp_path, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "PRIVATE_BODY"}})

    result = call(provider(tmp_path, handler))
    assert result.status == "error" and result.error_code == code
    assert len(calls) == 1 and "PRIVATE_BODY" not in json.dumps(result.to_dict())


def test_daily_spend_cap_blocks_before_sending(tmp_path):
    def handler(request):
        pytest.fail("Over-cap request must not be sent")

    capped = QuotaPolicy("inception-capped", 1, rpm=100, tpm=1_000_000, rpd=100, tpd=1_000_000)
    result = call(provider(tmp_path, handler, quota=capped))
    assert result.status == "error" and result.attempt_ids == ()


def test_model_identity_mismatch_is_rejected(tmp_path):
    result = call(provider(tmp_path, lambda request: httpx.Response(200, json=body("mercury-2"))))
    assert result.status == "error" and result.error_code == "invalid_response"


def test_generation_and_transport_must_match(tmp_path):
    store = RuntimeStore(tmp_path / "ledger.sqlite")
    common = dict(store=store, quota=QUOTA, prices=PRICES, api_key="k")
    with pytest.raises(ContractError):
        ProviderClient(**common, generation=GENERATION, transport=GroqTransport())
    with pytest.raises(ContractError):
        ProviderClient(**common, generation=GenerationConfig(), transport=InceptionTransport())
    assert isinstance(ProviderClient(**common, generation=GENERATION).transport, InceptionTransport)
    assert type(ProviderClient(**common).transport) is GroqTransport


def test_groq_transport_identity_is_unchanged():
    transport = GroqTransport()
    assert transport.endpoint == ENDPOINT and transport.adapter == ADAPTER_VERSION
    assert transport.namespace.startswith("groq-live-httpx-")
    assert InceptionTransport().namespace.startswith("inception-live-httpx-")


def smoke_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts/inception_smoke.py"
    spec = importlib.util.spec_from_file_location("inception_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_script_is_bounded_and_sends_one_metered_call(tmp_path, monkeypatch):
    smoke = smoke_module()
    assert smoke.POLICY.billing_mode == "metered" and smoke.POLICY.daily_budget_microusd == 1000
    assert smoke.POLICY.rpd == 1 and smoke.RETRIES.max_attempts == 1
    _, fact, result, budget, scope = smoke.prepare()
    worst = smoke.PRICES.reserve_cost(result.diagnostics.estimate.estimated_tokens, 256)
    assert 0 < worst <= smoke.POLICY.daily_budget_microusd
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                **body(),
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": fact["expected"]},
                    }
                ],
            },
        )

    client = ProviderClient(
        store=RuntimeStore(tmp_path / "ledger.sqlite"),
        quota=smoke.POLICY,
        prices=smoke.PRICES,
        api_key="TEST_ONLY_KEY",
        generation=smoke.GENERATION,
        retries=smoke.RETRIES,
        transport=InceptionTransport(http_transport=httpx.MockTransport(handler)),
    )
    outcome = asyncio.run(smoke.send(client, result, budget, scope))
    assert outcome.status == "success" and len(calls) == 1 and outcome.new_cost_microusd > 0
    again = asyncio.run(smoke.send(client, result, budget, scope))
    assert again.status == "error" and len(calls) == 1  # Daily request cap of one.


def test_smoke_key_reader_reads_only_its_line(tmp_path):
    smoke = smoke_module()
    env = tmp_path / ".env"
    env.write_text("GROQ_API_KEY=g\nINCEPTION_API_KEY=sk_test-only\nTESTPYPI_TOKEN=p\n")
    env.chmod(0o600)
    assert smoke.inception_key(env) == "sk_test-only"
    env.write_text("GROQ_API_KEY=g\n")
    with pytest.raises(ValueError, match="never displayed"):
        smoke.inception_key(env)


def test_null_content_stop_reply_is_a_certain_empty_response(tmp_path):
    # Shape seen live in D119 stage B: content null, finish "stop", no tool calls.
    raw = body()
    raw["choices"][0]["message"] = {
        "role": "assistant",
        "content": None,
        "reasoning_details": [],
        "tool_call_id": None,
        "tool_calls": None,
    }
    result = call(provider(tmp_path, lambda request: httpx.Response(200, json=raw)))
    assert result.status == "error" and result.error_code == "empty_response"
    assert result.completion is None and result.warning is None
    assert result.new_cost_microusd == 7  # 40 x 0.10 + 6 x 0.35 = 6.1, rounded up
