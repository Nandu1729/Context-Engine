"""Offline tests for the D119 stage B runner (answers + judge), on a tiny synthetic
dataset in LongMemEval's shape. Never uses the owner's key, ledger or the real dataset."""

import asyncio
import hashlib
import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import Completion, TransportFailure, Usage
from context_engine.providers.store import RuntimeStore
from context_engine.providers.transport import InceptionTransport

spec = importlib.util.spec_from_file_location(
    "longmemeval_accuracy_live_b",
    Path(__file__).resolve().parents[1] / "scripts/longmemeval_accuracy_live_b.py",
)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)

TYPES = ("knowledge-update", "multi-session", "temporal-reasoning")
FILLER = "We talked about the weather and a recipe for soup, nothing else of note."


def item(number, kind, abstain=False):
    code = f"code-{number:02d}"
    sessions = [
        [{"role": "user", "content": f"{FILLER} {i}"}, {"role": "assistant", "content": "Ok."}]
        for i in range(12)
    ]
    sessions[3][0] = {"role": "user", "content": f"My locker code is {code}.", "has_answer": True}
    return {
        "question_id": f"q{number:02d}" + ("_abs" if abstain else ""),
        "question_type": kind,
        "question": f"What is my locker code, question {number}?",
        "question_date": "2023/05/30 (Tue) 23:40",
        "answer": code,
        "answer_session_ids": ["s3"],
        "haystack_dates": [f"2023/05/{10 + i:02d} (Wed) 10:00" for i in range(12)],
        "haystack_session_ids": [f"s{i}" for i in range(12)],
        "haystack_sessions": sessions,
    }


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    items = [item(n, TYPES[n % 3]) for n in range(9)] + [item(99, TYPES[0], abstain=True)]
    data = tmp_path / "longmemeval.json"
    data.write_text(json.dumps(items))
    monkeypatch.setattr(live.lme, "DATA", data)
    monkeypatch.setattr(live.lme, "SHA256", hashlib.sha256(data.read_bytes()).hexdigest())
    monkeypatch.setattr(live, "QUESTIONS", 6)
    monkeypatch.setattr(live, "ANSWERS", 18)
    monkeypatch.setattr(live, "MAX_CALLS", 36)
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "PUBLIC", tmp_path / "public")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")

    async def forbidden(*args, **kwargs):
        pytest.fail("No network in runner tests")

    monkeypatch.setattr(InceptionTransport, "send", forbidden)
    clock = [time.time()]
    fake_time = SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    monkeypatch.setattr(live, "time", fake_time)

    async def advance(seconds):
        clock[0] += seconds

    store = RuntimeStore(live.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    questions, slots, requests, contexts = live.build()
    # D118 baseline for the paired comparison: everything wrong in D118.
    previous = {
        (q["question_id"], s): {"strict-v1": False, "lenient-v2": False, "lenient-v3": False}
        for q in questions
        for s in ("core_default", "chatmemory_default")
    }
    monkeypatch.setattr(live, "d118_rows", lambda: previous)
    manifest = live.identity(slots)
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return SimpleNamespace(
        questions=questions,
        items={q["question_id"]: q for q in questions},
        manifest=manifest,
        requests=requests,
        contexts=contexts,
        store=store,
        advance=advance,
        clock=fake_time,
    )


class FakeTransport:
    namespace = InceptionTransport().namespace

    def __init__(self, questions, failure=None, at=1, reply=None, verdict="yes", length=()):
        self.calls, self.failure, self.at, self.length = 0, failure, at, length
        self.answers = {q["question"]: q["answer"] for q in questions}
        self.reply, self.verdict, self.payloads = reply, verdict, []

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        self.payloads.append(payload)
        assert payload["model"] == "mercury-3" and api_key == "test-only"
        assert payload["temperature"] == 0.5
        if self.failure == "invalid_response" and self.calls in (
            self.at if isinstance(self.at, tuple) else (self.at,)
        ):
            # As live call 31: a response with usage that fails parsing.
            raise TransportFailure(
                "invalid_response",
                uncertain=True,
                usage=Usage(900, 60, 0, 50)
                if payload["max_completion_tokens"] == 1024
                else Usage(100, 2, 0, 0),
            )
        if self.failure and self.calls == self.at:
            raise TransportFailure(
                self.failure, uncertain=False, retryable=self.failure == "rate_limit"
            )
        if payload["max_completion_tokens"] == 64:  # Judge.
            assert payload["reasoning_effort"] == "instant" and len(payload["messages"]) == 1
            assert "Is the model response correct? Answer yes or no only." in str(payload)
            return Completion("mercury-3", f"t-{self.calls}", self.verdict, "stop", Usage(300, 1))
        assert payload["max_completion_tokens"] == 1024 and payload["reasoning_effort"] == "low"
        if self.calls in self.length:  # Thinking used the whole limit: empty answer.
            return Completion(
                "mercury-3", f"t-{self.calls}", "", "length", Usage(900, 1024, 0, 1024)
            )
        answer = self.reply or self.answers[payload["messages"][-1]["content"]]
        return Completion("mercury-3", f"t-{self.calls}", answer, "stop", Usage(900, 60, 0, 50))


def run(x, transport, **kwargs):
    clients = [
        ProviderClient(
            store=x.store,
            quota=live.POLICY,
            prices=live.PRICES,
            api_key="test-only",
            generation=generation,
            retries=live.RETRIES,
            transport=transport,
            clock=x.clock.time,
        )
        for generation in (live.ANSWER, live.JUDGE)
    ]
    return asyncio.run(
        live.dispatch(x.manifest, x.requests, x.items, clients, sleep=x.advance, **kwargs)
    )


def test_same_questions_and_three_arms(experiment):
    ids = [q["question_id"] for q in experiment.questions]
    assert len(ids) == 6 and not any(i.endswith("_abs") for i in ids)
    slots = experiment.manifest["slots"]
    assert [s["arm"] for s in slots[:3]] == list(live.ARMS)
    assert all(s["estimated_tokens"] <= live.ARMS[s["arm"]]["budget"] for s in slots)
    assert experiment.manifest["system"] == live.SYSTEM


def test_full_run_judges_every_answer_and_resumes(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "finished" and transport.calls == 36
    assert run(experiment, transport) == "finished" and transport.calls == 36  # No resend.
    judge = transport.payloads[18]["messages"][0]["content"]
    assert judge.startswith("I will give you a question, a correct answer")
    assert "Model Response: code-" in judge
    value, private, disagreements = live.report(
        experiment.manifest, experiment.questions, experiment.contexts
    )
    assert value["status"] == "COMPLETE"
    for arm in live.ARMS:
        group = value["results"][arm]
        assert group["answered"] == group["judged"] == 6 and group["empty"] == 0
        for name in live.GRADER_NAMES:
            assert group[name]["correct"] == 6
        assert group["paired_vs_d118"]["lenient-v3"]["improved"] == 6
    assert disagreements == [] and len(private) == 18
    assert "code-0" not in json.dumps(value)  # Answers stay private.


def test_judge_disagreements_are_reported(experiment):
    transport = FakeTransport(experiment.questions, verdict="No.")
    assert run(experiment, transport) == "finished"
    value, _, disagreements = live.report(
        experiment.manifest, experiment.questions, experiment.contexts
    )
    assert value["results"]["core_default"]["judge"]["correct"] == 0
    assert len(disagreements) == 10 and all(d["lenient-v3"] for d in disagreements)


def test_wrong_answers_get_the_stage_a_breakdown(experiment):
    transport = FakeTransport(experiment.questions, reply="unknown", verdict="no")
    assert run(experiment, transport) == "finished"
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    group = value["results"]["chatmemory_default"]
    assert group["wrong_lenient_v2"] == 6 and group["unknown_replies"] == 6
    assert sum(group["groups"].values()) == 6


def test_max_slots_pauses_then_resumes(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport, max_slots=10) == "paused" and transport.calls == 10
    assert all(p["max_completion_tokens"] == 1024 for p in transport.payloads)  # Answers first.
    assert run(experiment, transport) == "finished" and transport.calls == 36


@pytest.mark.parametrize(
    "failure,outcome",
    [("billing_or_quota", "stopped_billing_or_quota"), ("rate_limit", "stopped_rate_limit")],
)
def test_billing_and_rate_limit_stop_without_retry(experiment, failure, outcome):
    transport = FakeTransport(experiment.questions, failure)
    assert run(experiment, transport) == outcome
    assert run(experiment, transport) == "preserved_error" and transport.calls == 1


def test_zero_token_rejection_is_skipped_and_not_judged(experiment):
    transport = FakeTransport(experiment.questions, "provider_rejected", at=2)
    assert run(experiment, transport) == "finished" and transport.calls == 35
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert sum(g["rejected"] for g in value["results"].values()) == 1


def test_spend_cap_stops_before_sending(experiment, monkeypatch):
    monkeypatch.setattr(live, "CAP_MICROUSD", 1)
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "cap_would_exceed" and transport.calls == 0


def test_runner_limits_match_approval():
    assert (live.QUESTIONS, live.SEED, live.ANSWERS, live.MAX_CALLS) == (95, 118, 285, 570)
    assert live.TOTAL_CALLS == 600 and live.CAP_MICROUSD == 300_000 and live.MAX_REJECTIONS == 10
    assert (live.ANSWER.reasoning_effort, live.ANSWER.max_completion_tokens) == ("low", 1024)
    assert (live.JUDGE.reasoning_effort, live.JUDGE.max_completion_tokens) == ("instant", 64)
    assert live.ANSWER.model == live.JUDGE.model == "mercury-3"
    assert live.RETRIES.max_attempts == 1 and live.POLICY.daily_budget_microusd == 300_000
    assert live.ARMS["core_default"] == {
        "budget": 3000,
        "reserve": 280,
        "top_k": 4,
        "diverse_turns": False,
    }
    assert live.ARMS["chatmemory_default"] == {
        "budget": 3000,
        "reserve": 1200,
        "top_k": 13,
        "diverse_turns": True,
    }
    assert live.ARMS["chatmemory_8000"] == {
        "budget": 8000,
        "reserve": int(8000 * 0.4),
        "top_k": int(8000 * 0.4) // 90,
        "diverse_turns": True,
    }
    assert live.LEDGER.name == "longmemeval-d119-account.sqlite"  # Separate ledger.
    assert "9e0b455f4ef0e2ab8f2e582289761153549043fc" in live.JUDGE_SOURCE
    assert set(live.JUDGE_TEMPLATES) == {
        "single-session-user",
        "single-session-assistant",
        "multi-session",
        "temporal-reasoning",
        "knowledge-update",
        "single-session-preference",
    }


def test_chatmemory_8000_matches_chat_memory_settings(tmp_path):
    from context_engine import ChatMemory

    memory = ChatMemory(tmp_path / "memory.sqlite", budget=8000)
    budget = memory._budget(8000)
    retrieval = memory._retrieval(budget)
    assert budget.retrieval_reserve == live.ARMS["chatmemory_8000"]["reserve"]
    assert retrieval.top_k == live.ARMS["chatmemory_8000"]["top_k"]


def test_invalid_responses_are_counted_wrong_not_resent_and_run_continues(experiment):
    transport = FakeTransport(experiment.questions, "invalid_response", at=(4, 7))
    assert run(experiment, transport) == "finished" and transport.calls == 18 + 16
    assert run(experiment, transport) == "finished" and transport.calls == 34  # No resend.
    value, private, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    group = value["results"]["core_default"]  # Numbers 3 and 6: questions 2 and 3, core arm.
    assert group["answered"] == 6 and group["accepted_errors"] == 2 and group["rejected"] == 0
    assert group["judged"] == 4 and group["judge"]["of"] == 6
    for name in live.GRADER_NAMES:
        assert group[name]["correct"] == 4
    assert group["groups"]["invalid_response"] == 2 and len(private) == 16
    assert [i["slot"] for i in value["invalid_responses"]] == [3, 6]
    assert value["invalid_responses"][0]["raw"] == "not_saved"


def test_too_many_invalid_responses_stop(experiment, monkeypatch):
    monkeypatch.setattr(live, "MAX_INVALID_RESPONSES", 1)
    transport = FakeTransport(experiment.questions, "invalid_response", at=(2, 4))
    assert run(experiment, transport) == "stopped_invalid_response" and transport.calls == 4
    assert run(experiment, transport) == "too_many_invalid_responses" and transport.calls == 4


def test_judge_reply_without_text_counts_no_and_run_continues(experiment):
    transport = FakeTransport(experiment.questions, "invalid_response", at=20)
    assert run(experiment, transport) == "finished" and transport.calls == 36
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    group = value["results"]["chatmemory_default"]  # Number 19 judges answer 1.
    assert group["judge_no_text"] == 1 and group["judged"] == 6
    assert group["judge"] == {"correct": 5, "of": 6, "wilson95": live.wilson(5, 6)}
    assert group["lenient-v3"]["correct"] == 6 and group["accepted_errors"] == 0


def test_too_many_judge_replies_without_text_stop(experiment, monkeypatch):
    monkeypatch.setattr(live, "MAX_INVALID_JUDGE", 1)
    transport = FakeTransport(experiment.questions, "invalid_response", at=(20, 22))
    assert run(experiment, transport) == "stopped_invalid_response" and transport.calls == 22
    assert run(experiment, transport) == "too_many_invalid_responses" and transport.calls == 22


def test_capture_saves_only_failing_raw_bodies(tmp_path, monkeypatch):
    path = tmp_path / "raw-invalid-005.json"
    monkeypatch.setitem(live.CAPTURE, "path", path)
    body = {
        "id": "r1",
        "object": "chat.completion",
        "model": "mercury-3",
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": None}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    }
    raw = json.dumps(body).encode()
    with pytest.raises(live.TransportFailure):
        live.capturing_parse(raw, "mercury-3")
    assert path.read_bytes() == raw and oct(path.stat().st_mode)[-3:] == "600"
    assert live.describe_raw(raw) == {
        "finish_reason": "stop",
        "content": "null",
        "content_chars": None,
        "tool_calls": 0,
        "message_keys": ["content", "role"],
        "model": "mercury-3",
    }
    good = json.dumps(
        body
        | {"choices": [{**body["choices"][0], "message": {"role": "assistant", "content": "ok"}}]}
    ).encode()
    path.unlink()
    assert live.capturing_parse(good, "mercury-3").content == "ok" and not path.exists()


def test_manifest_from_the_runtime_runner_is_accepted(experiment):
    expected = experiment.manifest
    live.require_manifest(expected | {"runner_sha256": live.RUNTIME_RUNNER_SHA256}, expected)
    with pytest.raises(ValueError):
        live.require_manifest(expected | {"runner_sha256": "0" * 64}, expected)
    with pytest.raises(ValueError):
        live.require_manifest(expected | {"seed": 1}, expected)


def test_amendment_limits():
    assert live.MAX_INVALID_RESPONSES == live.MAX_INVALID_JUDGE == 10
    assert live.RUNTIME_RUNNER_SHA256.startswith("a06d5473")


def test_out_of_tokens_answers_count_wrong_and_are_not_judged(experiment):
    transport = FakeTransport(experiment.questions, length=(1, 4))
    assert run(experiment, transport) == "finished" and transport.calls == 18 + 16
    value, private, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    group = value["results"]["core_default"]
    assert group["answered"] == 6 and group["out_of_tokens"] == 2 and group["empty"] == 2
    assert group["judged"] == 4 and group["groups"]["out_of_tokens"] == 2
    for name in live.GRADER_NAMES:
        assert group[name]["correct"] == 4
    assert len(private) == 16
