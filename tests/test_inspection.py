"""Offline CLI input, content redaction and explicit no-overwrite exports."""

import json
import os
import subprocess
import sys
from copy import deepcopy

import pytest

from context_engine.config import Settings
from context_engine.errors import ContextEngineError, InspectionError
from context_engine.inspection import load_job, parse_job, save_inspection


def payload():
    return {
        "schema_version": 1,
        "scope": {"tenant_id": "synthetic", "session_id": "inspection"},
        "system": "PRIVATE_INSTRUCTIONS",
        "question": "Which database?",
        "at": "2026-09-07T00:00:00+00:00",
        "history": [
            {
                "turn_id": "t1",
                "messages": [
                    {"message_id": "m1", "role": "user", "content": "PRIVATE_HISTORY PostgreSQL"},
                ],
            }
        ],
        "pins": [{"key": "database", "value": "PostgreSQL", "origin": "application"}],
        "tools": [{"name": "lookup", "parameters": {"type": "object"}}],
        "budget": {"input_cap": 900},
    }


def test_parse_job_is_detached_and_preserves_full_inputs():
    raw = payload()
    original = deepcopy(raw)
    job = parse_job(raw, Settings.from_env({}))
    result = job.run()
    assert raw == original
    raw["history"][0]["messages"][0]["content"] = "mutation"
    assert job.arguments["history"][0].messages[0].content == "PRIVATE_HISTORY PostgreSQL"
    assert result.diagnostics.input_allowance == 900
    assert result.request.tools[0].name == "lookup"
    assert "PRIVATE" not in json.dumps(result.to_dict())
    assert "PRIVATE_HISTORY" in json.dumps(result.to_dict(include_content=True))
    assert job.run(input_cap=1000).diagnostics.input_allowance == 1000


def test_parser_preserves_tool_calls_and_frozen_summary():
    raw = payload()
    raw["history"][0]["messages"] = [
        {
            "message_id": "a",
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"call_id": "c", "name": "lookup", "arguments_json": '{ "q": "db" }'},
            ],
        },
        {"message_id": "b", "role": "tool", "content": "PostgreSQL", "tool_call_id": "c"},
    ]
    raw["summary"] = {
        "content": "Earlier database discussion",
        "covered_turn_ids": ["t1"],
        "policy_version": "synthetic-v1",
        "created_at": raw["at"],
    }
    job = parse_job(raw, Settings.from_env({}))
    turn = job.arguments["history"][0]
    assert turn.messages[0].tool_calls[0].arguments_json == '{ "q": "db" }'
    policy = job.arguments["summary_policy"]
    assert policy.snapshot.matches((turn,), turn.scope, job.arguments["at"])
    result = job.run()
    assert not result.diagnostics.to_dict()["summary_used"]  # No omitted history.


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("question", {}),
        ("at", "not a time"),
        ("at", 3),
        ("at", "2026-09-07"),
        ("scope", {"tenant_id": "missing session"}),
        ("history", {}),
        ("history", [{"turn_id": "missing messages"}]),
        ("pins", [{"key": "x", "value": "y", "origin": "app", "unknown": True}]),
        ("tools", [{"name": "lookup", "parameters": []}]),
        ("budget", {"input_cap": "900"}),
        ("cap", {"unsupported": 1}),
        ("retrieval", {"top_k": 0}),
        ("tokenizer", {"calibration_factor": 0}),
        (
            "summary",
            {
                "content": "x",
                "covered_turn_ids": ["missing"],
                "policy_version": "v1",
                "created_at": "2026-09-07T00:00:00Z",
            },
        ),
        (
            "summary",
            {
                "content": "x",
                "covered_turn_ids": ["t1", "t1"],
                "policy_version": "v1",
                "created_at": "2026-09-07T00:00:00Z",
            },
        ),
    ],
)
def test_malformed_fields_return_typed_errors(tmp_path, field, value):
    raw = payload()
    raw[field] = value
    path = tmp_path / "input.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ContextEngineError):
        load_job(path, Settings.from_env({})).run()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":1}',
        b'{"n":NaN}',
        b'{"n":Infinity}',
        b'{"secret":"PRIVATE',
        b"\xff",
        b"[]",
        b"null",
        b'{"scope":{}}',
        b"[" * 1500 + b"]" * 1500,
    ],
)
def test_bad_json_is_rejected_without_raw_content(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    with pytest.raises(InspectionError) as caught:
        load_job(path, Settings.from_env({}))
    assert "PRIVATE" not in json.dumps(caught.value.to_dict())


def test_input_size_turn_limit_and_missing_file(tmp_path, monkeypatch):
    import context_engine.inspection as module

    path = tmp_path / "input.json"
    with pytest.raises(InspectionError):
        load_job(path, Settings.from_env({}))
    path.write_text(json.dumps(payload()), encoding="utf-8")
    monkeypatch.setattr(module, "MAX_INSPECTION_BYTES", 10)
    with pytest.raises(InspectionError, match="byte limit"):
        load_job(path, Settings.from_env({}))
    monkeypatch.setattr(module, "MAX_INSPECTION_TURNS", 0)
    with pytest.raises(InspectionError, match="turn limit"):
        parse_job(payload(), Settings.from_env({}))


def test_exports_never_overwrite_and_fail_safely(tmp_path):
    path = tmp_path / "nested" / "inspection.json"
    original = {"content_included": False, "text": "తెలుగు"}
    save_inspection(path, original)
    assert json.loads(path.read_text(encoding="utf-8")) == original
    with pytest.raises(InspectionError, match="already exists"):
        save_inspection(path, {"changed": True})
    assert json.loads(path.read_text(encoding="utf-8")) == original
    with pytest.raises(InspectionError):
        save_inspection(path / "child.json", {})


def run_cli(tmp_path, *arguments):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            (
                "CONTEXT_",
                "TOKENIZER_",
                "MODEL_CONTEXT_",
                "MAX_COMPLETION_",
                "RETRIEVAL_",
                "SUMMARY_RESERVE_",
                "PROVIDER_INPUT_CAP_",
                "ADAPTER_OVERHEAD_",
                "CAP_",
                "BM25_",
            )
        )
    }
    env["GROQ_API_KEY"] = "PRIVATE_TEST_KEY"
    return subprocess.run(
        [sys.executable, "-m", "context_engine", *arguments],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )


