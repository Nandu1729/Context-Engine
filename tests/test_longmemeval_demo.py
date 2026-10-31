"""Tiny synthetic fixtures only: never require the owner's downloaded corpus in CI."""

import copy
import hashlib
import json
from dataclasses import replace

import pytest

from context_engine.config import Settings
from context_engine.errors import RequiredContextTooLarge
from context_engine.inspection import parse_job
from scripts import longmemeval_demo as demo


def fixture_row(category="single-session-user", identifier="test-1"):
    return {
        "question_id": identifier,
        "question_type": category,
        "question": "Which route was recorded?",
        "question_date": "2023/05/30 (Tue) 23:40",
        "answer": "SECRET_LABEL",
        "answer_session_ids": ["session-one"],
        "haystack_dates": ["2023/05/20 (Sat) 02:21"],
        "haystack_session_ids": ["session-one"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "The route is cedar-52.", "has_answer": True},
                {"role": "assistant", "content": "Recorded."},
            ]
        ],
    }


def fixture_rows():
    return [
        fixture_row(
            c if c != "abstention" else "single-session-user",
            f"id-{i}" + ("_abs" if c == "abstention" else ""),
        )
        for i, c in enumerate(demo.CATEGORIES)
    ]


def source_file(tmp_path):
    path = tmp_path / "source.json"
    path.write_text(json.dumps(fixture_rows()), encoding="utf-8")
    return path


def test_conversion_preserves_text_roles_dates_and_separates_labels():
    row = fixture_row()
    before = copy.deepcopy(row)
    payload, labels = demo.convert(row)
    assert row == before
    assert len(payload["history"]) == 2
    for turn, source in zip(payload["history"], row["haystack_sessions"][0], strict=True):
        message = turn["messages"][0]
        assert message["role"] == source["role"] and message["content"] == source["content"]
        assert set(message) == {"message_id", "role", "content"}
        assert turn["timestamp"] == "2023-05-20T02:21:00+00:00"
    assert payload["at"] == "2023-05-30T23:40:00+00:00"
    assert "SECRET_LABEL" not in json.dumps(payload)
    assert labels["answer"] == "SECRET_LABEL"
    assert labels["message_mapping"][0]["has_answer"] is True
    assert labels["message_mapping"][1]["has_answer"] is None


def test_annotations_cannot_change_engine_input():
    row = fixture_row()
    original, _ = demo.convert(row)
    row["answer"] = 12345
    row["answer_session_ids"] = []
    row["haystack_sessions"][0][0]["has_answer"] = False
    changed, labels = demo.convert(row)
    assert original == changed
    assert labels["answer"] == 12345


def test_duplicate_session_ids_dates_and_source_order_are_preserved():
    row = fixture_row()
    row["haystack_session_ids"] *= 2
    row["haystack_sessions"] *= 2
    row["haystack_dates"] = ["2023/06/01 (Thu) 01:00", "2023/05/20 (Sat) 02:21"]
    payload, labels = demo.convert(row)
    assert all(labels["source_flags"].values())
    ids = [t["turn_id"] for t in payload["history"]]
    assert len(ids) == len(set(ids)) == 4
    assert payload["history"][0]["timestamp"] > payload["at"]
    assert payload["history"][2]["timestamp"] < payload["at"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(question_type=[]),
        lambda r: r.update(haystack_dates=[]),
        lambda r: r.update(question_date="PRIVATE INVALID DATE"),
        lambda r: r.update(answer=True),
        lambda r: r.update(answer_session_ids=["unknown"]),
        lambda r: r["haystack_sessions"][0][0].update(role="system"),
        lambda r: r["haystack_sessions"][0][0].update(has_answer=1),
        lambda r: r["haystack_sessions"][0][0].update(content="\ud800"),
        lambda r: r["haystack_sessions"][0][0].update(tool_calls=[]),
    ],
)
def test_bad_contracts_fail_without_echoing_values(mutation):
    row = fixture_row()
    mutation(row)
    with pytest.raises(demo.DataError) as error:
        demo.convert(row)
    assert "PRIVATE" not in str(error.value)


