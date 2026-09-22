"""Explicit zero-price billing, unchanged quota safety and non-disclosing credential loading."""

import asyncio
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
from test_providers import REQUEST, call, client

from context_engine.errors import BenchmarkError, ContractError, QuotaError
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.execution import (
    RunJournal,
    execute,
    execution_profile,
    execution_snapshot,
    validate_execution,
)
from context_engine.evaluation.protocol import load_freeze, make_manifest
from context_engine.providers.contracts import PriceCard, QuotaPolicy, ReplayPolicy
from context_engine.providers.credentials import load_api_key, private_bytes
from context_engine.providers.store import RuntimeStore
from context_engine.tokens import TiktokenCounter

FREE = QuotaPolicy("confirmed-free-test", billing_mode="free_tier")
ZERO = PriceCard("owner-confirmed-free-test", 0, 0, 0)


@pytest.fixture
def provider(tmp_path):
    return client(
        RuntimeStore(tmp_path / "ledger.sqlite"), TiktokenCounter(), quota=FREE, prices=ZERO
    )


def test_free_call_records_usage_without_money(provider):
    result = call(provider)
    assert result.status == "success" and result.new_cost_microusd == 0
    rows = provider.store.snapshot(FREE)["attempts"]
    assert len(rows) == 1 and rows[0]["cost"] == rows[0]["reserved_cost"] == 0
    assert rows[0]["charged_tokens"] > 0 and json.loads(rows[0]["usage_json"])["input_tokens"] > 0


@pytest.mark.parametrize("dimension", ["rpm", "rpd", "tpm", "tpd"])
def test_zero_price_does_not_disable_quota(provider, dimension):
    provider.quota = replace(FREE, **{dimension: 0})
    result = call(provider)
    assert result.error_code == "quota_exhausted" and not provider.transport.calls


def test_default_zero_budget_remains_disabled(provider):
    provider.quota = replace(FREE, billing_mode="metered")
    assert call(provider).error_code == "quota_exhausted"
    assert not provider.transport.calls


@pytest.mark.parametrize("dimension", ["rpm", "rpd", "tpm", "tpd"])
def test_free_quota_survives_restart(provider, dimension):
    reservation = (
        provider.counter.count_request(REQUEST).estimated_tokens
        + provider.generation.max_completion_tokens
    )
    provider.quota = replace(FREE, **{dimension: 1 if dimension in ("rpm", "rpd") else reservation})
    assert call(provider).status == "success"
    reopened = client(
        RuntimeStore(provider.store.path), TiktokenCounter(), quota=provider.quota, prices=ZERO
    )
    assert call(reopened).error_code == "quota_exhausted"
    assert not reopened.transport.calls


def test_free_replay_zero_cost_no_new_request(provider):
    provider.replay = ReplayPolicy(enabled=True)
    first, second = call(provider), call(provider)
    assert first.status == "success" and second.status == "replay"
    assert second.new_cost_microusd == second.original_cost_microusd == 0
    assert len(provider.transport.calls) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"billing_mode": "unknown"},
        {"billing_mode": True},
        {"billing_mode": "free_tier", "daily_budget_microusd": 1},
    ],
)
def test_invalid_free_policy(kwargs):
    with pytest.raises(ContractError):
        QuotaPolicy("test", **kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "input_per_million_microusd",
        "cached_input_per_million_microusd",
        "output_per_million_microusd",
    ],
)
def test_free_account_rejects_any_paid_rate(provider, field):
    prices = replace(ZERO, **{field: 1})
    with pytest.raises(ContractError):
        client(provider.store, provider.counter, quota=FREE, prices=prices)
    with pytest.raises(ContractError):
        provider.store.admit(
            policy=FREE,
            key="x",
            model=provider.generation.model,
            reserved_tokens=1,
            reserved_cost=0,
            prices=prices,
            replay=ReplayPolicy(),
            now=provider.clock(),
        )


def test_free_admission_rejects_paid_reservation_and_account_switch(provider):
    with pytest.raises(ContractError):
        provider.store.admit(
            policy=FREE,
            key="x",
            model=provider.generation.model,
            reserved_tokens=1,
            reserved_cost=1,
            prices=ZERO,
            replay=ReplayPolicy(),
            now=provider.clock(),
        )
    assert call(provider).status == "success"
    with pytest.raises(QuotaError):
        provider.store.admit(
            policy=replace(FREE, billing_mode="metered", daily_budget_microusd=1),
            key="new",
            model=provider.generation.model,
            reserved_tokens=1,
            reserved_cost=0,
            prices=ZERO,
            replay=ReplayPolicy(),
            now=provider.clock(),
        )


def test_free_execution_zero_run_cap_and_resume(provider, tmp_path):
    bundle, frozen = load_bundle(), load_freeze()
    manifest = make_manifest(
        bundle,
        frozen,
        facts=["shard"],
        budgets=[900],
        variants=["A5"],
        models=[provider.generation.model],
    )
    clients = {provider.generation.model: provider}
    profile = execution_profile(manifest, clients, mode="offline", max_run_cost_microusd=0)
    journal = RunJournal(tmp_path / "run.sqlite", manifest, profile)
    assert asyncio.run(execute(bundle, frozen, journal, clients))["calls"] == 1
    assert asyncio.run(execute(bundle, frozen, journal, clients))["calls"] == 0
    payload = execution_snapshot(journal)
    assert validate_execution(bundle, frozen, payload)[2]["status"] == "TEST_ONLY"
    for maximum in (1, True, -1):
        with pytest.raises(BenchmarkError):
            execution_profile(manifest, clients, mode="offline", max_run_cost_microusd=maximum)


