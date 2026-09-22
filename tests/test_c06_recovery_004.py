"""Regression: equal ablation payloads are distinct cases, never case replay."""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from context_engine.errors import ContractError, QuotaError
from context_engine.providers.contracts import (
    Completion,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    Usage,
)
from context_engine.providers.store import RuntimeStore

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in (
    "c06_complete",
    "c06_cached_quota",
    "c06_recovery",
    "c06_recovery_003",
    "c06_recovery_004",
):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
r = module
POLICY = QuotaPolicy(**r.base.POLICY)
PRICES = PriceCard("test-free", 0, 0, 0)
NOW = 86400 * 100 + 120


def admit(store, **changes):
    return store.admit(
        **(
            {
                "policy": POLICY,
                "key": "identical-payload",
                "model": "openai/gpt-oss-20b",
                "reserved_tokens": 3243,
                "reserved_cost": 0,
                "prices": PRICES,
                "replay": ReplayPolicy(),
                "now": NOW,
            }
            | changes
        )
    )


def settle(store, attempt):
    store.mark_inflight(attempt.attempt_id)
    store.settle(
        attempt.attempt_id,
        now=NOW,
        completion=Completion("openai/gpt-oss-20b", "test", "UNKNOWN", "stop", Usage(100, 1)),
    )


def setup_store(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    monkeypatch.setattr(r, "PLAN", plan)
    return r.CaseQuotaStore(tmp_path / "ledger.sqlite")


def test_prior_completed_payload_allows_distinct_case(tmp_path, monkeypatch):
    store = setup_store(tmp_path, monkeypatch)
    old = RuntimeStore(store.path)
    first = admit(old)
    settle(old, first)
    before = old.snapshot(POLICY)["attempts"][0]
    monkeypatch.setattr(r, "claimed_probe", lambda *_: "case-B")
    second = admit(store)
    assert second.attempt_id != first.attempt_id
    after = store.snapshot(POLICY)
    assert next(x for x in after["attempts"] if x["id"] == first.attempt_id) == before
    assert after["events"][-1]["kind"] == "c06_admission_amendment004"


def test_same_case_cannot_redispatch_after_completion(tmp_path, monkeypatch):
    store = setup_store(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "claimed_probe", lambda *_: "case-B")
    first = admit(store)
    with pytest.raises(QuotaError):
        admit(store)
    settle(store, first)
    with pytest.raises(QuotaError):
        admit(store)
    monkeypatch.setattr(r, "claimed_probe", lambda *_: "case-C")
    assert admit(store).attempt_id != first.attempt_id


def test_unknown_usage_stays_held(tmp_path, monkeypatch):
    store = setup_store(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "claimed_probe", lambda *_: "case-B")
    first = admit(store)
    store.mark_inflight(first.attempt_id)
    store.settle(first.attempt_id, now=NOW, uncertain=True, reason="timeout")
    with pytest.raises(QuotaError):
        admit(store)


@pytest.mark.parametrize(
    "changes",
    [{"reserved_cost": 1}, {"reserved_tokens": 8001}, {"replay": ReplayPolicy(enabled=True)}],
)
def test_scope_guards_retained(tmp_path, monkeypatch, changes):
    store = setup_store(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "claimed_probe", lambda *_: "case-B")
    with pytest.raises(ContractError):
        admit(store, **changes)


def test_orphan_sidecar_number_is_never_reused(tmp_path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    (output / "c06-live-batch-155.json").touch()
    (output / "c06-live-batch-156.recovery.json").touch()
    monkeypatch.setattr(r, "ROOT", tmp_path)
    assert r.next_snapshot().name == "c06-live-batch-157.json"


def test_zero_progress_ready_stops_but_real_wait_is_allowed():
    before = {"terminal": 651, "status": "ready"}
    with pytest.raises(ValueError):
        r.check_progress(before, dict(before))
    r.check_progress(before, {"terminal": 651, "status": "wait"})
    r.check_progress(before, {"terminal": 652, "status": "ready"})


@pytest.fixture
def claim(tmp_path, monkeypatch):
    from context_engine.evaluation.corpus import load_bundle
    from context_engine.evaluation.execution import expected_request_key

    baseline = json.loads((SCRIPTS.parent / "output/c06-live-batch-155.json").read_text())
    row = next(e["record"] for e in baseline["entries"] if e["phase"] == "pending")
    journal = tmp_path / "journal.sqlite"
    con = sqlite3.connect(journal)
    con.execute("CREATE TABLE benchmark_probes(id TEXT,record TEXT,phase TEXT)")
    con.execute("CREATE TABLE benchmark_identity(payload TEXT)")
    con.execute(
        "INSERT INTO benchmark_probes VALUES(?,?,'dispatching')", (row["probe_id"], json.dumps(row))
    )
    con.execute(
        "INSERT INTO benchmark_identity VALUES(?)",
        (json.dumps({"profile": baseline["profile"], "manifest": baseline["manifest"]}),),
    )
    con.commit()
    monkeypatch.setattr(r.base, "JOURNAL", journal)
    monkeypatch.setattr(r, "verify", lambda: baseline)
    key = expected_request_key(
        row,
        baseline["profile"],
        r.base.EXECUTION,
        load_bundle().get("scenario")["scope"],
        baseline["manifest"]["protocol"],
    )
    yield con, row, key
    con.close()


def test_real_claim_binding_and_completed_case_refusal(claim):
    con, row, key = claim
    reservation = row["estimate"]["estimated_tokens"] + 256
    assert r.claimed_probe(key, row["model"], reservation) == row["probe_id"]
    con.execute("UPDATE benchmark_probes SET phase='done'")
    con.commit()
    with pytest.raises(QuotaError):
        r.claimed_probe(key, row["model"], reservation)


@pytest.mark.parametrize("wrong", ["key", "model", "reservation"])
def test_mismatched_claim_refused(claim, wrong):
    _, row, key = claim
    model, reservation = row["model"], row["estimate"]["estimated_tokens"] + 256
    if wrong == "key":
        key = "wrong"
    elif wrong == "model":
        model = "openai/gpt-oss-120b"
    else:
        reservation += 1
    with pytest.raises(ContractError):
        r.claimed_probe(key, model, reservation)


def test_hidden_batch_needs_live_optin(monkeypatch):
    monkeypatch.setattr(r.previous, "batch", lambda _: pytest.fail("must not dispatch"))
    assert r.main(["--batch", "unused"]) == 1
