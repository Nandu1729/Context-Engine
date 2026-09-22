"""C01 contracts and admission tests, including adversarial boundaries."""

import ast
import json
import math
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import tiktoken
from hypothesis import given
from hypothesis import strategies as st

from context_engine.budget import plan_budget, validate_request
from context_engine.cli import demo_request
from context_engine.config import CONFIG_DIRECTORY, BudgetConfig, Settings, TokenizerConfig
from context_engine.context import ContextCarrier, LayerDiagnostic
from context_engine.errors import (
    ConfigurationError,
    ContractError,
    LayerAllocationError,
    PromptTooLarge,
    RequiredContextTooLarge,
    TokenizerUnavailable,
)
from context_engine.models import (
    BlockKind,
    ChatRequest,
    Chunk,
    ContextBlock,
    KeyedPins,
    Message,
    Pin,
    Role,
    Scope,
    SourceRef,
    ToolCall,
    ToolDefinition,
    Turn,
)
from context_engine.tokens import CanonicalChatSerializer, TiktokenCounter, TokenEstimate

SCOPE = Scope("tenant-a", "session-a")
NOW = datetime(2026, 9, 7, tzinfo=UTC)
PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def counter():
    return TiktokenCounter()


@pytest.mark.parametrize(
    "name,value",
    [
        ("input_cap", -1),
        ("input_cap", 0),
        ("input_cap", True),
        ("input_cap", 900.0),
        ("model_capacity", -1),
        ("completion_reservation", 0),
        ("completion_reservation", 131072),
        ("retrieval_reserve", -1),
        ("summary_reserve", False),
        ("provider_input_cap", 0),
    ],
)
def test_invalid_budget_values_fail(name, value):
    with pytest.raises(ConfigurationError):
        BudgetConfig(**{name: value})


@pytest.mark.parametrize("factor", [0, 0.99, float("nan"), float("inf"), True, "1.07"])
def test_invalid_calibration_fails(factor):
    with pytest.raises(ConfigurationError):
        TokenizerConfig(calibration_factor=factor)


def test_output_reservation_and_per_request_cap_are_independent():
    config = BudgetConfig(
        input_cap=1000, model_capacity=900, completion_reservation=200, provider_input_cap=600
    )
    assert config.input_allowance == 600
    assert replace(config, provider_input_cap=None).input_allowance == 700
    assert replace(config, model_capacity=2000, provider_input_cap=None).input_allowance == 1000


def test_config_ignores_quota_as_context_limit_and_does_not_reveal_bad_values():
    assert Settings.from_env({"TPM": "1", "GROQ_API_KEY": "private-key"}).budget.input_cap == 3000
    with pytest.raises(ConfigurationError) as caught:
        Settings.from_env({"CONTEXT_BUDGET_TOKENS": "secret-value"})
    assert "secret-value" not in json.dumps(caught.value.to_dict())
    with pytest.raises(ConfigurationError):
        Settings.from_env({"TOKENIZER_FUDGE": "nan"})


def test_config_paths_are_independent_of_cwd(tmp_path, monkeypatch):
    first = Settings.from_env({"CONTEXT_OUTPUT_DIR": "run-output"})
    monkeypatch.chdir(tmp_path)
    second = Settings.from_env({"CONTEXT_OUTPUT_DIR": "run-output"})
    assert first.output_dir == second.output_dir == CONFIG_DIRECTORY / "run-output"
    assert Settings(output_dir=tmp_path).output_dir == tmp_path.resolve()
    assert not (CONFIG_DIRECTORY / "run-output").exists()  # Configuration performs no writes.


def test_originals_are_deeply_immutable_and_working_copy_is_separate():
    original = Message("m1", Role.USER, "head important middle tail")
    supplied = [original]
    turn = Turn("t1", SCOPE, supplied, timestamp=NOW)
    supplied.clear()
    assert turn.messages == (original,)
    with pytest.raises(FrozenInstanceError):
        original.content = "changed"
    working = replace(turn, messages=(replace(original, content="head … tail"),))
    carrier = ContextCarrier(
        SCOPE,
        (turn,),
        (working,),
        KeyedPins(SCOPE),
        Message("question", Role.USER, "What was in the middle?"),
    )
    assert carrier.original_turns[0].messages[0].content == "head important middle tail"
    assert turn.content_hash != working.content_hash
    updated = replace(carrier, diagnostics=(LayerDiagnostic("CAP", "message_capped", ("t1",)),))
    assert carrier.diagnostics == ()
    assert updated.diagnostics[0].changed_turn_ids == ("t1",)
    with pytest.raises(ContractError):
        replace(carrier, diagnostics=(LayerDiagnostic("CAP", "message_capped", ("missing",)),))