@pytest.fixture
def key_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("# synthetic only\nGROQ_API_KEY=PRIVATE_TEST_KEY\n")
    path.chmod(0o600)
    return path


def test_explicit_key_file_does_not_modify_environment(key_file, monkeypatch):
    import os

    assert load_api_key(key_file) == "PRIVATE_TEST_KEY"
    assert "GROQ_API_KEY" not in os.environ
    monkeypatch.setenv("GROQ_API_KEY", "PRIVATE_TEST_KEY")
    assert load_api_key(key_file) == "PRIVATE_TEST_KEY"
    monkeypatch.setenv("GROQ_API_KEY", "DIFFERENT_PRIVATE_KEY")
    with pytest.raises(ContractError) as error:
        load_api_key(key_file)
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "GROQ_API_KEY=",
        "GROQ_API_KEY=''",
        'GROQ_API_KEY=""',
        "GROQ_API_KEY=A\nGROQ_API_KEY=B",
        "OTHER=PRIVATE_SECRET",
        "GROQ_API_KEY=$(touch should-not-exist)",
        "GROQ_API_KEY=`whoami`",
        "GROQ_API_KEY=PRIVATE KEY",
        "GROQ_API_KEY=PRIVATE;command",
        "GROQ_API_KEY=é",
    ],
)
def test_key_file_rejects_invalid_assignments_without_echo(key_file, content):
    key_file.write_text(content)
    with pytest.raises(ContractError) as error:
        load_api_key(key_file)
    assert "PRIVATE" not in str(error.value) and "touch" not in str(error.value)


@pytest.mark.parametrize("value", ["PRIVATE_KEY", "'PRIVATE_KEY'", '"PRIVATE_KEY"'])
def test_key_file_accepts_plain_or_quoted_key(key_file, value):
    key_file.write_text(f"GROQ_API_KEY={value}\n")
    assert load_api_key(key_file) == "PRIVATE_KEY"


@pytest.mark.parametrize("problem", ["public", "symlink", "oversized", "missing", "directory"])
def test_private_file_boundaries(key_file, problem):
    path = key_file
    if problem == "public":
        path.chmod(0o644)
    elif problem == "symlink":
        path = key_file.parent / "link"
        path.symlink_to(key_file)
    elif problem == "oversized":
        path.write_text("X" * 8193)
    elif problem == "missing":
        path = key_file.parent / "missing"
    else:
        path = key_file.parent
    with pytest.raises(ContractError):
        private_bytes(path, 8192)


@pytest.mark.parametrize(
    "problem",
    [
        "valid",
        "paid_rate",
        "positive_free_run",
        "positive_free_day",
        "bool_run",
        "metered_zero",
        "public_config",
        "unapproved",
        "unauthorized",
    ],
)
def test_live_cli_preflight_before_any_store_or_dispatch(key_file, monkeypatch, problem):
    from context_engine.evaluation import run_commands as module

    model = "openai/gpt-oss-120b"
    # Isolate configuration preflight; never rewrite the real protocol or its approval.
    bundle = SimpleNamespace(
        get=lambda _: {"approval": "owner_pending" if problem == "unapproved" else "owner_approved"}
    )
    monkeypatch.setattr(module, "load_bundle", lambda: bundle)
    monkeypatch.setattr(
        module, "make_manifest", lambda *a, **kw: SimpleNamespace(data={"models": [model]})
    )
    config = {
        "quota": asdict(FREE),
        "prices": {model: asdict(ZERO)},
        "max_run_cost_microusd": 0,
        "ledger_path": str(key_file.parent / "ledger.sqlite"),
    }
    if problem == "paid_rate":
        config["prices"][model]["output_per_million_microusd"] = 1
    if problem == "positive_free_run":
        config["max_run_cost_microusd"] = 1
    if problem == "positive_free_day":
        config["quota"]["daily_budget_microusd"] = 1
    if problem == "bool_run":
        config["max_run_cost_microusd"] = False
    if problem == "metered_zero":
        config["quota"]["billing_mode"] = "metered"
    path = key_file.parent / "config.json"
    path.write_text(json.dumps(config))
    path.chmod(0o644 if problem == "public_config" else 0o600)
    args = SimpleNamespace(
        command="benchmark-run",
        model=[model],
        fact=None,
        budget=None,
        variant=None,
        mode="live",
        allow_live=problem != "unauthorized",
        live_config=path,
        env_file=key_file,
        max_calls=0,
        snapshot=key_file.parent / "result.json",
    )

    class ValidatedBeforeStore(Exception):
        pass

    def no_store(*_):
        raise ValidatedBeforeStore()

    monkeypatch.setattr(module, "RuntimeStore", no_store)
    expected = ValidatedBeforeStore if problem == "valid" else (BenchmarkError, ContractError)
    with pytest.raises(expected) as error:
        module.run_command(args)
    assert "PRIVATE_TEST_KEY" not in str(error.value)
    assert not (key_file.parent / "ledger.sqlite").exists()
