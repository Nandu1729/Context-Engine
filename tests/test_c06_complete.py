"""Controller tests use synthetic ledger data; no live provider or owner key."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "c06_complete", Path(__file__).resolve().parents[1] / "scripts/c06_complete.py"
)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NOW = 86400 * 100 + 120


def attempt(tokens=5000, when=NOW - 10, **overrides):
    return {
        "state": "completed",
        "charged_tokens": tokens,
        "cost": 0,
        "request_count": 1,
        "created": when,
        "settled": when,
        **overrides,
    }


def test_unused_day_ready():
    assert c.pacing([], 3000, NOW)["status"] == "ready"


def test_paces_minute_without_reset():
    row = attempt()
    assert c.pacing([row], 3244, NOW)["status"] == "wait"
    assert 0 < c.pacing([row], 3244, NOW)["seconds"] <= 30
    assert c.pacing([row], 3244, NOW + 61)["status"] == "ready"
    assert row["charged_tokens"] == 5000


def test_daily_quota_stops_and_preserves_old_days():
    row = attempt(tokens=198000, when=NOW - 100)
    result = c.pacing([row], 3000, NOW)
    assert result["status"] == "stop" and result["reason"] == "daily_quota"
    assert result["daily_remaining"] == 2000
    later = c.pacing([row], 3000, result["next_local_utc_window"])
    assert later["status"] == "ready" and row["charged_tokens"] == 198000


def test_daily_requests_limited():
    assert (
        c.pacing([attempt(0, NOW - 100, request_count=1000)], 3000, NOW)["reason"] == "daily_quota"
    )


def test_minute_requests_limited():
    assert c.pacing([attempt(0, request_count=30)], 3000, NOW)["status"] == "wait"


@pytest.mark.parametrize("state", ["reserved", "inflight", "uncertain"])
def test_uncertainty_never_expires(state):
    assert (
        c.pacing([attempt(when=0, state=state)], 3000, NOW)["reason"]
        == "uncertain_or_active_attempt"
    )


@pytest.mark.parametrize("overrides", [{"charged_tokens": None}, {"cost": None}, {"cost": 1}])
def test_unknown_or_paid_stops(overrides):
    assert c.pacing([attempt(**overrides)], 3000, NOW)["status"] == "stop"


@pytest.mark.parametrize("reservation", [0, -1, 8001, True, 1.5])
def test_invalid_reservation_stops(reservation):
    assert c.pacing([], reservation, NOW)["status"] == "stop"


def test_settlement_anchor_and_exact_minute_boundary():
    assert c.pacing([attempt(6000, NOW - 500, settled=NOW - 1)], 3000, NOW)["status"] == "wait"
    assert c.pacing([attempt(6000, NOW - 60)], 3000, NOW)["status"] == "ready"


def test_default_is_readonly(monkeypatch):
    monkeypatch.setattr(c, "inspect", lambda: {"status": "ready"})
    monkeypatch.setattr(c, "dispatch", lambda _: pytest.fail("must not run"))
    monkeypatch.setattr(c.os, "open", lambda *a: pytest.fail("must not create lock"))
    assert c.main([]) == 0


def test_snapshot_names_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "output/c06-live-batch-068.json").touch()
    (tmp_path / "output/c06-live-batch-069.json").touch()
    assert c.next_snapshot().name == "c06-live-batch-070.json"
