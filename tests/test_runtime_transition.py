"""Real old-runtime preservation and strict rejection of historical replay on new code."""

import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from context_engine.errors import BenchmarkError
from context_engine.evaluation.protocol import code_hash, load_freeze

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archives/c10-admission-093"
WHEEL = ARCHIVE / "context_engineering_core-0.9.2-py3-none-any.whl"
BASELINE_HASH = "298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc"
# 0.11.0 patched certifi/urllib3; historical runtime identities recorded these exact wheels.
HISTORICAL_DEPENDENCIES = {
    "certifi-2026.7.22-py3-none-any.whl": (
        "62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775"
    ),
    "urllib3-2.7.0-py3-none-any.whl": (
        "9fb4c81ebbb1ce9531cce37674bbc6f1360472bc18ca9a553ede278ef7276897"
    ),
}


def historical_dependencies() -> list[str]:
    """Verified pre-0.11.0 dependency wheels, to prepend for archived-runtime replays."""
    directory = ROOT / "archives/runtime-deps-pre-0110"
    paths = []
    for name, expected in HISTORICAL_DEPENDENCIES.items():
        path = directory / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        paths.append(str(path))
    return paths


def test_current_runtime_matches_new_freeze_not_baseline():
    assert load_freeze()["runtime"]["code_hash"] == code_hash()
    assert code_hash() != BASELINE_HASH
    assert load_freeze()["runtime"]["package_version"] == "0.14.0"
    assert (
        json.loads((ARCHIVE / "baseline-freeze.json").read_text())["runtime"]["code_hash"]
        == BASELINE_HASH
    )


def test_old_qualification_rejects_new_runtime_without_modified_guards():
    qualification = runpy.run_path(str(ROOT / "scripts/c09_qualification.py"))
    with pytest.raises(BenchmarkError, match="freeze"):
        qualification["load"]()
    policy = runpy.run_path(str(ROOT / "scripts/c09_policy_qualification.py"))
    with pytest.raises(ValueError, match="Frozen"):
        policy["prepare"]()


@pytest.mark.parametrize(
    "directory,version,wheel_hash",
    [
        (
            "c10-credentials-094",
            "0.9.3",
            "2ce93721c77b378dec1b776dfa8d33b0866ffa5ca51fbf8f44b33c2d6b582eaf",
        ),
        (
            "c10-storage-095",
            "0.9.4",
            "034b57c33847925edb13ecfe7207c80de2a643c574eafbb02d5cd311e1d975d1",
        ),
        (
            "c10-tempdirs-096",
            "0.9.5",
            "f9103807db9317ff15f9f191a02b513b55b49decd2b3bd8bd83d0c1fc616a9e0",
        ),
        (
            "c11-summaries-0100",
            "0.9.6",
            "d8a2a0bb5171fbb9098e0e821f763e3484befee70c5a236c6c0a36d60eada5b3",
        ),
        (
            "c11-recover-default-0110",
            "0.10.0",
            "59157d991027063bf3cf96a8be9fb484062c142552ee4f86bd255dd0ac16788e",
        ),
        (
            "c12-adapters-0120",
            "0.11.0",
            "fa9882324cd39554fa2cce364aa5cc5009ba827e1592fc9a1206d9985fc821ff",
        ),
        (
            "c12-latency-0121",
            "0.12.0",
            "9b289b16355b5941943c98041feed40be9a529a5b6a15058a7d92ae4229f95ac",
        ),
        (
            "c13-paraphrase-0130",
            "0.12.1",
            "1585cabd2098821ff5d413b82764b9efe72c3dadf03ccbf084fe2527960ad217",
        ),
        (
            "c14-semantic-0140",
            "0.13.0",
            "ce1048d7158942e6bc151fe6820d14b43f3035dab9c947239e525efded4143ae",
        ),
    ],
)
def test_preserved_prior_wheel_and_freeze_match(tmp_path, directory, version, wheel_hash):
    archive = ROOT / "archives" / directory
    wheel = archive / f"context_engineering_core-{version}-py3-none-any.whl"
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == wheel_hash
    baseline = json.loads((archive / "baseline-freeze.json").read_text(encoding="utf-8"))
    program = """
import json, sys
sys.path.insert(0, sys.argv[1])
from context_engine.evaluation.protocol import code_hash, load_freeze
freeze = load_freeze()
assert freeze['runtime']['code_hash'] == code_hash()
print(json.dumps(freeze))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-c", program, str(wheel)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR"}
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == baseline
    assert baseline["runtime"]["code_hash"] != code_hash()


def test_preserved_wheel_accepts_original_manifests_offline(tmp_path):
    assert hashlib.sha256(WHEEL.read_bytes()).hexdigest() == (
        "0b4e0d7bf09814fbaa62f29d725740fcee367d24074cfa2b8002185edb024d67"
    )
    program = """
import asyncio, json, runpy, socket, ssl, sys
from pathlib import Path
assert sys.flags.utf8_mode == 1
sys.path.insert(0, sys.argv[1])
sys.path[:0] = json.loads(sys.argv[3])
def deny(*args, **kwargs):
    raise AssertionError('No network in historical runtime validation')
class DeniedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        deny()
socket.socket, socket.create_connection = DeniedSocket, deny
from context_engine.evaluation.protocol import code_hash, runtime_identity
root = Path(sys.argv[2])
q = runpy.run_path(str(root / 'scripts/c09_qualification.py'))
_, _, manifest = q['load']()
saved = root / 'output/c09-qualification-002/preparation.json'
assert q['prepare']() == json.loads(saved.read_text())
p = runpy.run_path(str(root / 'scripts/c09_policy_qualification.py'))
assert p['identity']() == json.loads((p['DIRECTORY'] / 'manifest.json').read_text())
assert manifest['runtime'] == runtime_identity()
print(json.dumps({'hash': code_hash(), 'version': runtime_identity()['package_version']}))
"""
    allowed = {
        "PATH",
        "HOME",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "LOCALAPPDATA",
        "TIKTOKEN_CACHE_DIR",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result = subprocess.run(
        # The sanitized environment deliberately does not inherit PYTHONUTF8.
        # Preserve historical default UTF-8 reads even on Windows CP1252 hosts.
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            program,
            str(WHEEL),
            str(ROOT),
            json.dumps(historical_dependencies()),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"hash": BASELINE_HASH, "version": "0.9.2"}