@pytest.mark.parametrize("command", ["inspect", "probe"])
def test_offline_cli_from_other_cwd_and_synthetic_demo(tmp_path, command):
    completed = run_cli(tmp_path, command)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["inference_calls"] == 0 and result["synthetic_input"]
    assert result["mode"] == ("offline_probe" if command == "probe" else "offline_inspection")
    assert "request" not in result and "answer" not in result
    assert result["diagnostics"]["estimate"]["estimated_tokens"] == 637
    assert "PRIVATE_TEST_KEY" not in completed.stdout + completed.stderr


def test_cli_config_inspect_opt_in_export_and_structured_failure(tmp_path):
    configured = run_cli(tmp_path, "config")
    assert configured.returncode == 0
    assert set(json.loads(configured.stdout)) == {"budget", "tokenizer", "cap", "retrieval"}
    assert "PRIVATE_TEST_KEY" not in configured.stdout + configured.stderr
    source, output = tmp_path / "source.json", tmp_path / "result.json"
    source.write_text(json.dumps(payload()), encoding="utf-8")
    completed = run_cli(
        tmp_path,
        "inspect",
        "--input",
        str(source),
        "--show-content",
        "--budget",
        "1000",
        "--output",
        str(output),
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert result["content_included"] and not result["synthetic_input"]
    assert result["diagnostics"]["input_allowance"] == 1000
    assert "PRIVATE_HISTORY" in completed.stdout
    before = output.read_bytes()
    duplicate = run_cli(tmp_path, "inspect", "--output", str(output))
    assert duplicate.returncode == 1 and not duplicate.stdout
    assert json.loads(duplicate.stderr)["code"] == "invalid_inspection_input"
    assert before == output.read_bytes()
    raw = payload()
    raw["question"] = "PRIVATE_QUESTION " * 1000
    source.write_text(json.dumps(raw), encoding="utf-8")
    impossible = run_cli(tmp_path, "inspect", "--input", str(source))
    assert impossible.returncode == 1 and not impossible.stdout
    assert json.loads(impossible.stderr)["code"] == "required_context_too_large"
    assert "PRIVATE_QUESTION" not in impossible.stderr
