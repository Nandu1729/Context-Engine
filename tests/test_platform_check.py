import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("platform_probe", ROOT / "scripts/platform_check.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_real_local_probes_are_not_production_qualification():
    result = probe.check()
    assert result["status"] == "LOCAL_PROBES_PASS"
    assert len(result["probes"]) == 4 and all(p["passed"] for p in result["probes"].values())
    assert result["inference_calls"] == 0
    assert result["qualification_complete"] is False
    assert len(result["runner_sha256"]) == 64


def test_failure_is_recorded_without_sensitive_error_message(monkeypatch):
    def failed():
        raise RuntimeError("SECRET_TEST_DETAIL")

    monkeypatch.setattr(probe, "memory_demo", failed)
    result = probe.check()
    assert result["status"] == "FAIL"
    assert not result["probes"]["memory_recovery"]["passed"]
    assert "SECRET_TEST_DETAIL" not in json.dumps(result)


def test_missing_research_capability_does_not_claim_compatibility(monkeypatch):
    original = probe.importlib.util.find_spec
    monkeypatch.setattr(
        probe.importlib.util, "find_spec", lambda name: None if name == "fcntl" else original(name)
    )
    result = probe.check()
    assert result["research_runner_capabilities"]["fcntl_module_available"] is False
    assert result["qualification_complete"] is False


def test_directory_fsync_failure_is_explicit(monkeypatch):
    def failed(_fd):
        raise OSError("unsupported")

    monkeypatch.setattr(probe.os, "fsync", failed)
    assert probe.directory_sync_probe() is False


def test_output_cannot_be_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_text("preserved")
    monkeypatch.setattr("sys.argv", ["platform_check.py", "--output", str(path)])
    monkeypatch.setattr(probe, "check", lambda: pytest.fail("Must reject before probing"))
    with pytest.raises(SystemExit):
        probe.main()
    assert path.read_text() == "preserved"


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_kill_probe_newlines_and_credential_isolation(monkeypatch, newline):
    monkeypatch.setenv("GROQ_API_KEY", "TEST_ONLY_NOT_A_REAL_KEY")

    class Child:
        returncode = None

        async def readline(self):
            return b"ready" + newline

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    child = Child()
    child.stdout = child

    async def spawn(*args, **kwargs):
        assert "GROQ_API_KEY" not in kwargs["env"]
        return child

    monkeypatch.setattr(probe.asyncio, "create_subprocess_exec", spawn)
    assert asyncio.run(probe.kill_probe()) == {"subprocess_killed_and_reaped": True}
    assert child.returncode is not None
