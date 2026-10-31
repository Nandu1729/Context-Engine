"""Probe correctness tests; passing tests do not imply retrieval quality passes."""

import json

import pytest

from scripts import retrieval_quality_probe as probe


@pytest.mark.parametrize(
    "intervals,expected",
    [([(0, 3), (3, 8)], True), ([(0, 3), (4, 8)], False), ([(0, 8)], True), ([], False)],
)
def test_interval_coverage_does_not_hide_gaps(intervals, expected):
    assert probe.covered(0, 8, intervals) is expected


def test_question_system_and_wrong_source_do_not_count():
    case = probe.cases()[0]
    history, _, _ = probe.inputs(case)
    fact = case[2][0]
    messages = [{"role": "system", "content": fact}, {"role": "user", "content": fact}]
    assert probe.measure(messages, history, case[2]) == [False]
    messages.append(
        {
            "role": "user",
            "content": "[WINDOW DATA]\n"
            + json.dumps([{"turn": "t99", "messages": [{"content": fact}]}]),
        }
    )
    assert probe.measure(messages, history, case[2]) == [False]


def test_retrieved_slice_requires_exact_original():
    case = probe.cases()[0]
    history, _, _ = probe.inputs(case)
    chunk = {"turn": "t0", "message": "m0", "start": 0, "end": 3, "text": "BAD"}
    with pytest.raises(ValueError, match="source slice"):
        probe.measure(
            [{"role": "user", "content": "[RETRIEVED DATA]\n" + json.dumps([chunk])}],
            history,
            case[2],
        )


def test_missing_evidence_is_not_a_correct_abstention_claim():
    history, _, _ = probe.inputs(probe.cases()[-1])
    assert probe.measure([], history, ()) == []


@pytest.mark.parametrize("gap", [False, True])
def test_measure_uses_union_of_valid_source_slices(gap):
    case = probe.cases()[0]
    history, _, _ = probe.inputs(case)
    text = case[2][0]
    cut = 8
    intervals = [(0, cut), (cut + int(gap), len(text))]
    chunks = [
        {"turn": "t0", "message": "m0", "start": a, "end": b, "text": text[a:b]}
        for a, b in intervals
    ]
    messages = [{"role": "user", "content": "[RETRIEVED DATA]\n" + json.dumps(chunks)}]
    assert probe.measure(messages, history, case[2]) == [not gap]


def test_invalid_annotation_cannot_become_a_pass():
    history, _, _ = probe.inputs(probe.cases()[0])
    with pytest.raises(ValueError, match="annotation"):
        probe.measure([], history, ("invented source",))


def test_correct_window_source_counts():
    case = probe.cases()[0]
    history, _, _ = probe.inputs(case)
    messages = [
        {
            "role": "user",
            "content": "[WINDOW DATA]\n"
            + json.dumps([{"turn": "t0", "messages": [{"content": case[2][0]}]}]),
        }
    ]
    assert probe.measure(messages, history, case[2]) == [True]


def test_real_offline_probe_deterministic_and_labels_not_sent(monkeypatch):
    real = probe.assemble_context
    calls = []

    def observe(history, question, pins, budget, **kwargs):
        assert set(kwargs) == {"system", "at"}
        calls.append((question, budget.input_cap))
        return real(history, question, pins, budget, **kwargs)

    monkeypatch.setattr(probe, "assemble_context", observe)
    first, second = probe.run(), probe.run()
    assert first == second
    assert len(calls) == 16
    assert first["answer_quality"] == first["abstention_behavior"] == "NOT_EVALUATED"
    assert len(first["rows"]) == 8 and first["inference_calls"] == 0
    for row in first["rows"]:
        assert row["estimated_tokens"] <= row["budget"]
        assert row["retained_events"] == sum(row["event_coverage"])
        if row["case"] == "missing_evidence":
            assert row["evidence_status"] == "NOT_APPLICABLE"


def test_output_exclusive_and_metadata_only(tmp_path, monkeypatch, capsys):
    report = {"status": "DIAGNOSTIC_ONLY", "rows": []}
    monkeypatch.setattr(probe, "run", lambda: report)
    path = tmp_path / "report.json"
    assert probe.main(["--output", str(path)]) == 0
    assert json.loads(path.read_text()) == report
    with pytest.raises(FileExistsError):
        probe.main(["--output", str(path)])
    assert json.loads(capsys.readouterr().out) == report
