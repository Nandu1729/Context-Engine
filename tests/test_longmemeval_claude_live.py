"""Offline tests for the D123 Claude runner (stage B runner, patched), on a tiny synthetic
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
from context_engine.providers.transport import AnthropicTransport

spec = importlib.util.spec_from_file_location(
    "longmemeval_claude_live",
    Path(__file__).resolve().parents[1] / "scripts/longmemeval_claude_live.py",
)
claude = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claude)
claude.patch()
live = claude.b

FABLE, OPUS = "claude-fable-5-1", "claude-opus-5-5"
TYPES = ("knowledge-update", "multi-session", "temporal-reasoning")
FILLER = "We talked about the weather and a recipe for soup, nothing else of note."
STAGE_B_ARMS = ("core_default", "chatmemory_default", "chatmemory_8000")


def item(number, kind):
    code = f"code-{number:02d}"
    sessions = [
        [{"role": "user", "content": f"{FILLER} {i}"}, {"role": "assistant", "content": "Ok."}]
        for i in range(12)
    ]
    sessions[3][0] = {"role": "user", "content": f"My locker code is {code}.", "has_answer": True}
    return {
        "question_id": f"q{number:02d}",
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
    items = [item(n, TYPES[n % 3]) for n in range(9)]
    data = tmp_path / "longmemeval.json"
    data.write_text(json.dumps(items))
    monkeypatch.setattr(live.lme, "DATA", data)
    monkeypatch.setattr(live.lme, "SHA256", hashlib.sha256(data.read_bytes()).hexdigest())
    questions, answers, stage_b = 6, 12, 18
    for module in (claude, live):
        monkeypatch.setattr(module, "QUESTIONS", questions)
        monkeypatch.setattr(module, "ANSWERS", answers)
        monkeypatch.setattr(module, "MAX_CALLS", 2 * answers + stage_b)
    monkeypatch.setattr(claude, "JUDGES", 2 * answers)
    monkeypatch.setattr(claude, "STAGE_B_ANSWERS", stage_b)
    monkeypatch.setattr(live, "RUN", tmp_path / "experiment")
    monkeypatch.setattr(live, "PUBLIC", tmp_path / "public")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "account.sqlite")
    monkeypatch.setattr(claude, "LEDGER", tmp_path / "account.sqlite")

    async def forbidden(*args, **kwargs):
        pytest.fail("No network in runner tests")

    monkeypatch.setattr(AnthropicTransport, "send", forbidden)
    clock = [time.time()]
    fake_time = SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)
    monkeypatch.setattr(live, "time", fake_time)

    async def advance(seconds):
        clock[0] += seconds

    sample = live.d118.sample(live.d118.eligible(live.d118.load_items()), questions, live.SEED)
    # Stage B: slot order question x arm; the 8000 arm of every question ran out of
    # tokens (no text, not re-judged); mercury judged every other answer "yes".
    stage_b_run = tmp_path / "stage-b"
    stage_b_run.mkdir()
    rows = []
    for q in sample:
        for arm in STAGE_B_ARMS:
            slot = len(rows)
            out = arm == "chatmemory_8000"
            rows.append(
                {
                    "slot": slot,
                    "question_id": q["question_id"],
                    "arm": arm,
                    "status": "truncated" if out else "success",
                    "out_of_tokens": out,
                    "accepted_error": False,
                    **dict.fromkeys(("strict-v1", "lenient-v2", "lenient-v3"), False),
                    "judge": not out,
                }
            )
            completion = Completion(
                "mercury-3",
                f"b-{slot}",
                "" if out else q["answer"],
                "length" if out else "stop",
                Usage(900, 60, 0, 50),
            )
            live.save(
                stage_b_run / f"receipt-{slot:03d}.json",
                {
                    "result": {
                        "status": "truncated" if out else "success",
                        "completion": completion.to_dict(),
                    }
                },
            )
    public = tmp_path / "stage-b.json"
    public.write_text(json.dumps({"rows": rows}))
    monkeypatch.setattr(claude, "STAGE_B_PUBLIC", public)
    monkeypatch.setattr(claude, "STAGE_B_RUN", stage_b_run)

    store = RuntimeStore(claude.LEDGER)
    with store.transaction() as db:
        store._account(db, live.POLICY, time.time())
    questions_, slots, requests, contexts = live.build()
    manifest = live.identity(slots)
    live.RUN.mkdir()
    live.save(live.RUN / "manifest.json", manifest)
    return SimpleNamespace(
        questions=questions_,
        slots=slots,
        items={q["question_id"]: q for q in questions_},
        manifest=manifest,
        requests=requests,
        contexts=contexts,
        store=store,
        advance=advance,
        clock=fake_time,
        stage_b_rows=rows,
    )


class FakeTransport:
    namespace = AnthropicTransport().namespace

    def __init__(self, questions, failure=None, at=(), verdict="yes"):
        self.calls, self.failure, self.at, self.verdict, self.payloads = 0, failure, at, verdict, []
        self.answers = {q["question"]: q["answer"] for q in questions}

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        self.payloads.append(payload)
        assert api_key == "test-only" and "temperature" not in payload
        judge = payload["model"] == OPUS
        if self.calls in self.at and self.failure == "empty_response":
            usage = Usage(100, 2, 0, 0) if judge else Usage(900, 60, 0, 0)
            raise TransportFailure("empty_response", uncertain=False, usage=usage)
        if self.calls in self.at:
            raise TransportFailure(self.failure, uncertain=False)
        if judge:
            assert payload["max_tokens"] == 2048 and payload["output_config"] == {
                "effort": "medium"
            }
            assert "Is the model response correct?" in payload["messages"][0]["content"][0]["text"]
            return Completion(OPUS, f"t-{self.calls}", self.verdict, "stop", Usage(300, 1))
        assert payload["model"] == FABLE and payload["max_tokens"] == 8192
        assert payload["thinking"] == {"type": "adaptive", "display": "omitted"}
        assert payload["output_config"] == {"effort": "high"} and payload["system"]
        answer = self.answers[payload["messages"][-1]["content"][-1]["text"]]
        return Completion(FABLE, f"t-{self.calls}", answer, "stop", Usage(900, 6, 0, 0))


def run(x, transport, **kwargs):
    clients = [
        ProviderClient(
            store=x.store,
            quota=live.POLICY,
            prices=prices,
            api_key="test-only",
            generation=generation,
            retries=live.RETRIES,
            transport=transport,
            clock=x.clock.time,
        )
        for generation, prices in (
            (claude.ANSWER, claude.ANSWER_PRICES),
            (claude.JUDGE, claude.JUDGE_PRICES),
        )
    ]
    return asyncio.run(
        live.dispatch(x.manifest, x.requests, x.items, clients, sleep=x.advance, **kwargs)
    )


def test_settings_reuse_stage_b_prompt_and_limits():
    stage_b = claude._load("longmemeval_accuracy_live_b")  # Unpatched copy.
    assert claude.ARMS == {arm: stage_b.ARMS[arm] for arm in claude.ARMS}
    assert (claude.ANSWER.model, claude.JUDGE.model) == (FABLE, OPUS)
    assert claude.ANSWER.thinking == claude.JUDGE.thinking == "adaptive"
    assert (claude.ANSWER.effort, claude.ANSWER.max_completion_tokens) == ("high", 8192)
    assert (claude.JUDGE.effort, claude.JUDGE.max_completion_tokens) == ("medium", 2048)
    assert live.SYSTEM == stage_b.SYSTEM and live.JUDGE_TEMPLATES == stage_b.JUDGE_TEMPLATES
    assert live.LEDGER != stage_b.LEDGER and live.RUN_ID != stage_b.RUN_ID
    assert live.POLICY.daily_budget_microusd == claude.CAP_MICROUSD
    assert live.POLICY.billing_mode == "metered" and live.RETRIES.max_attempts == 1
    assert claude.MAX_CALLS <= claude.TOTAL_CALLS == live.POLICY.rpd


def test_plan_counts_rejudges_only_for_stage_b_answers_with_text(experiment):
    plan = live.plan(experiment.questions, experiment.slots)
    assert plan["rejudge_stage_b_answers"]["calls"] == 12  # 8000 arm had no text.
    assert plan["calls_max"] == 12 + 12 + 12
    assert plan["stage_b_replies_found"] == 12 and "same_contexts_as_stage_b" not in plan
    assert 0 < plan["worst_case_total_microusd"] <= claude.CAP_MICROUSD


def test_full_run_answers_judges_and_rejudges_once(experiment):
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "finished" and transport.calls == 36
    assert run(experiment, transport) == "finished" and transport.calls == 36  # No resend.
    rejudge = transport.payloads[24]["messages"][0]["content"][0]["text"]
    assert "Model Response: code-" in rejudge
    value, private, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["status"] == "COMPLETE" and value["rejudge_status"] == "COMPLETE"
    for arm in claude.ARMS:
        result = value["results"][arm]
        assert result["judge"]["correct"] == 6 and "paired_vs_d118" not in result
        assert result["paired_vs_mercury_same_judge"]["both_right"] == 6
        assert result["paired_vs_mercury_lenient_v3"]["improved"] == 6
    stage_b = value["stage_b_rejudge"]
    assert stage_b["core_default"]["outside_judge"]["correct"] == 6
    assert stage_b["core_default"]["agree"] == 6
    assert stage_b["chatmemory_8000"]["rejudged"] == 0
    assert stage_b["chatmemory_8000"]["outside_judge"] == {"correct": 0, "of": 6} | {
        "wilson95": live.wilson(0, 6)
    }
    assert "code-0" not in json.dumps(value) and len(private) == 12
    rows = experiment.store.snapshot(live.POLICY)["attempts"]
    assert {json.loads(r["price_json"])["version"] for r in rows} == {
        claude.ANSWER_PRICES.version,
        claude.JUDGE_PRICES.version,
    }


def test_judge_disagreement_with_mercury_is_counted(experiment):
    transport = FakeTransport(experiment.questions, verdict="no")
    assert run(experiment, transport) == "finished"
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    core = value["stage_b_rejudge"]["core_default"]
    assert core["mercury_yes_outside_no"] == 6 and core["agree"] == 0
    paired = value["results"]["core_default"]["paired_vs_mercury_same_judge"]
    assert paired["both_wrong"] == 6


def test_empty_answer_is_counted_wrong_and_not_judged(experiment):
    transport = FakeTransport(experiment.questions, "empty_response", at=(1,))
    assert run(experiment, transport) == "finished" and transport.calls == 35
    value, _, _ = live.report(experiment.manifest, experiment.questions, experiment.contexts)
    assert value["results"]["core_default"]["accepted_errors"] == 1
    assert value["rows"][0]["judge"] is False


@pytest.mark.parametrize("failure", ["billing_or_quota", "rate_limit", "authentication"])
def test_provider_errors_stop(experiment, failure):
    transport = FakeTransport(experiment.questions, failure, at=(2,))
    assert run(experiment, transport) == f"stopped_{failure}" and transport.calls == 2


def test_cap_stops_before_any_call(experiment, monkeypatch):
    monkeypatch.setattr(claude, "CAP_MICROUSD", 1)
    transport = FakeTransport(experiment.questions)
    assert run(experiment, transport) == "cap_would_exceed" and transport.calls == 0


def test_pacing_uses_each_calls_price_card_with_margin(monkeypatch):
    answer = claude.ANSWER_PRICES.reserve_cost(claude.margin(1000), 8192)
    judge = claude.JUDGE_PRICES.reserve_cost(claude.margin(1000), 2048)
    assert judge < answer
    monkeypatch.setattr(claude, "CAP_MICROUSD", answer - 1)
    now = time.time()
    assert claude.pacing([], 1000, 2048, now)[0] == "ready"
    assert claude.pacing([], 1000, 8192, now)[0] == "cap_would_exceed"
    assert claude.margin(1000) == 1500


def test_key_reader_reads_only_its_line(tmp_path):
    env = tmp_path / ".env"
    env.write_text("INCEPTION_API_KEY=i\nANTHROPIC_API_KEY=sk-ant-test-only\nOTHER=x\n")
    env.chmod(0o600)
    assert claude.anthropic_key(env) == "sk-ant-test-only"
    env.write_text("INCEPTION_API_KEY=i\n")
    with pytest.raises(ValueError, match="never displayed"):
        claude.anthropic_key(env)
