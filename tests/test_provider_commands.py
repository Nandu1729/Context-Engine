"""Command integration remains offline, including the explicit live-probe path."""

import json

import pytest

from context_engine.cli import main
from context_engine.providers.commands import SyntheticTransport, provider_demo
from context_engine.providers.transport import GroqTransport


def live_args(tmp_path):
    return [
        "provider-probe",
        "--ledger",
        str(tmp_path / "runtime.sqlite"),
        "--account-id",
        "synthetic",
        "--security-scope",
        "test",
        "--snapshot-revision",
        "r1",
        "--daily-budget-microusd",
        "10000",
        "--price-version",
        "synthetic",
        "--input-rate-microusd",
        "1000000",
        "--cached-input-rate-microusd",
        "500000",
        "--output-rate-microusd",
        "2000000",
        "--rpm",
        "30",
        "--tpm",
        "8000",
        "--rpd",
        "100",
        "--tpd",
        "200000",
    ]


def test_offline_demo():
    result = provider_demo()
    assert result["status"] == "PASS" and result["real_inference_calls"] == 0
    assert result["simulated_transport_calls"] == 2
    assert result["ledger"]["known_cost_microusd"] == 96
    assert result["ledger"]["held_cost_microusd"] == 0
    assert result["results"]["identical_replay"]["new_cost_microusd"] == 0


def test_demo_export_never_overwrites(tmp_path, capsys):
    target = tmp_path / "demo.json"
    assert main(["provider-demo", "--output", str(target)]) == 0
    original = target.read_bytes()
    assert json.loads(original)["status"] == "PASS"
    assert main(["provider-demo", "--output", str(target)]) == 1
    assert target.read_bytes() == original


@pytest.mark.parametrize("allow,key", [(False, True), (True, False)])
def test_probe_requires_authorization_and_key_before_writes(
    tmp_path, monkeypatch, capsys, allow, key
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    if key:
        monkeypatch.setenv("GROQ_API_KEY", "PRIVATE_TEST_KEY")
    args = live_args(tmp_path) + (["--allow-live"] if allow else [])
    assert main(args) == 1 and not (tmp_path / "runtime.sqlite").exists()
    assert "PRIVATE_TEST_KEY" not in capsys.readouterr().err


def test_probe_with_mocked_transport_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GROQ_API_KEY", "PRIVATE_TEST_KEY")
    fake = SyntheticTransport()
    monkeypatch.setattr(GroqTransport, "send", lambda self, *args: fake.send(*args))
    assert main(live_args(tmp_path) + ["--allow-live"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "success" and fake.calls == 1
    assert "content" not in result["completion"]
    assert "PRIVATE_TEST_KEY" not in json.dumps(result)
