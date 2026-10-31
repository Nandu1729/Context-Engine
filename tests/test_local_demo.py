"""Local milestone smoke; synthetic data only, no provider or owner corpus."""

import json
from unittest.mock import patch

import pytest

from context_engine.errors import ContractError
from context_engine.tokens import TiktokenCounter
from scripts import local_demo


@pytest.fixture(scope="module")
def report():
    # Public tokenizer assets may need initialization on a clean machine.
    TiktokenCounter()
    return local_demo.run()


def test_real_sdk_and_temporary_lifecycle(report):
    assert report["status"] == "PASS" and report["milestone"] == "LOCAL_DEMO_ONLY"
    assert report["sdk"]["source_turns"] == 12
    assert report["sdk"]["estimated_input_tokens"] == 838
    assert report["sdk"]["input_allowance"] == 900
    assert report["sdk"]["sample_cap_tokens"] == 80
    assert len(report["sdk"]["checks"]) == 6 and all(report["sdk"]["checks"].values())
    assert len(report["memory"]["checks"]) == 9 and all(report["memory"]["checks"].values())


def test_report_does_not_claim_answers_or_include_content(report):
    assert report["inference_calls"] == 0
    assert report["answer_quality"] == "NOT_EVALUATED"
    assert not report["enterprise_approved"] and not report["content_included"]
    serialized = json.dumps(report)
    assert "checkout-v41" not in serialized and "shard-19" not in serialized
    assert "UNTRUSTED SAMPLE LOG" not in serialized


def test_cli_metadata_output_and_plain_language(report, tmp_path, capsys):
    output = tmp_path / "new" / "report.json"
    with patch.object(local_demo, "run", return_value=report):
        assert local_demo.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text()) == report
    assert "No AI answer generated" in capsys.readouterr().out


def test_existing_output_rejected_before_work(tmp_path):
    output = tmp_path / "old.json"
    output.write_text("preserved")
    with patch.object(local_demo, "run") as execute:
        with pytest.raises(SystemExit):
            local_demo.main(["--output", str(output)])
        execute.assert_not_called()
    assert output.read_text() == "preserved"


def test_output_creation_race_preserves_other_writer(report, tmp_path):
    output = tmp_path / "race.json"

    def race():
        output.write_text("other writer")
        return report

    with patch.object(local_demo, "run", side_effect=race):
        assert local_demo.main(["--output", str(output)]) == 1
    assert output.read_text() == "other writer"


def test_errors_are_redacted(capsys):
    with patch.object(local_demo, "run", side_effect=ContractError("PRIVATE_DATA")):
        assert local_demo.main([]) == 1
    assert "PRIVATE_DATA" not in capsys.readouterr().out


def test_no_output_option_creates_no_report(report, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch.object(local_demo, "run", return_value=report):
        assert local_demo.main([]) == 0
    assert list(tmp_path.iterdir()) == []


def test_failed_lifecycle_cannot_be_reported_as_pass(report):
    with patch.object(local_demo, "memory_demo", return_value={"status": "FAIL", "checks": {}}):
        with pytest.raises(ContractError, match="lifecycle"):
            local_demo.run()
