"""Portable synthetic tests: no owner's files, credentials, network or live claims."""

import asyncio
import copy
import time
from dataclasses import replace

import httpx
import pytest

from context_engine.budget import validate_request
from context_engine.models import ChatRequest, Message
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from scripts import longmemeval_live as live


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "configuration", lambda: None)
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(live, "RUN", tmp_path / "run")
    monkeypatch.setattr(live, "REVIEW", tmp_path / "review")
    monkeypatch.setattr(live, "SOURCE", tmp_path / "source.json")
    live.SOURCE.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(live, "SOURCE_HASH", live.file_hash(live.SOURCE))
    live.RUN.mkdir()
    live.REVIEW.mkdir()
    rows = []
    for i, cat in enumerate(live.CATEGORIES):
        for arm in ("dated", "dated_recovery"):
            path = f"{i}-{arm}.json"
            request = ChatRequest((Message("m", "user", f"Route for {cat}: café-52?"),))
            live.save(live.REVIEW / path, {"request": request.to_wire()})
            label = f"label-{i}-{arm}.json"
            live.save(live.REVIEW / label, {"answer": "LABEL_NOT_SENT"})
            estimate = validate_request(
                request=request, config=live.BUDGET, counter=live.TiktokenCounter()
            ).estimated_tokens
            rows.append(
                {
                    "row": i,
                    "question_id": f"case-{i}",
                    "category": cat,
                    "variant": arm,
                    "budget": 3000,
                    "status": "PREPARED",
                    "estimated_tokens": estimate,
                    "request_hash": live.fingerprint(request.to_wire()),
                    "paths": {"assembly": path, "labels": label},
                    "coverage": {},
                }
            )
    monkeypatch.setattr(live, "preparation", lambda: {"planned_slots": 14, "rows": rows})
    store = live.RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    manifest = live.identity()
    manifest.update(
        baseline={},
        provenance="TEST_ONLY",
        model_preflight={
            "model": live.MODEL,
            "listed": True,
            "active": True,
            "checked_at": time.time(),
        },
    )
    live.save(live.RUN / "manifest.json", manifest)
    return store, manifest


class Fake:
    namespace = live.GroqTransport().namespace

    def __init__(self, mode="answer"):
        self.calls, self.mode = 0, mode

    async def send(self, payload, api_key, timeout):
        assert "LABEL_NOT_SENT" not in str(payload)
        assert payload["max_completion_tokens"] == 256
        assert payload["model"] == live.MODEL
        assert "response_format" not in payload
        self.calls += 1
        if self.mode == "error":
            raise TransportFailure("provider_rejected", uncertain=False, retryable=False)
        return Completion(
            live.MODEL,
            f"fake-{self.calls}",
            "" if self.mode == "empty" else "café-52",
            "length" if self.mode == "truncated" else "stop",
            Usage(40, 20, 0, 0),
        )


def client(store, fake):
    return live.ProviderClient(
        store=store,
        quota=live.POLICY,
        prices=live.PRICES,
        api_key="offline",
        generation=live.GENERATION,
        retries=live.RETRIES,
        transport=fake,
    )


@pytest.mark.parametrize("mode", ["answer", "empty", "truncated"])
def test_fourteen_distinct_claims_settled_and_completed_resume_has_no_calls(run, mode):
    store, manifest = run
    fake = Fake(mode)
    provider = client(store, fake)
    assert asyncio.run(live.dispatch(manifest, provider)) == "finished"
    assert asyncio.run(live.dispatch(manifest, provider)) == "finished"
    assert fake.calls == 14
    result = live.report(manifest, live.ledger())
    assert result["provider_attempts"] == result["claims"] == 14
    assert result["charged_tokens"] == 840 and result["configured_cost_microusd"] == 0
    assert result["heldout_used"] == result["unresolved_attempts"] == 0
    assert result["answer_quality"] == "TEST_ONLY"
    assert result["official_benchmark_score"] == "NOT_EVALUATED"
    assert all(r["nonempty"] == (mode == "answer") for r in result["outcomes"])
    assert all(g["planned"] == 7 for g in result["groups"])


def test_error_is_preserved_stops_and_never_retries(run):
    store, manifest = run
    fake = Fake("error")
    provider = client(store, fake)
    assert asyncio.run(live.dispatch(manifest, provider)) == "provider_error_or_unknown_usage"
    assert asyncio.run(live.dispatch(manifest, provider)) == "preserved_error"
    assert fake.calls == 1
    assert live.report(manifest, live.ledger())["dispositions"] == {"error": 1, "not_attempted": 13}


def test_unreceipted_claim_is_never_redispatched(run):
    store, manifest = run
    execution = live.fingerprint(manifest)
    live.save(
        live.RUN / "claim-00.json",
        {
            "execution_id": execution,
            "slot": 0,
            "request_key": live.request_key(manifest["preparation"]["rows"][0], execution),
        },
    )
    fake = Fake()
    assert asyncio.run(live.dispatch(manifest, client(store, fake))) == "unreceipted_claim"
    assert fake.calls == 0 and live.report(manifest, live.ledger())["usage_uncertain"]


