"""D090: explicit Windows boundary for frozen POSIX research runners only."""

import json
import shutil
import sys

import pytest
from private_files import set_private_permissions

from context_engine.evaluation.protocol import runtime_identity


@pytest.fixture(scope="session")
def tmp_path_factory(tmp_path_factory):
    """Synthetic Windows storage gets a private, inheritable directory ACL.

    Only this session's pytest-owned directory is changed; never operator paths.
    Negative tests explicitly grant broad access after setup.
    """
    with pytest.MonkeyPatch.context() as patch:
        if sys.platform == "win32":
            set_private_permissions(tmp_path_factory.getbasetemp())
            original = tmp_path_factory.mktemp

            def mktemp(basename, numbered=True):
                # Python's Windows mkdir(0700) installs a protected OWNER RIGHTS
                # ACL, replacing inheritance from our configured base directory.
                path = original(basename, numbered=numbered)
                set_private_permissions(path)
                return path

            patch.setattr(tmp_path_factory, "mktemp", mktemp)
        yield tmp_path_factory


@pytest.fixture(scope="module")
def candidate_harness(tmp_path_factory):
    """Fresh TEST_ONLY manifests for unit tests, never rewrite historical freezes.

    Runtime identity remains real; all resource/runtime guards still execute.
    Historical replay is checked separately using the preserved 0.9.2 wheel.
    """
    with pytest.MonkeyPatch.context() as patch:

        def prepare(module):
            directory = tmp_path_factory.mktemp("candidate-harness") / module.DIRECTORY.name
            shutil.copytree(module.DIRECTORY, directory)
            manifest_path = directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["runtime"] = runtime_identity()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            patch.setattr(module, "DIRECTORY", directory)

        yield prepare


# Exact modules, not wildcards: new tests are never automatically excluded.
# Their frozen runner imports require fcntl; Linux/macOS still collect all of them.
POSIX_RUNNER_MODULES = (
    "test_c06_cached_quota.py",
    "test_c06_complete.py",
    "test_c06_recovery.py",
    "test_c06_recovery_003.py",
    "test_c06_recovery_004.py",
    "test_c06_recovery_005.py",
    "test_c06_recovery_006.py",
    "test_c06_recovery_007.py",
    "test_c06_recovery_008.py",
    "test_c06_recovery_009.py",
    "test_c06_rejection_diagnostic.py",
    "test_c09_live.py",
    "test_c09_policy_live.py",
    "test_c09_qualification_live.py",
    "test_c09_response_diagnostic.py",
    "test_c09_structured_smoke.py",
    "test_gemini_comparison.py",
)


def excluded_modules(platform):
    return list(POSIX_RUNNER_MODULES) if platform == "win32" else []


collect_ignore = excluded_modules(sys.platform)


def pytest_terminal_summary(terminalreporter):
    if collect_ignore:
        terminalreporter.section("Windows scope: frozen POSIX runners NOT TESTED")
        terminalreporter.write_line(
            "17 modules excluded before import (fcntl unavailable); "
            "these are NOT passes. Linux/macOS run the complete suite."
        )
        for name in collect_ignore:
            terminalreporter.write_line(f"  NOT TESTED: {name}")
