"""Synthetic, network-disabled regressions; no owner's corpus required."""

import copy
import hashlib
import json

import pytest

from context_engine.config import Settings
from context_engine.inspection import InspectionJob, parse_job
from scripts import longmemeval_demo as demo
from scripts import longmemeval_review as review


def row(cat="single-session-user", i=0):
    return {
        "question_id": f"{cat}-{i}" + ("_abs" if cat == "abstention" else ""),
        "question_type": "single-session-user" if cat == "abstention" else cat,
        "question": f"Which route for {cat} {i}?",
        "question_date": "2023/05/30 (Tue) 23:40",
        "answer": "LABEL_NOT_ENGINE_INPUT",
        "answer_session_ids": [f"source-{cat}-{i}"],
        "haystack_dates": ["2023/05/20 (Sat) 02:21"],
        "haystack_session_ids": [f"source-{cat}-{i}"],
        "haystack_sessions": [
            [
                {
                    "role": "user",
                    "content": "The route is cedar-52.",
                    "has_answer": cat != "abstention",
                }
            ]
        ],
    }


def rows():
    return [row(cat, i) for cat in review.CATEGORIES for i in range(5)]


def small_split(data, exposed):
    return review.make_split(data, exposed, development_per_category=1, heldout_per_category=2)


def test_split_is_deterministic_disjoint_and_labels_do_not_choose_good_answers():
    data = rows()
    split = small_split(data, [0])
    altered = copy.deepcopy(data)
    for r in altered:
        r["answer"] = "wrong"
        r["haystack_sessions"][0][0]["has_answer"] = False
    assert small_split(altered, [0]) == split
    all_ids = [r["row"] for part in split["partitions"].values() for r in part]
    assert sorted(all_ids) == list(range(len(data))) and len(set(all_ids)) == len(data)
    assert len(split["partitions"]["heldout"]) == 14
    assert len(split["partitions"]["development"]) == 7
    expected = dict(split)
    expected.pop("split_sha256")
    assert review.digest(expected) == split["split_sha256"]


def test_grouping_is_transitive_and_keeps_question_family_and_evidence_together():
    data = [row(i=i) for i in range(4)]
    data[1]["question_id"] = data[0]["question_id"] + "_abs"
    data[2]["answer_session_ids"] = data[1]["answer_session_ids"]
    assert sorted(review.groups(data)) == [[0, 1, 2], [3]]


def test_exposed_partner_cannot_enter_other_splits():
    data = rows()
    data[1]["answer_session_ids"] = data[0]["answer_session_ids"]
    split = small_split(data, [0])
    assert [r["row"] for r in split["partitions"]["previously_exposed"]] == [0, 1]


def test_insufficient_category_is_not_silently_reduced():
    with pytest.raises(demo.DataError, match="insufficient_split_category"):
        small_split([row()], [])


@pytest.mark.parametrize("dated,recovery", review.ARMS.values())
def test_mapping_keeps_original_messages_question_and_labels_separate(dated, recovery):
    original = row()
    saved = copy.deepcopy(original)
    payload, labels = review.mapped_input(original, dated=dated, recovery=recovery)
    assert original == saved
    assert payload["question"] == original["question"]
    assert (
        payload["history"][0]["messages"][0]["content"]
        == original["haystack_sessions"][0][0]["content"]
    )
    assert labels["answer"] == original["answer"]
    assert original["answer"] not in json.dumps(payload)
    assert payload["retrieval"]["recover_capped_window"] is recovery
    altered = copy.deepcopy(original)
    altered["answer"] = 100
    altered["answer_session_ids"] = []
    altered["haystack_sessions"][0][0]["has_answer"] = False
    assert review.mapped_input(altered, dated=dated, recovery=recovery)[0] == payload


def test_dates_are_visible_even_when_message_is_capped_and_budget_counts_them():
    original = row()
    original["haystack_sessions"][0][0]["content"] *= 100
    payload, labels = review.mapped_input(original, dated=True)
    result = parse_job(payload, Settings()).run()
    wire = json.dumps(result.messages)
    assert "session_date=2023-05-20T02:21" in wire
    assert "Question date: 2023-05-30T23:40" in wire
    assert "timezone is unspecified" in wire
    assert result.diagnostics.estimate.estimated_tokens <= 900
    score = review.coverage(result.to_dict(include_content=True), payload, labels)
    assert score["details"][0]["window_is_capped"]
    assert score["full_marked_messages"] == 0


def test_future_dates_and_order_are_not_silently_changed():
    original = row()
    original["haystack_dates"] = ["2024/05/20 (Mon) 02:21"]
    payload, labels = review.mapped_input(original, dated=True)
    assert labels["source_flags"]["sessions_after_question"]
    assert "2024-05-20T02:21" in payload["history"][0]["turn_id"]


