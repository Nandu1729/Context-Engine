"""C06 runner, provenance, resume and report checks; no real inference."""

import asyncio
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import pytest

from context_engine.cli import main
from context_engine.config import BudgetConfig
from context_engine.errors import BenchmarkError
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.execution import (
    RunJournal,
    execute,
    execution_profile,
    execution_snapshot,
    load_execution,
    request_from_wire,
    save_execution,
    validate_execution,
)
from context_engine.evaluation.harness import prepare_probe
from context_engine.evaluation.protocol import load_freeze, make_manifest
from context_engine.evaluation.reporting import export_report, leaderboard, scorecard
from context_engine.evaluation.run_commands import OfflineBenchmarkTransport
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    Completion,
    GenerationConfig,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    TransportFailure,
    Usage,
    fingerprint,
)
from context_engine.providers.store import RuntimeStore

MODEL = "openai/gpt-oss-120b"


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def frozen():
    return load_freeze()


class CountingTransport(OfflineBenchmarkTransport):
    def __init__(self, action=None):
        self.calls = 0
        self.action = action

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        assert set(payload) <= {
            "messages",
            "tools",
            "model",
            "max_completion_tokens",
            "temperature",
            "reasoning_effort",
            "tool_choice",
            "stream",
            "n",
            "include_reasoning",
            "service_tier",
        }
        if isinstance(self.action, Exception):
            raise self.action
        if self.action:
            return await self.action(payload)
        return await super().send(payload, api_key, timeout)


def setup_run(
    tmp_path,
    bundle,
    frozen,
    *,
    facts=None,
    variants=None,
    models=None,
    quota=None,
    maximum=100000,
    transport=None,
    replay=None,
):
    manifest = make_manifest(
        bundle,
        frozen,
        facts=facts or ["shard"],
        budgets=[900],
        variants=variants or ["A0", "A5"],
        models=models or [MODEL],
    )
    store = RuntimeStore(tmp_path / "provider.sqlite")
    quota = quota or QuotaPolicy("synthetic-test", 100000, rpm=100, tpm=100000, rpd=100, tpd=100000)
    transport = transport or CountingTransport()
    clients = {
        m: ProviderClient(
            store=store,
            quota=quota,
            prices=PriceCard("synthetic", 1000000, 500000, 2000000),
            api_key="PRIVATE_TEST_KEY",
            transport=transport,
            generation=GenerationConfig(model=m),
            replay=replay,
        )
        for m in manifest.data["models"]
    }
    profile = execution_profile(manifest, clients, mode="offline", max_run_cost_microusd=maximum)
    journal = RunJournal(tmp_path / "run.sqlite", manifest, profile)
    return journal, clients, transport


def run(bundle, frozen, journal, clients, **kwargs):
    return asyncio.run(execute(bundle, frozen, journal, clients, **kwargs))


@pytest.fixture(scope="module")
def finished(tmp_path_factory, bundle, frozen):
    journal, clients, transport = setup_run(
        tmp_path_factory.mktemp("execution"),
        bundle,
        frozen,
        variants=[f"A{i}" for i in range(6)],
        models=[MODEL, "openai/gpt-oss-20b"],
    )
    assert run(bundle, frozen, journal, clients)["status"] == "FINISHED"
    return execution_snapshot(journal), clients, transport


def test_complete_matrix_test_only_and_receipts(finished, bundle, frozen):
    payload, clients, transport = finished
    manifest, rows, validity = validate_execution(bundle, frozen, payload)
    assert len(manifest.slots) == 12 and len(rows) == 12
    assert transport.calls == 10 and validity["status"] == "TEST_ONLY"
    assert sum(r["state"] == "non_fit" for r in rows) == 2
    assert all(r["answer"] == "UNKNOWN" for r in rows if r["state"] == "success")
    assert "PRIVATE_TEST_KEY" not in json.dumps(payload)
    card = scorecard(bundle, frozen, payload)
    assert card["quality_acceptance"]["status"] == "NOT_EVALUATED"
    assert sum(g["new_cost_microusd"] for g in card["groups"]) == 500