@pytest.mark.parametrize("mutation", ["receipt", "claim", "baseline", "runtime", "extra"])
def test_tampered_evidence_and_historical_rows_fail_closed(run, mutation):
    store, manifest = run
    asyncio.run(live.dispatch(manifest, client(store, Fake())))
    if mutation in {"receipt", "claim"}:
        path = live.RUN / f"{mutation}-00.json"
        value = live.read(path)
        if mutation == "receipt":
            value["result"]["completion"]["content"] = "altered"
        else:
            value["slot"] = 99
        path.write_text(live.canonical_json(value), encoding="utf-8")
    elif mutation == "baseline":
        manifest["baseline"]["missing-history"] = "bad-hash"
    elif mutation == "runtime":
        manifest["runtime"]["code_hash"] = "bad-hash"
    else:
        live.save(live.RUN / "claim-14.json", {})
    with pytest.raises(ValueError):
        live.inspect(manifest, live.ledger())


def test_no_overwrite_or_concurrent_run(run):
    with pytest.raises(FileExistsError):
        live.save(live.RUN / "manifest.json", {})
    with live.run_lock():
        with pytest.raises(FileExistsError), live.run_lock():
            pass
        assert (live.RUN / "runner.lock").exists()
    assert not (live.RUN / "runner.lock").exists()


@pytest.mark.parametrize("field", ["generation", "retries", "replay", "prices"])
def test_altered_dispatch_configuration_rejected_before_call(run, field):
    store, manifest = run
    fake = Fake()
    provider = client(store, fake)
    if field == "generation":
        provider.generation = replace(provider.generation, max_completion_tokens=512)
    elif field == "retries":
        provider.retries = replace(provider.retries, max_attempts=2)
    elif field == "replay":
        provider.replay = replace(provider.replay, enabled=True)
    else:
        provider.prices = replace(provider.prices, input_per_million_microusd=1)
    with pytest.raises(ValueError):
        asyncio.run(live.dispatch(manifest, provider))
    assert fake.calls == 0


def selections():
    development, runs = [], []
    for i, cat in enumerate(live.CATEGORIES):
        for j in range(2):
            row = i * 2 + j
            development.append({"row": row, "question_id": f"q-{row}", "category": cat})
            for arm in ("dated", "dated_recovery"):
                runs.append(
                    {
                        "row": row,
                        "arm": arm,
                        "category": cat,
                        "budget": 3000,
                        "partition": "development",
                        "status": "ASSEMBLED",
                        "source_flags": {"sessions_after_question": j == 0},
                    }
                )
    return {"partitions": {"development": development, "heldout": [{"row": 99}]}}, runs


def test_selection_excludes_future_and_holdout_without_quality_selection():
    split, runs = selections()
    chosen = live.select(split, runs)
    assert {r["row"] for r in chosen} == set(range(1, 14, 2))
    changed = copy.deepcopy(runs)
    for r in changed:
        r["coverage"] = {"full_marked_messages": 999}
        r["answer"] = "DO_NOT_SELECT_BY_ME"
    assert live.select(split, changed) == chosen
    split["partitions"]["heldout"].append({"row": 1})
    with pytest.raises(ValueError):
        live.select(split, runs)


def test_missing_eligible_category_fails_without_substitution():
    split, runs = selections()
    for r in runs:
        if r["category"] == "abstention":
            r["source_flags"]["sessions_after_question"] = True
    with pytest.raises(ValueError):
        live.select(split, runs)


@pytest.mark.parametrize("mode", ["active", "missing", "inactive", "redirect", "oversized"])
def test_model_preflight_bounded_readonly_no_retry(mode):
    calls = []

    def respond(request):
        calls.append(request)
        assert (
            request.method == "GET" and str(request.url) == "https://api.groq.com/openai/v1/models"
        )
        if mode == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com/secret"})
        if mode == "oversized":
            return httpx.Response(200, content=b"x" * 1_000_001)
        return httpx.Response(
            200,
            json={
                "data": []
                if mode == "missing"
                else [{"id": live.MODEL, "active": mode == "active"}]
            },
        )

    task = live.model_preflight("test-key", transport=httpx.MockTransport(respond))
    if mode == "active":
        assert asyncio.run(task)["active"]
    else:
        with pytest.raises(ValueError):
            asyncio.run(task)
    assert len(calls) == 1


def test_pacing_checks_actual_shared_usage_and_bounded_waits():
    assert live.pacing([], 5656, 1000) == ("ready", 0)
    row = {
        "state": "completed",
        "cost": 0,
        "charged_tokens": 3000,
        "created": 990,
        "settled": 995,
        "request_count": 1,
    }
    assert live.pacing([row], 5656, 1000) == ("minute_wait", 30)
    assert live.pacing([{**row, "cost": None}], 5656, 1000)[0] == "unsafe_account"
    assert live.pacing([{**row, "charged_tokens": 199000}], 5656, 1000)[0] == "daily_quota"
    assert live.pacing([], 8001, 1000)[0] == "unserviceable_reservation"