def test_source_json_size_duplicates_and_nonfinite_rejected(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    for value in ('[{"x":1,"x":2}]', "[NaN]", "not json"):
        path.write_text(value)
        with pytest.raises(demo.DataError):
            demo.read_source(path)
    monkeypatch.setattr(demo, "MAX_SOURCE_BYTES", 2)
    path.write_text("[1,2]")
    with pytest.raises(demo.DataError, match="source_too_large"):
        demo.read_source(path)


def test_oversized_converted_case_is_not_truncated(monkeypatch):
    monkeypatch.setattr(demo, "MAX_INSPECTION_BYTES", 10)
    with pytest.raises(demo.DataError, match="inspection_input_too_large"):
        demo.convert(fixture_row())


def test_selection_deterministic_by_category_not_answer():
    rows = fixture_rows()
    rows.insert(1, fixture_row(identifier="second-user"))
    audit, indices = demo.audit_source(rows)
    assert indices == [0, 2, 3, 4, 5]
    assert audit["row_count"] == 6
    with pytest.raises(demo.DataError, match="duplicate_question_id"):
        demo.audit_source(rows + [rows[0]])
    with pytest.raises(demo.DataError, match="missing_demo_category"):
        demo.audit_source(rows[:2])


def test_coverage_uses_wire_not_only_turn_ids():
    payload, labels = demo.convert(fixture_row())
    job = parse_job(payload, Settings())
    result = job.run()
    assert demo.retention(result, job, labels)["full_marked_messages_retained"] == 1
    wire = tuple(
        replace(m, content="[WINDOW DATA]\n[]") if m.content.startswith("[WINDOW DATA]\n") else m
        for m in result.request.messages
    )
    broken = replace(result, request=replace(result.request, messages=wire))
    assert demo.retention(broken, job, labels)["full_marked_messages_retained"] == 0
    labels["message_mapping"][0]["has_answer"] = False
    assert demo.retention(result, job, labels)["full_marked_message_fraction"] is None


def test_full_run_preserves_source_and_keeps_labels_out_of_reports(tmp_path):
    source = source_file(tmp_path)
    before = source.read_bytes()
    output = tmp_path / "new-demo"
    report = demo.run(source, output)
    assert source.read_bytes() == before
    assert report["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["source_unchanged"] and report["all_assembled"]
    assert not report["publisher_hash_matches"]  # synthetic fixture is not the publisher corpus
    assert len(report["runs"]) == report["planned_runs"] == 10
    assert report["inference_calls"] == 0 and report["answer_quality"] == "NOT_EVALUATED"
    for path in output.rglob("*"):
        if path.is_file() and path.name != "labels.json":
            assert "SECRET_LABEL" not in path.read_text()
    assert (output / "index.html").exists()
    with pytest.raises(demo.DataError, match="output_exists"):
        demo.run(source, output)


def test_assembly_errors_stay_in_denominator(tmp_path, monkeypatch):
    from context_engine.inspection import InspectionJob

    def fail(*args, **kwargs):
        raise RequiredContextTooLarge("PRIVATE BODY")

    monkeypatch.setattr(InspectionJob, "run", fail)
    report = demo.run(source_file(tmp_path), tmp_path / "new-demo")
    assert len(report["runs"]) == 10 and not report["all_assembled"]
    assert all(r["status"] == "ASSEMBLY_REJECTED" for r in report["runs"])
    assert "PRIVATE BODY" not in json.dumps(report)


def test_cli_failure_is_content_free(tmp_path, capsys):
    source = tmp_path / "source.json"
    source.write_text("PRIVATE BODY")
    assert demo.main(["--input", str(source), "--output", str(tmp_path / "new")]) == 1
    assert "PRIVATE BODY" not in capsys.readouterr().out