def test_source_offsets_validate_unicode_revision_scope_hash_and_chunk():
    message = Message("m1", Role.TOOL, "prefix తెలుగు 🌍 suffix", tool_call_id="call1")
    turn = Turn("t1", SCOPE, (message,), timestamp=NOW)
    start = message.content.index("తెలుగు")
    end = message.content.index(" suffix")
    source = SourceRef(SCOPE, "t1", "m1", 1, start, end, message.content_hash)
    chunk = Chunk("chunk1", source, "తెలుగు 🌍", "codepoints-v1")
    chunk.validate_source(turn)
    assert source.extract(turn) == "తెలుగు 🌍"
    for changed in (
        replace(turn, revision=2),
        replace(turn, scope=Scope("other", "session-a")),
        replace(turn, messages=(replace(message, content="changed"),)),
    ):
        with pytest.raises(ContractError):
            source.extract(changed)
    with pytest.raises(ContractError):
        replace(source, end=len(message.content) + 1).extract(turn)
    with pytest.raises(ContractError):
        replace(chunk, content="x" * len(chunk.content)).validate_source(turn)


def test_keyed_pins_reject_conflicts_and_track_expiry():
    pin = Pin(
        SCOPE,
        "database",
        "PostgreSQL",
        "application",
        effective_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    with pytest.raises(ContractError):
        KeyedPins(SCOPE, (pin, replace(pin, value="MySQL", revision=2)))
    assert pin.is_active(NOW)
    assert not pin.is_active(NOW - timedelta(seconds=1))
    assert not pin.is_active(NOW + timedelta(days=1))
    with pytest.raises(ContractError):
        pin.is_active(datetime(2026, 9, 7))
    with pytest.raises(ContractError):
        KeyedPins(Scope("other", "session-a"), (pin,))
    pins = KeyedPins(SCOPE, (replace(pin, key="z"), pin))
    assert [p.key for p in pins.pins] == ["database", "z"]


def test_carrier_rejects_scope_drift_identity_loss_and_duplicate_question():
    message = Message("m1", Role.USER, "original")
    turn = Turn("t1", SCOPE, (message,), timestamp=NOW)
    carrier = ContextCarrier(
        SCOPE, (turn,), (turn,), KeyedPins(SCOPE), Message("q1", Role.USER, "question")
    )
    for changes in (
        {"working_turns": ()},
        {"question": message},
        {"original_turns": (replace(turn, scope=Scope("b", "s")),)},
        {"working_turns": (replace(turn, revision=2),)},
        {"working_turns": (replace(turn, messages=(replace(message, role=Role.ASSISTANT),)),)},
    ):
        with pytest.raises(ContractError):
            replace(carrier, **changes)
    assert ContextBlock(BlockKind.PINNED, "data").required
    assert not ContextBlock(BlockKind.RETRIEVED, "evidence").required


def tool_request():
    calls = (ToolCall("call1", "lookup", '{"id":"42"}'), ToolCall("call2", "lookup", '{"id":"43"}'))
    tools = (ToolDefinition("lookup", "Look up an incident", '{"type":"object"}'),)
    return ChatRequest(
        (
            Message("m1", Role.USER, "Look up both incidents"),
            Message("m2", Role.ASSISTANT, "", tool_calls=calls),
            Message("m3", Role.TOOL, "result 43", tool_call_id="call2"),
            Message("m4", Role.TOOL, "result 42", tool_call_id="call1"),
        ),
        tools,
    )


def test_tool_calls_preserve_pairing_and_detach_wire_objects():
    original_arguments = '{  "id": "42"  }'
    original_call = ToolCall("original", "lookup", original_arguments)
    assert original_call.arguments_json == original_arguments
    assert original_call.to_wire()["function"]["arguments"] == original_arguments
    request = tool_request()
    wire = request.to_wire()
    wire["tools"][0]["function"]["parameters"]["injected"] = True
    assert "injected" not in request.to_wire()["tools"][0]["function"]["parameters"]
    for messages in (
        request.messages[:-1],
        request.messages[2:],
        (*request.messages, replace(request.messages[-1], message_id="duplicate")),
        (request.messages[1], request.messages[0], *request.messages[2:]),
    ):
        with pytest.raises(ContractError):
            ChatRequest(messages)
    with pytest.raises(ContractError):
        Message("m", Role.USER, "", tool_calls=request.messages[1].tool_calls)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', "[]", '{"x":"\ud800"}'])
def test_unsafe_or_ambiguous_tool_json_is_rejected(raw):
    with pytest.raises(ContractError):
        ToolCall("call1", "lookup", raw)


def test_full_serialization_counts_roles_tools_arguments_and_calibration(counter):
    request = tool_request()
    encoded = tiktoken.get_encoding("o200k_harmony")
    wire = CanonicalChatSerializer().serialize(request)
    result = counter.count_request(request)
    assert result.serialized_tokens == len(encoded.encode_ordinary(wire))
    assert result.estimated_tokens == math.ceil(result.serialized_tokens * 1.07)
    assert result.tool_schema_tokens > 0
    assert result.serialized_tokens > result.message_content_tokens
    assert (
        result.message_content_tokens
        + result.tool_schema_tokens
        + result.serialization_delta_tokens
        == result.serialized_tokens
    )
    assert '"arguments"' in wire and '"tool_call_id"' in wire and '"role"' in wire
    assert '"message_id"' not in wire
    assert result.to_dict()["provider_accounting_verified"] is False


def test_adapter_serializer_and_overhead_are_used():
    class TestAdapter:
        name = "test-template-v1"

        def serialize(self, request):
            return "adapter-prefix\n" + CanonicalChatSerializer().serialize(request) + "\nreply:"

    counter = TiktokenCounter(TokenizerConfig(adapter_overhead_tokens=17), TestAdapter())
    result = counter.count_request(demo_request())
    assert result.serializer_name == "test-template-v1"
    assert result.estimated_tokens == math.ceil((result.serialized_tokens + 17) * 1.07)
    changed = counter.count_request(demo_request("Database = MySQL"))
    assert result.request_fingerprint != changed.request_fingerprint


@pytest.mark.parametrize(
    "content", ["తెలుగు", "العربية", "👩🏽‍💻 🌍", "", "<|endoftext|><|im_start|>"]
)
def test_unicode_and_literal_control_token_text(counter, content):
    assert counter.count_text(content) == len(
        tiktoken.get_encoding("o200k_harmony").encode_ordinary(content)
    )
    request = ChatRequest((Message("m", Role.USER, content),))
    assert counter.count_request(request).estimated_tokens > 0


def test_unpaired_surrogate_and_missing_tokenizer_fail_cleanly(counter, monkeypatch):
    with pytest.raises(ContractError):
        counter.count_text("\ud800")
    with pytest.raises(TokenizerUnavailable):
        TiktokenCounter(TokenizerConfig(encoding_name="does-not-exist"))

    def unavailable(_):
        raise OSError("secret-transport-detail")

    monkeypatch.setattr(tiktoken, "get_encoding", unavailable)
    with pytest.raises(TokenizerUnavailable) as caught:
        TiktokenCounter()
    assert "secret-transport-detail" not in json.dumps(caught.value.to_dict())


def test_required_overflow_including_long_question_is_content_free(counter):
    request = demo_request("private-pin " * 1000)
    before = request.to_wire()
    config = BudgetConfig(input_cap=900)
    with pytest.raises(RequiredContextTooLarge) as caught:
        plan_budget(required_request=request, config=config, counter=counter)
    error = caught.value.to_dict()
    assert error["details"]["overflow_tokens"] > 0
    assert "private-pin" not in json.dumps(error)
    assert request.to_wire() == before
    long_question = ChatRequest((Message("q", Role.USER, "question " * 2000),))
    with pytest.raises(RequiredContextTooLarge):
        plan_budget(required_request=long_question, config=config, counter=counter)


def test_tool_schema_can_cause_overflow_even_when_question_fits(counter):
    request = demo_request()
    config = BudgetConfig(input_cap=900)
    plan_budget(required_request=request, config=config, counter=counter)
    huge = ToolDefinition("lookup", "description " * 2000, '{"type":"object"}')
    with pytest.raises(RequiredContextTooLarge):
        plan_budget(
            required_request=replace(request, tools=(huge,)), config=config, counter=counter
        )


def test_exact_boundary_empty_optional_allocations_and_final_recount(counter):
    request = demo_request()
    exact = counter.count_request(request).estimated_tokens
    config = BudgetConfig(input_cap=exact, retrieval_reserve=0, summary_reserve=0)
    plan = plan_budget(required_request=request, config=config, counter=counter)
    assert plan.window_tokens == 0
    assert (
        validate_request(request=request, config=config, counter=counter).estimated_tokens == exact
    )
    with pytest.raises(PromptTooLarge):
        validate_request(
            request=request, config=replace(config, input_cap=exact - 1), counter=counter
        )
    with pytest.raises(LayerAllocationError):
        plan_budget(
            required_request=request, config=replace(config, summary_reserve=1), counter=counter
        )


@given(
    required=st.integers(0, 10000),
    spare=st.integers(0, 10000),
    retrieval=st.integers(0, 500),
    summary=st.integers(0, 500),
)
def test_budget_conservation_for_generated_allocations(required, spare, retrieval, summary):
    class FixedCounter:
        def count_request(self, request):
            return TokenEstimate(required, required, 0, 0, 1.0, "test", "1", "test", "hash")

    allowance = max(1, required + spare + retrieval + summary)
    config = BudgetConfig(
        input_cap=allowance,
        model_capacity=allowance + 256,
        retrieval_reserve=retrieval,
        summary_reserve=summary,
    )
    plan = plan_budget(required_request=demo_request(), config=config, counter=FixedCounter())
    assert (
        plan.required_estimate.estimated_tokens
        + plan.retrieval_tokens
        + plan.summary_tokens
        + plan.window_tokens
        == allowance
    )
    assert plan.window_tokens >= spare


def test_large_finite_calibration_has_no_float_overflow(counter):
    estimate = counter.count_request(demo_request())
    assert replace(estimate, calibration_factor=1e308).estimated_tokens >= 10**308


@pytest.mark.parametrize("directory", [None, 42, "bad\x00path"])
def test_invalid_output_directory_is_a_structured_error(directory):
    with pytest.raises(ConfigurationError):
        Settings(output_dir=directory)


def test_package_and_configuration_dependency_boundaries():
    package = PROJECT / "src/context_engine"
    for path in package.rglob("*.py"):
        if "evaluation" in path.relative_to(package).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        assert not any(
            "groq" in name
            or (("benchmark" in name or "evaluation" in name) and path.name != "cli.py")
            for name in imported
        )
        if (
            not {"providers", "service"}.intersection(path.relative_to(package).parts)
            and path.name != "cli.py"
        ):
            assert not any(
                any(
                    boundary in name
                    for boundary in ("providers", "service", "httpx", "fastapi", "jwt", "uvicorn")
                )
                for name in imported
            )
        if path.name == "config.py":
            assert not set(imported) & {"models", "tokens", "budget", "context", "layers"}


def test_installed_cli_from_other_directory_and_no_secret_output(tmp_path):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            (
                "CONTEXT_",
                "TOKENIZER_",
                "MODEL_CONTEXT_",
                "MAX_COMPLETION_",
                "RETRIEVAL_RESERVE_",
                "SUMMARY_RESERVE_",
                "PROVIDER_INPUT_CAP_",
                "ADAPTER_OVERHEAD_",
            )
        )
    }
    env["GROQ_API_KEY"] = "private-key-not-for-output"
    check = subprocess.run(
        [sys.executable, "-m", "context_engine", "check"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert check.stdout == "deps ok\n"
    demo = subprocess.run(
        [sys.executable, "-m", "context_engine", "demo-budget"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "required_context_too_large" in demo.stdout
    assert env["GROQ_API_KEY"] not in demo.stdout + demo.stderr


def test_import_is_lazy_and_has_no_tokenizer_initialization(tmp_path):
    code = "import sys; import context_engine; assert 'tiktoken' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True)