def fake_retrieval(payload, intervals):
    t = payload["history"][0]
    m = t["messages"][0]
    chunks = [
        {
            "turn": t["turn_id"],
            "message": m["message_id"],
            "start": a,
            "end": b,
            "text": m["content"][a:b],
        }
        for a, b in intervals
    ]
    return {
        "diagnostics": {"planned_window_turn_ids": []},
        "request": {
            "messages": [{"role": "user", "content": "[RETRIEVED DATA]\n" + json.dumps(chunks)}]
        },
    }


@pytest.mark.parametrize(
    "intervals,full",
    [([(0, 5), (5, 22)], 1), ([(0, 5), (6, 22)], 0), ([(0, 10), (5, 22)], 1), ([(5, 22)], 0)],
)
def test_coverage_requires_full_contiguous_exact_text(intervals, full):
    payload, labels = review.mapped_input(row())
    # The original fixture has 22 characters.
    assert len(payload["history"][0]["messages"][0]["content"]) == 22
    result = fake_retrieval(payload, intervals)
    assert review.coverage(result, payload, labels)["full_marked_messages"] == full


def test_forged_slice_rejected_and_diagnostic_ids_alone_do_not_count():
    payload, labels = review.mapped_input(row())
    result = fake_retrieval(payload, [(0, 22)])
    result["request"]["messages"][0]["content"] = result["request"]["messages"][0][
        "content"
    ].replace("cedar", "birch")
    with pytest.raises(demo.DataError, match="invalid_retrieved_slice"):
        review.coverage(result, payload, labels)
    result = fake_retrieval(payload, [])
    result["diagnostics"]["planned_window_turn_ids"] = [payload["history"][0]["turn_id"]]
    assert review.coverage(result, payload, labels)["full_marked_messages"] == 0


def test_summary_retains_rejections_and_abstention_is_not_a_pass():
    records = [
        {
            "arm": "baseline",
            "budget": 900,
            "status": "ASSEMBLY_REJECTED",
            "source_flags": {"sessions_after_question": True},
        },
        {
            "arm": "baseline",
            "budget": 900,
            "status": "ASSEMBLED",
            "source_flags": {"sessions_after_question": False},
            "coverage": {
                "marked_messages": 0,
                "full_marked_messages": 0,
                "all_marked_messages": None,
            },
        },
    ]
    summary = review.summarize(records)[0]
    assert summary["planned"] == 2 and summary["assembled"] == summary["rejected"] == 1
    assert summary["cases_all_marked"] == 0 and summary["cases_without_marks"] == 1


def test_end_to_end_preserves_prior_and_never_executes_holdout(tmp_path, monkeypatch):
    data = rows()
    source = tmp_path / "source.json"
    source.write_text(json.dumps(data))
    raw = source.read_bytes()
    monkeypatch.setattr(demo, "PUBLISHER_SHA256", hashlib.sha256(raw).hexdigest())
    prior = tmp_path / "prior"
    demo.run(source, prior)
    before = {p.name + p.parent.name: p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    original_split = review.make_split
    monkeypatch.setattr(
        review,
        "make_split",
        lambda r, e: original_split(r, e, development_per_category=1, heldout_per_category=2),
    )
    executed = []
    original_run = InspectionJob.run

    def traced(job, **kwargs):
        executed.append(job.arguments["question"])
        return original_run(job, **kwargs)

    monkeypatch.setattr(InspectionJob, "run", traced)
    output = tmp_path / "review"
    report = review.run(source, prior, output)
    split = json.loads((output / "split.json").read_text())
    heldout = {r["row"] for r in split["partitions"]["heldout"]}
    assert not {data[i]["question"] for i in heldout} & set(executed)
    assert not {r["row"] for r in report["runs"]} & heldout
    assert report["heldout_assembled"] == report["heldout_scored"] == report["inference_calls"] == 0
    assert len(report["runs"]) == report["planned_runs"] == 96
    assert all(r["status"] == "ASSEMBLED" for r in report["runs"])
    assert source.read_bytes() == raw
    assert before == {
        p.name + p.parent.name: p.read_bytes() for p in prior.rglob("*") if p.is_file()
    }
    for p in output.rglob("*"):
        if p.is_file() and not p.name.startswith("labels-"):
            assert "LABEL_NOT_ENGINE_INPUT" not in p.read_text()
    with pytest.raises(demo.DataError, match="output_exists"):
        review.run(source, prior, output)


def test_source_identity_required_before_outputs(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(rows()))
    with pytest.raises(demo.DataError, match="unexpected_source_identity"):
        review.run(source, tmp_path / "prior", tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_mapping_limit_rejects_not_truncates(monkeypatch):
    monkeypatch.setattr(review, "MAX_INSPECTION_BYTES", 10)
    with pytest.raises(demo.DataError, match="inspection_input_too_large"):
        review.mapped_input(row(), dated=True)
