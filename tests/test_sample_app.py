"""Sample application connection and safe terminal behavior."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import sample_app
from context_engine.errors import ContractError
from context_engine.tokens import TiktokenCounter
from scripts.incident_demo import offline_network


@pytest.fixture(autouse=True)
def offline():
    TiktokenCounter()
    with offline_network():
        yield


def test_interactive_connection_displays_context_on_request(capsys):
    with patch("builtins.input", return_value="Which version did we roll back to?"):
        assert sample_app.main(["--show-context"]) == 0
    output = capsys.readouterr().out
    assert "CONNECTED" in output and "checkout-v41" in output
    assert "Which version did we roll back to?" in output
    assert "not an AI answer" in output


def test_noninteractive_default_is_content_free_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("builtins.input", side_effect=AssertionError("Must not prompt")):
        assert sample_app.main(["--question", "Has the root cause been confirmed?"]) == 0
    output = capsys.readouterr().out
    assert "CONNECTED" in output and "checkout-v41" not in output
    assert "Has the root cause" not in output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_cancel_is_clean(error, capsys):
    with patch("builtins.input", side_effect=error):
        assert sample_app.main([]) == 130
    assert "Cancelled" in capsys.readouterr().out


def test_blank_question_never_calls_engine(capsys):
    with patch.object(sample_app, "prepare_context") as prepare:
        assert sample_app.main(["--question", "  "]) == 1
        prepare.assert_not_called()
    assert "CONNECTED" not in capsys.readouterr().out


def test_errors_are_redacted(capsys):
    with patch.object(sample_app, "prepare_context", side_effect=ContractError("PRIVATE_DATA")):
        assert sample_app.main(["--question", "PRIVATE_QUESTION"]) == 1
    output = capsys.readouterr().out
    assert "PRIVATE_DATA" not in output and "PRIVATE_QUESTION" not in output
    assert "CONNECTED" not in output


@pytest.fixture
def converted_input(tmp_path):
    path = tmp_path / "input-baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": {"tenant_id": "sample", "session_id": "development"},
                "system": "Use evidence only.",
                "question": "PRIVATE_QUESTION: Which database?",
                "at": "2026-10-02T00:00:00+00:00",
                "history": [
                    {
                        "turn_id": "t1",
                        "messages": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "PRIVATE_HISTORY PostgreSQL",
                            }
                        ],
                    }
                ],
                "budget": {"input_cap": 1200, "summary_reserve": 0},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_converted_input_uses_saved_question_and_budget_without_mutation(converted_input, capsys):
    before = converted_input.read_bytes()
    with patch("builtins.input", side_effect=AssertionError("Must not prompt")):
        assert sample_app.main(["--input", str(converted_input), "--show-context"]) == 0
    output = capsys.readouterr().out
    assert "PRIVATE_QUESTION" in output and "PRIVATE_HISTORY" in output
    assert "/1200" in output and "Loaded source turns: 1" in output
    assert converted_input.read_bytes() == before
    assert list(converted_input.parent.iterdir()) == [converted_input]


def test_longmemeval_shortcut_reads_only_input_and_defaults_to_no_content(
    converted_input,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(sample_app, "LONGMEMEVAL_INPUT", converted_input)
    original_open = Path.open
    opened = []

    def only_input(path, *args, **kwargs):
        assert path == converted_input, "Must not read a label, corpus or credential file"
        opened.append(path)
        return original_open(path, *args, **kwargs)

    with patch.object(Path, "open", only_input):
        assert sample_app.main(["--longmemeval"]) == 0
    assert opened == [converted_input]
    output = capsys.readouterr().out
    assert "CONNECTED" in output and "PRIVATE" not in output and "PostgreSQL" not in output


@pytest.mark.parametrize("field", ["answer", "has_answer", "answer_session_ids"])
def test_ground_truth_fields_rejected_before_assembly(converted_input, field, capsys):
    payload = json.loads(converted_input.read_text())
    payload[field] = "PRIVATE_LABEL"
    converted_input.write_text(json.dumps(payload))
    with patch("context_engine.inspection.assemble_context") as assemble:
        assert sample_app.main(["--input", str(converted_input)]) == 1
        assemble.assert_not_called()
    output = capsys.readouterr().out
    assert "PRIVATE_LABEL" not in output and "CONNECTED" not in output


@pytest.mark.parametrize("raw", ["[]", '{"answer":"PRIVATE_LABEL"}', "{bad"])
def test_raw_corpus_labels_and_invalid_json_rejected(tmp_path, raw, capsys):
    path = tmp_path / "invalid.json"
    path.write_text(raw)
    assert sample_app.main(["--input", str(path)]) == 1
    output = capsys.readouterr().out
    assert "CONNECTED" not in output and "PRIVATE_LABEL" not in output


def test_missing_conversion_does_not_download(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sample_app, "LONGMEMEVAL_INPUT", tmp_path / "missing.json")
    assert sample_app.main(["--longmemeval"]) == 1
    output = capsys.readouterr().out
    assert "No download attempted" in output and "CONNECTED" not in output


@pytest.mark.parametrize(
    "args",
    [
        ["--longmemeval", "--input", "input.json"],
        ["--longmemeval", "--question", "PRIVATE_QUESTION"],
    ],
)
def test_conflicting_sources_or_question_fail_before_file_read(args):
    with patch.object(sample_app, "load_job") as load:
        with pytest.raises(SystemExit) as error:
            sample_app.main(args)
        assert error.value.code == 2
        load.assert_not_called()


def test_dataset_assembly_has_its_own_network_guard(converted_input, capsys):
    import socket

    # Detect regression even if the outer test-fixture guard would also block it.
    with patch("socket.create_connection") as connect:
        with patch.object(
            sample_app,
            "load_job",
            side_effect=lambda *a: socket.create_connection(("example.invalid", 443)),
        ):
            assert sample_app.main(["--input", str(converted_input)]) == 1
        connect.assert_not_called()
    assert "CONNECTED" not in capsys.readouterr().out
