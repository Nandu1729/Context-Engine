"""Diagnostic classifications are fixed labels, never provider content."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in ("c06_complete", "c06_cached_quota", "c06_recovery", "c06_rejection_diagnostic"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
d = module


def test_only_fixed_labels_leave_classifier():
    assert d.classify('{"error":{"code":"secret","message":"private data"}}') == {
        "code": "unclassified",
        "tool_generation_reported": False,
    }
    assert d.classify('{"error":{"code":"tool_use_failed","message":"Tool choice is none"}}') == {
        "code": "tool_use_failed",
        "tool_generation_reported": True,
    }


@pytest.mark.parametrize("raw", ["not json", "null", "{}", '{"error":[]}', '{"error":{"code":[]}}'])
def test_malformed_error_never_echoed(raw):
    assert d.classify(raw) == {"code": "unclassified", "tool_generation_reported": False}


def test_default_never_calls_provider(monkeypatch):
    monkeypatch.setattr(d, "run", lambda *_: pytest.fail("not authorized"))
    assert d.main([]) == 0