def test_restart_skips_completed_and_honors_batch(tmp_path, bundle, frozen):
    journal, clients, transport = setup_run(tmp_path, bundle, frozen, facts=["shard", "database"])
    first = run(bundle, frozen, journal, clients, max_calls=1)
    assert first["reason"] == "batch_limit" and transport.calls == 1
    reopened = RunJournal(tmp_path / "run.sqlite", journal.manifest, journal.profile)
    assert run(bundle, frozen, reopened, clients)["status"] == "FINISHED"
    assert transport.calls == 2
    assert run(bundle, frozen, reopened, clients)["calls"] == 0 and transport.calls == 2


def test_quota_blocks_without_terminalizing_unsent_probe(tmp_path, bundle, frozen):
    quota = QuotaPolicy("q", 100000, rpm=1, tpm=100000, rpd=10, tpd=100000)
    journal, clients, transport = setup_run(
        tmp_path, bundle, frozen, facts=["shard", "database"], quota=quota
    )
    for client in clients.values():
        client.clock = lambda: 1788825600.0
    result = run(bundle, frozen, journal, clients)
    assert result["reason"] == "quota" and transport.calls == 1
    assert any(e["phase"] == "pending" and not e["receipt"] for e in journal.snapshot())
    for client in clients.values():
        client.clock = lambda: 1788825661.0
    assert run(bundle, frozen, journal, clients)["status"] == "FINISHED"
    assert transport.calls == 2


def test_total_run_budget_survives_restart(tmp_path, bundle, frozen):
    journal, clients, transport = setup_run(tmp_path, bundle, frozen, maximum=1)
    assert run(bundle, frozen, journal, clients)["reason"] == "run_budget"
    assert not transport.calls
    assert run(bundle, frozen, journal, clients)["reason"] == "run_budget"
    with pytest.raises(BenchmarkError, match="drift"):
        RunJournal(
            tmp_path / "run.sqlite",
            journal.manifest,
            {**journal.profile, "max_run_cost_microusd": 10000},
        )


def test_uncertain_dispatch_on_cancellation_never_replayed(tmp_path, bundle, frozen):
    async def check():
        started = asyncio.Event()

        async def blocking(_):
            started.set()
            await asyncio.Event().wait()

        journal, clients, transport = setup_run(
            tmp_path, bundle, frozen, transport=CountingTransport(blocking)
        )
        task = asyncio.create_task(execute(bundle, frozen, journal, clients))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        result = await execute(bundle, frozen, journal, clients)
        assert result["reason"] == "uncertain_dispatch" and transport.calls == 1

    asyncio.run(check())


def test_unknown_usage_halts_remaining_work(tmp_path, bundle, frozen):
    transport = CountingTransport(TransportFailure("timeout", uncertain=True))
    journal, clients, _ = setup_run(
        tmp_path, bundle, frozen, facts=["shard", "database"], transport=transport
    )
    assert run(bundle, frozen, journal, clients)["reason"] == "uncertain_usage"
    assert run(bundle, frozen, journal, clients)["reason"] == "uncertain_usage"
    card = scorecard(bundle, frozen, execution_snapshot(journal))
    assert sum(g["unknown_cost_outcomes"] for g in card["groups"]) == 1
    assert transport.calls == 1


def test_single_dispatch_claim_across_threads(tmp_path, bundle, frozen):
    journal, clients, _ = setup_run(
        tmp_path, bundle, frozen, facts=["shard", "database"], variants=["A5"]
    )
    for slot in journal.manifest.slots:
        journal.prepare(prepare_probe(bundle, frozen, journal.manifest, slot["probe_id"]))
    ids = [s["probe_id"] for s in journal.manifest.slots]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda identifier: journal.claim(identifier, 100), ids))
    assert outcomes.count(None) == 1 and outcomes.count("uncertain_dispatch") == 1


