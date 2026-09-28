"""Verify the narrow platform boundary without changing any frozen runner."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).parent
spec = importlib.util.spec_from_file_location("platform_scope", TESTS / "conftest.py")
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_temp_factory_permissions_cover_each_new_directory_and_restore(
    monkeypatch, tmp_path, platform
):
    events = []

    def original(basename, numbered=True):
        path = tmp_path / (basename + ("0" if numbered else ""))
        path.mkdir()
        events.append(("created", path))
        return path

    factory = SimpleNamespace(getbasetemp=lambda: tmp_path, mktemp=original)
    monkeypatch.setattr(scope, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(
        scope, "set_private_permissions", lambda path: events.append(("secured", path))
    )
    fixture = scope.tmp_path_factory.__wrapped__(factory)
    assert next(fixture) is factory
    first = factory.mktemp("numbered")
    second = factory.mktemp("exact", numbered=False)
    expected = [("created", first), ("created", second)]
    if platform == "win32":
        expected = [
            ("secured", tmp_path),
            ("created", first),
            ("secured", first),
            ("created", second),
            ("secured", second),
        ]
    assert events == expected
    # Deliberate negative-test ACL changes are never repaired on a later lookup.
    factory.getbasetemp()
    assert events == expected
    fixture.close()
    assert factory.mktemp is original


def test_temp_factory_permission_failure_is_not_suppressed(monkeypatch, tmp_path):
    def original(basename, numbered=True):
        path = tmp_path / basename
        path.mkdir()
        return path

    def secure(path):
        if path != tmp_path:
            raise OSError("synthetic ACL setup failure")

    factory = SimpleNamespace(getbasetemp=lambda: tmp_path, mktemp=original)
    monkeypatch.setattr(scope, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(scope, "set_private_permissions", secure)
    fixture = scope.tmp_path_factory.__wrapped__(factory)
    next(fixture)
    try:
        with pytest.raises(OSError, match="ACL setup failure"):
            factory.mktemp("blocked")
    finally:
        fixture.close()
    assert factory.mktemp is original


@pytest.mark.parametrize("platform", ["darwin", "linux", "freebsd", "unknown"])
def test_non_windows_keeps_every_module(platform):
    assert scope.excluded_modules(platform) == []


def test_windows_boundary_is_exact_existing_files():
    names = scope.excluded_modules("win32")
    assert len(names) == len(set(names)) == 17
    assert all((TESTS / name).is_file() for name in names)
    assert all("*" not in name and "/" not in name for name in names)
    assert "test_service.py" not in names
    assert "test_c09_workers.py" not in names
    names.clear()
    assert len(scope.excluded_modules("win32")) == 17


@pytest.mark.parametrize("windows", [True, False])
def test_collection_boundary_and_visible_report(tmp_path, windows):
    # A tiny isolated pytest project tests real collection. This simulates only
    # the scope decision, not Windows runtime behavior or product qualification.
    source = (TESTS / "conftest.py").read_text(encoding="utf-8")
    source = source.replace(
        "excluded_modules(sys.platform)", f"excluded_modules({'win32' if windows else 'linux'!r})"
    )
    (tmp_path / "conftest.py").write_text(source, encoding="utf-8")
    (tmp_path / "private_files.py").write_text(
        (TESTS / "private_files.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "test_c06_complete.py").write_text(
        'raise RuntimeError("POSIX_IMPORT_SENTINEL")\n', encoding="utf-8"
    )
    (tmp_path / "test_product.py").write_text(
        "def test_product():\n    assert True\n", encoding="utf-8"
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTEST_")}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if windows:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout
        for name in scope.POSIX_RUNNER_MODULES:
            assert f"NOT TESTED: {name}" in result.stdout
        assert "POSIX_IMPORT_SENTINEL" not in result.stdout
    else:
        assert result.returncode == 2
        assert "POSIX_IMPORT_SENTINEL" in result.stdout
        assert "NOT TESTED:" not in result.stdout
