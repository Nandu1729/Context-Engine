"""Exercise the copyable SDK example without model calls or owner data."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from context_engine.errors import ContractError
from context_engine.tokens import TiktokenCounter
from examples import sdk_quickstart as example
from scripts.incident_demo import offline_network


@pytest.fixture(autouse=True)
def cached_offline():
    TiktokenCounter()  # Public vocabulary initialization, before socket denial.
    with offline_network():
        yield


def test_real_sdk_preserves_sample_evidence_policy_and_question():
    result = example.prepare_context()
    assert result.diagnostics.remaining_tokens >= 0
    assert result.diagnostics.input_allowance == 900
    assert result.messages[0]["content"] == example.SYSTEM
    assert result.messages[-1]["content"] == example.QUESTION
    content = json.dumps(result.messages)
    for fact in ("checkout-v41", "pool is now 20", "Root cause is not confirmed"):
        assert fact in content
    assert len(result.diagnostics.kept_turn_ids) == 3


def test_question_override_and_fresh_wire_output():
    question = "Has the root cause been confirmed?"
    result = example.prepare_context(question)
    messages = result.messages
    messages[-1]["content"] = "modified outside the SDK"
    assert result.messages[-1]["content"] == question
    assert example.prepare_context(question).messages == result.messages


def test_default_console_has_no_content_or_local_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert example.main([]) == 0
    output = capsys.readouterr().out
    assert "CONTEXT READY" in output and "not an AI answer" in output
    assert "checkout-v41" not in output and example.QUESTION not in output
    assert list(tmp_path.iterdir()) == []


def test_explicit_context_display_and_custom_question(capsys):
    assert example.main(["--show-context", "--question", "Which version is active?"]) == 0
    output = capsys.readouterr().out
    assert "checkout-v41" in output and "Which version is active?" in output


def test_error_does_not_echo_sensitive_details(capsys):
    with patch.object(example, "prepare_context", side_effect=ContractError("PRIVATE_DATA")):
        assert example.main([]) == 1
    output = capsys.readouterr().out
    assert "PRIVATE_DATA" not in output and "failed" in output


def test_question_over_budget_fails_without_echo(capsys):
    assert example.main(["--question", "PRIVATE_DATA " * 2000]) == 1
    output = capsys.readouterr().out
    assert "CONTEXT READY" not in output and "PRIVATE_DATA" not in output


def test_standalone_entrypoint_from_other_directory(tmp_path):
    # The copied example needs only the installed package, not repository scripts.
    source = Path(example.__file__).read_text(encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import socket\n"
            "def denied(*a, **kw): raise RuntimeError('Network disabled')\n"
            "socket.socket.connect = denied\nsocket.socket.connect_ex = denied\n"
            "socket.create_connection = denied\nsocket.getaddrinfo = denied\n" + source,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "CONTEXT READY" in completed.stdout
    assert list(tmp_path.iterdir()) == []