@pytest.mark.parametrize(
    "change", ["request", "cost", "scope", "model", "answer", "usage", "phase", "digest", "mode"]
)
def test_tampered_evidence_rejected_even_with_rehashed_export(finished, bundle, frozen, change):
    payload = deepcopy(finished[0])
    entry = next(e for e in payload["entries"] if e["receipt"])
    if change == "request":
        entry["record"]["request"]["messages"][-1]["content"] = "tampered"
    elif change == "cost":
        entry["receipt"]["result"]["new_cost_microusd"] = 0
    elif change == "scope":
        entry["receipt"]["ledger_rows"][0]["account"] = "other"
    elif change == "model":
        entry["receipt"]["result"]["completion"]["model"] = (
            "openai/gpt-oss-20b" if entry["record"]["model"] == MODEL else MODEL
        )
    elif change == "answer":
        entry["record"]["answer"] = "shard-19"
    elif change == "usage":
        entry["receipt"]["result"]["completion"]["usage"]["input_tokens"] = 0
    elif change == "phase":
        entry["phase"] = "pending"
    elif change == "mode":
        payload["profile"]["mode"] = "live"
        payload["execution_id"] = fingerprint(
            {"manifest": payload["manifest"], "profile": payload["profile"]}
        )
    payload["digest"] = fingerprint({k: v for k, v in payload.items() if k != "digest"})
    if change == "digest":
        payload["digest"] = "wrong"
    with pytest.raises(BenchmarkError):
        validate_execution(bundle, frozen, payload)


def test_reports_network_disabled_and_byte_reproducible(
    tmp_path, finished, bundle, frozen, monkeypatch
):
    def no_network(*args, **kwargs):
        raise AssertionError("Reports must not use network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    card = scorecard(bundle, frozen, finished[0])
    first = export_report(tmp_path / "one", card)
    second = export_report(tmp_path / "two", card)
    assert first == second and first["report_inference_calls"] == 0
    assert (tmp_path / "one/context_cost.png").read_bytes().startswith(b"\x89PNG")
    assert "TEST_ONLY" in leaderboard(card)
    with pytest.raises(BenchmarkError):
        export_report(tmp_path / "one", card)


def test_live_cli_denied_before_creating_files(tmp_path, bundle, frozen, monkeypatch, capsys):
    monkeypatch.setenv("GROQ_API_KEY", "PRIVATE_TEST_KEY")
    args = [
        "benchmark-run",
        "--mode",
        "live",
        "--allow-live",
        "--run-dir",
        str(tmp_path / "live"),
        "--snapshot",
        str(tmp_path / "live.json"),
        "--fact",
        "shard",
    ]
    assert main(args) == 1 and not (tmp_path / "live").exists()
    assert "PRIVATE_TEST_KEY" not in capsys.readouterr().err


@pytest.mark.parametrize("maximum", [0, -1, True, 10**13])
def test_invalid_run_cap(tmp_path, bundle, frozen, maximum):
    with pytest.raises(BenchmarkError):
        setup_run(tmp_path, bundle, frozen, maximum=maximum)


def test_generation_and_transport_drift_rejected(tmp_path, bundle, frozen):
    journal, clients, transport = setup_run(tmp_path, bundle, frozen)
    clients[MODEL].generation = replace(clients[MODEL].generation, temperature=0.5)
    with pytest.raises(BenchmarkError):
        run(bundle, frozen, journal, clients)
    assert transport.calls == 0


def test_truncation_exportable_but_invalid(tmp_path, bundle, frozen):
    async def partial(payload):
        return Completion(
            payload["model"], "partial", "unfinished", "length", Usage(40, 256, 0, 240)
        )

    journal, clients, _ = setup_run(tmp_path, bundle, frozen, transport=CountingTransport(partial))
    run(bundle, frozen, journal, clients)
    card = scorecard(bundle, frozen, execution_snapshot(journal))
    assert card["validity"]["status"] == "INVALID" and card["groups"][-1]["truncated"] == 1
    assert "INVALID" in leaderboard(card)


def test_snapshot_load_is_readonly_and_bounded(tmp_path, finished, bundle, frozen):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(finished[0]))
    assert load_execution(path, bundle, frozen) == finished[0]
    path.write_bytes(b"x" * 32_000_001)
    with pytest.raises(BenchmarkError):
        load_execution(path, bundle, frozen)


