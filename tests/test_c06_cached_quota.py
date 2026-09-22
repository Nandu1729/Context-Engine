"""Offline tests for explicit cache-only quota amendment; never reads owner keys."""

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from context_engine.errors import ContractError, QuotaError, StorageError
from context_engine.providers.contracts import (
    Completion,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    Usage,
)
from context_engine.providers.store import RuntimeStore

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("c06_complete", SCRIPTS / "c06_complete.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
sys.modules["c06_complete"] = base
spec = importlib.util.spec_from_file_location("c06_cached_quota", SCRIPTS / "c06_cached_quota.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NOW = 86400 * 100 + 120
POLICY = QuotaPolicy(**base.POLICY)
PRICES = PriceCard("test-free", 0, 0, 0)


def row(cached=54272, **overrides):
    return {
        "state": "completed",
        "charged_tokens": 197221,
        "cost": 0,
        "request_count": 173,
        "created": NOW - 100,
        "settled": NOW - 100,
        "usage_json": json.dumps(asdict(Usage(197000, 221, cached))),
        **overrides,
    }


def test_known_credit_releases_only_confirmed_tokens_and_preserves_row():
    r = row()
    before = dict(r)
    status = c.pacing([r], 3231, NOW)
    assert status["status"] == "ready"
    assert status["daily_remaining"] == 57051
    assert status["known_cached_daily_tokens"] == 54272
    assert status["full_daily_tokens"] == 197221
    assert r == before


@pytest.mark.parametrize("cached", [None, 0])
def test_unknown_or_zero_cached_gets_no_credit(cached):
    assert c.pacing([row(cached)], 3231, NOW)["reason"] == "daily_quota"


@pytest.mark.parametrize(
    "overrides",
    [
        {"state": "uncertain"},
        {"state": "inflight"},
        {"state": "reserved"},
        {"cost": 1},
        {"cost": None},
        {"charged_tokens": None},
    ],
)
def test_cache_never_releases_active_unknown_or_paid_usage(overrides):
    assert c.pacing([row(**overrides)], 3231, NOW)["status"] == "stop"


def test_credit_does_not_change_request_limits():
    assert c.pacing([row(request_count=1000)], 3231, NOW)["reason"] == "daily_quota"


def test_minute_and_settlement_window_still_apply():
    r = row(settled=NOW - 1)
    assert c.pacing([r], 3231, NOW)["status"] == "wait"
    assert c.pacing([r], 3231, NOW + 61)["status"] == "ready"


@pytest.mark.parametrize(
    "change",
    [
        {"charged_tokens": 197220},
        {"usage_json": '{"input_tokens":10,"output_tokens":2,"cached_input_tokens":11}'},
        {"usage_json": "not-json"},
    ],
)
def test_inconsistent_usage_fails_closed(change):
    with pytest.raises((ContractError, StorageError, ValueError)):
        c.pacing([row(**change)], 3231, NOW)


def admit(store, key="next", **overrides):
    args = dict(
        policy=POLICY,
        key=key,
        model="openai/gpt-oss-20b",
        reserved_tokens=3231,
        reserved_cost=0,
        prices=PRICES,
        replay=ReplayPolicy(),
        now=NOW,
    )
    return store.admit(**(args | overrides))


def seeded(tmp_path, cached=54272):
    path = tmp_path / "ledger.sqlite"
    old = RuntimeStore(path)
    first = admit(old, key="prior", reserved_tokens=100, now=NOW - 101)
    old.mark_inflight(first.attempt_id)
    old.settle(
        first.attempt_id,
        now=NOW - 100,
        completion=Completion(
            "openai/gpt-oss-20b", "test-id", "OK", "stop", Usage(197000, 221, cached)
        ),
    )
    return old, c.CachedQuotaStore(path)


def test_store_projection_keeps_full_usage_and_writes_audit_event(tmp_path):
    old, new = seeded(tmp_path)
    before = old.snapshot(POLICY)["attempts"]
    with pytest.raises(QuotaError):
        admit(old)
    reservation = admit(new)
    after = new.snapshot(POLICY)
    assert next(r for r in after["attempts"] if r["id"] == before[0]["id"]) == before[0]
    assert (
        next(r for r in after["attempts"] if r["id"] == reservation.attempt_id)["reserved_tokens"]
        == 3231
    )
    assert after["events"][-1]["kind"] == "cached_quota_admission_v1"
    with pytest.raises(QuotaError):
        admit(new, key="competing")


def test_unknown_cache_still_blocked_in_store(tmp_path):
    _, new = seeded(tmp_path, cached=None)
    with pytest.raises(QuotaError):
        admit(new)


def test_completed_key_never_resent(tmp_path):
    _, new = seeded(tmp_path)
    with pytest.raises(QuotaError):
        admit(new, key="prior")


@pytest.mark.parametrize(
    "overrides",
    [
        {"reserved_cost": 1},
        {"reserved_tokens": 8001},
        {"policy": replace(POLICY, tpd=400000)},
        {"replay": ReplayPolicy(enabled=True)},
    ],
)
def test_store_refuses_scope_expansion(tmp_path, overrides):
    _, new = seeded(tmp_path)
    with pytest.raises(ContractError):
        admit(new, **overrides)


def test_default_status_does_not_dispatch(monkeypatch):
    monkeypatch.setattr(c, "inspect", lambda: {"status": "ready"})
    monkeypatch.setattr(c, "dispatch", lambda _: pytest.fail("no inference"))
    monkeypatch.setattr(c, "verify_amendment", lambda: pytest.fail("no live bootstrap"))
    assert c.main([]) == 0


def test_hidden_batch_also_requires_explicit_live_flag(monkeypatch):
    monkeypatch.setattr(c, "batch", lambda _: pytest.fail("no inference"))
    assert c.main(["--batch", "unused.json"]) == 1
