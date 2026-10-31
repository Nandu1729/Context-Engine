"""Repository-only demo: real assembly, escaped content, explicit export and no inference."""

import importlib.util
import json
import socket
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest

from context_engine.config import CapConfig, RetrievalConfig, Settings
from context_engine.errors import ContextEngineError
from context_engine.inspection import load_job

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("incident_demo", ROOT / "scripts/incident_demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_sample_runs_real_engine_with_budget_pressure():
    job = load_job(demo.SAMPLE, Settings())
    original = job.arguments["history"]
    result = job.run()
    assert result.diagnostics.estimate.estimated_tokens <= 900
    assert result.diagnostics.omitted_turn_ids and result.diagnostics.retrieved_turn_ids
    assert "t01" in result.diagnostics.retrieved_turn_ids
    assert "t09" in result.diagnostics.kept_turn_ids
    assert "checkout-v42" in str(result.messages)
    assert "checkout-v41" in str(result.messages)
    assert "checkout-v41" in original[8].messages[0].content
    assert job.arguments["history"] == original
    page = demo.build_report(show_content=True)
    assert page == demo.build_report(show_content=True)
    assert "SYNTHETIC SAMPLE" in page and "NOT_EVALUATED" in page
    assert "No model called" in page and "838" in page


@pytest.mark.parametrize("recover", [False, True])
def test_smaller_message_cap_does_not_imply_full_turn_retention(recover):
    job = load_job(demo.SAMPLE, Settings())
    retrieval = RetrievalConfig(recover_capped_window=recover)
    job = replace(
        job,
        arguments={**job.arguments, "cap_config": CapConfig(), "retrieval_config": retrieval},
    )
    result = job.run()
    assert "t09" in result.diagnostics.kept_turn_ids
    # A kept turn can still lose capped text; the default (recover) restores it as evidence.
    assert ("checkout-v41" in str(result.messages)) is recover
    assert ("t09" in result.diagnostics.retrieved_turn_ids) is recover
    assert "checkout-v41" in job.arguments["history"][8].messages[0].content


def test_content_hidden_by_default_including_custom_ids(tmp_path):
    data = json.loads(demo.SAMPLE.read_text())
    data["question"] = "PRIVATE QUESTION"
    data["history"][0]["turn_id"] = "PRIVATE TURN"
    data["system"] = "PRIVATE SYSTEM"
    data["history"][0]["messages"][0]["content"] = "PRIVATE CONTENT"
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    page = demo.build_report(path)
    assert "PRIVATE" not in page and "Content hidden" in page
    assert "PROVENANCE NOT VERIFIED" in page
    assert "SYNTHETIC SAMPLE" not in page
    shown = demo.build_report(path, show_content=True)
    assert "PRIVATE QUESTION" in shown and "PRIVATE CONTENT" in shown


def test_untrusted_html_is_escaped_and_page_has_no_active_resources():
    question = '<script>alert("x")</script><img src="https://invalid/"> & <b>text</b>'
    page = demo.build_report(question=question, show_content=True)
    assert "&lt;script&gt;" in page and "&lt;img" in page
    assert "SYNTHETIC SAMPLE" not in page

    class CheckTags(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in {"script", "iframe", "img", "object", "embed", "link"}
            assert not any(key.startswith("on") or key in {"src", "href"} for key, _ in attrs)

    CheckTags().feed(page)
    assert "default-src 'none'" in page


def test_question_budget_and_cwd_overrides(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page = demo.build_report(
        question="Is a final root cause recorded?", budget=1200, show_content=True
    )
    assert "Is a final root cause recorded?" in page and "1200" in page
    with pytest.raises(ContextEngineError):
        demo.build_report(budget=1)


def test_duplicate_keys_and_truth_fields_rejected(tmp_path):
    path = tmp_path / "input.json"
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ContextEngineError):
        demo.build_report(path)
    data = json.loads(demo.SAMPLE.read_text())
    data["ground_truth"] = "must remain separate"
    path.write_text(json.dumps(data))
    with pytest.raises(ContextEngineError):
        demo.build_report(path)


def test_python_network_blocked_and_restored():
    original = socket.create_connection
    with demo.offline_network():
        with pytest.raises(RuntimeError, match="Network disabled"):
            socket.create_connection(("example.invalid", 443))
        with pytest.raises(RuntimeError, match="Network disabled"):
            socket.getaddrinfo("example.invalid", 443)
        with socket.socket() as client:
            for method in (client.connect, client.connect_ex):
                with pytest.raises(RuntimeError, match="Network disabled"):
                    method(("127.0.0.1", 1))
    assert socket.create_connection is original


def test_cli_output_and_content_free_stdout(tmp_path, capsys):
    output = tmp_path / "new" / "index.html"
    assert demo.main(["--output", str(output), "--show-content"]) == 0
    assert "checkout-v42" in output.read_text()
    assert "checkout-v42" not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        demo.main(["--output", str(output)])
    assert "checkout-v42" in output.read_text()


def test_exclusive_creation_preserves_racing_writer(tmp_path, monkeypatch, capsys):
    output = tmp_path / "index.html"

    def race(*args, **kwargs):
        output.write_text("other writer")
        return "new report"

    monkeypatch.setattr(demo, "build_report", race)
    assert demo.main(["--output", str(output)]) == 1
    assert output.read_text() == "other writer"
    assert "other writer" not in capsys.readouterr().out


def test_failures_do_not_export_or_echo_input(tmp_path, monkeypatch, capsys):
    output = tmp_path / "index.html"

    def failure(*args, **kwargs):
        raise RuntimeError("PRIVATE ERROR BODY")

    monkeypatch.setattr(demo, "build_report", failure)
    assert demo.main(["--output", str(output)]) == 1
    assert not output.exists()
    assert "PRIVATE ERROR BODY" not in capsys.readouterr().out