def test_replay_receipt_keeps_original_usage_but_no_new_cost(tmp_path, bundle, frozen):
    journal, clients, transport = setup_run(
        tmp_path, bundle, frozen, variants=["A5"], replay=ReplayPolicy(True)
    )
    prepared = prepare_probe(
        bundle, frozen, journal.manifest, journal.manifest.slots[0]["probe_id"]
    )
    client = clients[MODEL]
    original = asyncio.run(
        client.complete(
            request_from_wire(prepared["request"]),
            BudgetConfig(input_cap=900),
            scope=bundle.job("Synthetic question").arguments["pinned_facts"].scope,
            security_scope=journal.profile["security_scope"],
            snapshot_revision=journal.profile["snapshot_revision"],
            policy_version=journal.execution_id,
        )
    )
    assert run(bundle, frozen, journal, clients)["status"] == "FINISHED"
    payload = execution_snapshot(journal)
    receipt = payload["entries"][0]["receipt"]["result"]
    assert receipt["status"] == "replay" and receipt["replay_of"] == original.attempt_ids[0]
    card = scorecard(bundle, frozen, payload)
    assert card["groups"][0]["new_cost_microusd"] == 0
    assert card["groups"][0]["observed_attempt_usage"]["attempts"] == 0
    assert transport.calls == 1


def test_coordinated_receipt_request_key_tamper_is_rejected(finished, bundle, frozen):
    payload = deepcopy(finished[0])
    entry = next(e for e in payload["entries"] if e["receipt"])
    entry["receipt"]["result"]["request_key"] = "wrong-request"
    for row in entry["receipt"]["ledger_rows"]:
        row["request_key"] = "wrong-request"
    payload["digest"] = fingerprint({k: v for k, v in payload.items() if k != "digest"})
    with pytest.raises(BenchmarkError, match="different assembled request"):
        validate_execution(bundle, frozen, payload)


def test_model_swap_cli_and_resume(tmp_path, bundle, frozen, capsys):
    args = [
        "model-swap",
        "--run-dir",
        str(tmp_path / "run"),
        "--fact",
        "shard",
        "--budget",
        "900",
        "--variant",
        "A5",
    ]
    assert main(args + ["--snapshot", str(tmp_path / "one.json")]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["calls"] == 2 and first["real_inference_calls"] == 0
    payload = load_execution(tmp_path / "one.json", bundle, frozen)
    assert len(payload["manifest"]["models"]) == 2
    assert main(args + ["--snapshot", str(tmp_path / "two.json")]) == 0
    assert json.loads(capsys.readouterr().out)["calls"] == 0
    assert main(args + ["--snapshot", str(tmp_path / "two.json")]) == 1


def test_missing_snapshot_and_duplicate_entries_fail(tmp_path, finished, bundle, frozen):
    with pytest.raises(BenchmarkError):
        load_execution(tmp_path / "missing.json", bundle, frozen)
    payload = deepcopy(finished[0])
    payload["entries"].append(deepcopy(payload["entries"][0]))
    payload["digest"] = fingerprint({k: v for k, v in payload.items() if k != "digest"})
    with pytest.raises(BenchmarkError):
        validate_execution(bundle, frozen, payload)


def test_compact_snapshot_export_never_overwrites(tmp_path, finished, bundle, frozen):
    path = tmp_path / "snapshot.json"
    save_execution(path, finished[0])
    raw = path.read_bytes()
    assert raw.count(b"\n") == 1
    assert load_execution(path, bundle, frozen) == finished[0]
    with pytest.raises(BenchmarkError):
        save_execution(path, finished[0])
    assert path.read_bytes() == raw


def test_oversized_export_leaves_no_file(tmp_path):
    path = tmp_path / "oversized.json"
    with pytest.raises(BenchmarkError, match="export limit"):
        save_execution(path, {"large": "x" * 32_000_000})
    assert not path.exists()
