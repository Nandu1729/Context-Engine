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


def test_current_runtime_matches_new_freeze_not_baseline():
    assert load_freeze()["runtime"]["code_hash"] == code_hash()
    assert code_hash() != BASELINE_HASH
    assert load_freeze()["runtime"]["package_version"] == "0.9.3"
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


def test_preserved_wheel_accepts_original_manifests_offline(tmp_path):
    assert hashlib.sha256(WHEEL.read_bytes()).hexdigest() == (
        "0b4e0d7bf09814fbaa62f29d725740fcee367d24074cfa2b8002185edb024d67"
    )
    program = """
import asyncio, json, runpy, socket, ssl, sys
from pathlib import Path
assert sys.flags.utf8_mode == 1
sys.path.insert(0, sys.argv[1])
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
        [sys.executable, "-X", "utf8", "-c", program, str(WHEEL), str(ROOT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"hash": BASELINE_HASH, "version": "0.9.2"}
