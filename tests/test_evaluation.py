"""C04 frozen corpus, ablations, grading, all five gates and resume integrity."""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from context_engine import AssemblyOptions, assemble_context
from context_engine.errors import BenchmarkError, ContractError, InspectionError
from context_engine.evaluation.commands import altered_bundle, benchmark_plan, corruption_demo
from context_engine.evaluation.corpus import (
    Bundle,
    check_fixture,
    check_leakage,
    load_bundle,
    strict_json,
)
from context_engine.evaluation.grading import answer_correct, present, proportion
from context_engine.evaluation.harness import evidence_locations, prepare_probe
from context_engine.evaluation.protocol import (
    Manifest,
    check_manifest,
    check_protocol,
    freeze_record,
    load_freeze,
    make_manifest,
    preflight,
)
from context_engine.evaluation.results import (
    assess_targets,
    load_run,
    record_response,
    save_run,
    statistics,
    validate_run,
)
from context_engine.layers import CapLayer
from context_engine.models import BlockKind, KeyedPins, Pin, canonical_json
from context_engine.tokens import TiktokenCounter

DATA = Path(__file__).resolve().parents[1] / "src/context_engine/evaluation/data"


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def frozen(bundle):
    return load_freeze()  # Never silently bless new code or fixture drift in tests.


@pytest.fixture(scope="module")
def manifest(bundle, frozen):
    return make_manifest(
        bundle,
        frozen,
        facts=["shard"],
        budgets=[900],
        variants=["A0", "A5"],
        models=["openai/gpt-oss-120b"],
    )


@pytest.fixture(scope="module")
def records(bundle, frozen, manifest):
    return [prepare_probe(bundle, frozen, manifest, s["probe_id"]) for s in manifest.slots]


def test_frozen_corpus_cardinality_source_placement_and_packaged_identity(bundle, frozen):
    assert frozen == freeze_record(bundle)
    check_fixture(bundle)
    check_leakage(bundle)
    check_protocol(bundle)
    assert len(bundle.facts) == 31
    assert {
        zone: sum(f["zone"] == zone for f in bundle.facts) for zone in ("early", "middle", "late")
    } == {
        "early": 10,
        "middle": 11,
        "late": 10,
    }
    assert bundle.fact("shard")["source_turn_id"] == "t82"
    job = bundle.job(bundle.fact("shard")["question"])
    original = job.arguments["history"][81].messages[-1]
    assert original.role == "tool"
    assert "shard-19" in original.content
    assert "shard-19" not in CapLayer(TiktokenCounter()).cap_text(original.content)
    assert len(job.arguments["history"]) == 100
    changed = bundle.get("ground_truth")
    changed["facts"].clear()
    assert len(bundle.facts) == 31
    with pytest.raises(FrozenInstanceError):
        bundle.parts = ()
    with pytest.raises(BenchmarkError):
        Bundle(())


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        "null",
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1,"x":2}',
        '{"x":"\ud800"}',
        "{",
        "[" * 1200,
    ],
)
def test_bad_benchmark_json_fails_structurally(raw):
    with pytest.raises(BenchmarkError):
        strict_json(raw)


def test_missing_and_oversized_resources_are_typed(tmp_path):
    with pytest.raises(BenchmarkError):
        load_bundle(tmp_path)
    (tmp_path / "scenario.json").write_bytes(b"x" * 2_000_001)
    with pytest.raises(BenchmarkError, match="byte limit"):
        load_bundle(tmp_path)


@pytest.mark.parametrize(
    "mutation", ["missing_turn", "duplicate_turn", "duplicate_message", "metadata", "wrong_schema"]
)
def test_fixture_gate_rejects_scenario_corruption(bundle, frozen, mutation):
    scenario = bundle.get("scenario")
    if mutation == "missing_turn":
        scenario["history"].pop()
    elif mutation == "duplicate_turn":
        scenario["history"][-1]["turn_id"] = "t1"
    elif mutation == "duplicate_message":
        scenario["history"][-1]["messages"][0]["message_id"] = "m1"
    elif mutation == "metadata":
        scenario["ground_truth"] = bundle.get("ground_truth")
    else:
        scenario["schema_version"] = True
    gates = preflight(altered_bundle(bundle, "scenario", scenario), frozen)
    assert next(g for g in gates if g.gate == "V1").status == "FAIL"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_fact",
        "duplicate_fact",
        "missing_source",
        "wrong_value",
        "wrong_zone",
        "alias_collision",
        "wrong_flagship",
    ],
)
def test_truth_source_and_alias_invariants(bundle, frozen, mutation):
    truth = bundle.get("ground_truth")
    if mutation == "missing_fact":
        truth["facts"].pop()
    elif mutation == "duplicate_fact":
        truth["facts"][-1]["fact_id"] = truth["facts"][0]["fact_id"]
    elif mutation == "missing_source":
        truth["facts"][0]["source_message_id"] = "missing"
    elif mutation == "wrong_value":
        truth["facts"][0]["expected"] = "not-planted"
    elif mutation == "wrong_zone":
        truth["facts"][0]["zone"] = "late"
    elif mutation == "alias_collision":
        truth["facts"][0]["aliases"] = [truth["facts"][1]["expected"]]
    else:
        next(f for f in truth["facts"] if f["fact_id"] == "shard")["question"] = "Changed question?"
    assert (
        next(
            g
            for g in preflight(altered_bundle(bundle, "ground_truth", truth), frozen)
            if g.gate == "V1"
        ).status
        == "FAIL"
    )


@pytest.mark.parametrize("leak", ["shard-19", "SHARD 19", "ＳＨＡＲＤ-19", "shard\u200b-19"])
def test_summary_leakage_invalidates_before_inference(bundle, frozen, leak):
    summary = bundle.get("summary_fixture")
    summary["content"] += " " + leak
    changed = altered_bundle(bundle, "summary_fixture", summary)
    assert next(g for g in preflight(changed, frozen) if g.gate == "V2").status == "FAIL"
    with pytest.raises(BenchmarkError):
        make_manifest(changed, frozen)


def test_question_pins_and_extra_plant_are_invalid(bundle, frozen):
    truth = bundle.get("ground_truth")
    truth["facts"][0]["question"] += " shard-19"
    changed = altered_bundle(bundle, "ground_truth", truth)
    assert next(g for g in preflight(changed, frozen) if g.gate == "V2").status == "FAIL"
    scenario = bundle.get("scenario")
    scenario["pins"] = [{"key": "answer", "value": "shard-19", "origin": "application"}]
    changed = altered_bundle(bundle, "scenario", scenario)
    assert next(g for g in preflight(changed, frozen) if g.gate == "V2").status == "FAIL"
    scenario = bundle.get("scenario")
    scenario["history"][-1]["messages"][0]["content"] += " shard-19"
    with pytest.raises(BenchmarkError, match="outside"):
        check_fixture(altered_bundle(bundle, "scenario", scenario))


@pytest.mark.parametrize(
    "text,alias,expected",
    [
        ("shard-19", "shard-1", False),
        ("xshard-19", "shard-19", False),
        ("shard-19-extra", "shard-19", False),
        ("shard-19.2", "shard-19", False),
        ("The partition was shard-19.", "shard-19", True),
        ("(SHARD-19)", "shard-19", True),
        ("ＳＨＡＲＤ-19", "shard-19", True),
        ("shard\u200b-19", "shard-19", True),
        ("t7", "7", False),
        ("17", "7", False),
        ("7.", "7", True),
    ],
)
def test_identifier_aware_presence(text, alias, expected):
    assert present(text, (alias,)) is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("  SHARD-19\n", True),
        ('{"answer":"shard-19"}', True),
        ('{"answer":"shard-19","reason":"guess"}', False),
        ('{"answer":"wrong","answer":"shard-19"}', False),
        ('{"answer":19}', False),
        ('{"answer":["shard-19"]}', False),
        ("Not shard-19", False),
        ("shard-19 or shard-20", False),
        ("UNKNOWN", False),
        ("shard-19.", False),
        ("{bad", False),
    ],
)
def test_exact_and_structured_answer_grading(answer, expected):
    assert answer_correct(answer, ("shard-19",)) is expected


def test_denominators_and_wilson_interval():
    assert answer_correct("7", ("seven", "7"))
    assert proportion(0, 0)["rate"] is None
    estimate = proportion(27, 31)
    assert estimate["count"] == 27 and estimate["denominator"] == 31
    assert 0.70 < estimate["wilson95"][0] < estimate["rate"] < estimate["wilson95"][1] < 1
    for values in ((2, 1), (-1, 31), (True, 1), (0, -1)):
        with pytest.raises(BenchmarkError):
            proportion(*values)


def test_full_plan_has_stable_unique_slots_and_no_spend(bundle, frozen):
    m = make_manifest(bundle, frozen)
    assert len(m.slots) == 744  # Two models, two budgets, six variants, 31 facts.
    assert len({slot["probe_id"] for slot in m.slots}) == 744
    assert m == make_manifest(bundle, frozen)
    assert len([s for s in m.slots if s["budget"] == 900]) == 372
    assert m.data["protocol"]["approval"] == "owner_approved"  # Owner decision D047.
    report = benchmark_plan()
    assert report["inference_calls"] == 0 and not report["spending_authorized"]
    assert report["conservative_tokens_before_retries"] == sum(s["budget"] + 256 for s in m.slots)
    changed = m.data
    changed["protocol"]["generation"]["max_completion_tokens"] = 512
    with pytest.raises(BenchmarkError):
        check_manifest(bundle, frozen, Manifest(canonical_json(changed)))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"facts": []},
        {"facts": ["missing"]},
        {"facts": ["shard", "shard"]},
        {"budgets": [900.0]},
        {"facts": [{}]},
        {"variants": ["A9"]},
    ],
)
def test_invalid_plan_selections_are_typed(bundle, frozen, kwargs):
    with pytest.raises(BenchmarkError):
        make_manifest(bundle, frozen, **kwargs)


def test_freeze_detects_fixture_config_code_and_dependency_changes(bundle, frozen):
    for field in ("package_version", "code_hash", "python"):
        changed = deepcopy(frozen)
        changed["runtime"][field] = "drift"
        assert next(g for g in preflight(bundle, changed) if g.gate == "V5").status == "FAIL"
    changed = deepcopy(frozen)
    changed["runtime"]["dependencies"]["tiktoken"] = "drift"
    assert next(g for g in preflight(bundle, changed) if g.gate == "V5").status == "FAIL"
    protocol = bundle.get("protocol")
    protocol["cap"]["max_tokens"] += 1
    assert (
        next(
            g
            for g in preflight(altered_bundle(bundle, "protocol", protocol), frozen)
            if g.gate == "V5"
        ).status
        == "FAIL"
    )
    protocol["targets"]["correct"] = 1
    with pytest.raises(BenchmarkError):
        check_protocol(altered_bundle(bundle, "protocol", protocol))


def test_flagship_raw_nonfit_and_full_retrieval(records, bundle, frozen, manifest):
    raw, full = records
    assert raw["state"] == "non_fit" and raw["estimate"]["estimated_tokens"] > 900
    assert raw["raw_serialized_tokens"] == 15521
    assert raw["estimate"]["estimated_tokens"] == 16608
    assert full["state"] == "prepared" and full["estimate"]["estimated_tokens"] == 804
    assert full["fact_present"] and full["retained_evidence"]
    assert full["evidence_locations"] == ["retrieved"]
    assert full["answer"] is None and full["answer_correct"] is None
    assert full["diagnostics"]["retrieved_turn_ids"][0] == "t82"
    validation = validate_run(bundle, frozen, manifest, records)
    assert validation["status"] == "PREPARED"
    assert [g["status"] for g in validation["gates"]] == ["PASS", "PASS", "PASS", "NOT_RUN", "PASS"]
    assert assess_targets(manifest, records, validation)["status"] == "NOT_EVALUATED"
    stats = statistics(manifest, records)
    assert stats[0]["non_fit"] == 1 and stats[0]["fit_all_planned"]["count"] == 0
    assert stats[1]["answer_correct_all_planned"]["rate"] is None
    with pytest.raises(BenchmarkError):
        record_response(bundle, raw, answer="shard-19", finish_reason="stop", origin="test")


def test_all_ablations_use_correct_options_and_reservations(bundle, frozen):
    m = make_manifest(
        bundle, frozen, facts=["shard"], budgets=[900], models=["openai/gpt-oss-120b"]
    )
    rows = [prepare_probe(bundle, frozen, m, slot["probe_id"]) for slot in m.slots]
    assert [r["variant"] for r in rows] == ["A0", "A1", "A2", "A3", "A4", "A5"]
    assert all(r["estimate"]["estimated_tokens"] <= 900 for r in rows[1:])
    assert all(not r["fact_present"] for r in rows[1:4])
    assert all(r["fact_present"] for r in rows[4:])
    assert rows[2]["request"] == rows[3]["request"]  # Empty primary PIN fixture.
    assert all(not r["diagnostics"]["summary_used"] for r in rows[1:5])
    assert rows[5]["diagnostics"]["summary_used"]
    assert rows[1]["diagnostics"]["layer_diagnostics"][0]["reason_code"] == "layer_disabled"


def test_engine_never_receives_truth_metadata(bundle, frozen, manifest, monkeypatch):
    import context_engine.evaluation.harness as module

    called = []
    real = module.assemble_context

    def recording(history, question, pins, budget, **kwargs):
        called.append((history, question, pins, kwargs))
        assert all(key not in kwargs for key in ("expected", "aliases", "fact_id", "ground_truth"))
        assert not pins.pins and "shard-19" not in question
        assert "shard-19" not in kwargs["summary_policy"].content
        return real(history, question, pins, budget, **kwargs)

    monkeypatch.setattr(module, "assemble_context", recording)
    prepare_probe(bundle, frozen, manifest, manifest.slots[-1]["probe_id"])
    assert len(called) == 1


def test_source_lineage_does_not_claim_capped_middle_was_retained(bundle):
    job = bundle.job(bundle.fact("archive")["question"])
    result = assemble_context(
        **job.arguments,
        token_counter=TiktokenCounter(),
        options=AssemblyOptions(retrieve=False, summarize=False),
    )
    assert "t99" in result.diagnostics.kept_turn_ids
    assert not evidence_locations(result, bundle.fact("archive"), job.arguments["history"])
    # A matching value in another source is not credited as declared-source evidence.
    changed_blocks = tuple(
        replace(b, content='["archive-pine"]', sources=()) if b.kind == BlockKind.RETRIEVED else b
        for b in result.blocks
    )
    assert not evidence_locations(
        replace(result, blocks=changed_blocks), bundle.fact("archive"), job.arguments["history"]
    )


def test_separate_pin_fixture_and_disabled_options_do_not_mutate_inputs(bundle):
    fixture = bundle.get("pin_retention")
    job = bundle.job(fixture["question"])
    original_pins = KeyedPins(
        job.arguments["pinned_facts"].scope,
        (
            Pin(
                job.arguments["pinned_facts"].scope,
                fixture["key"],
                fixture["value"],
                fixture["origin"],
                effective_at=job.arguments["at"],
            ),
        ),
    )
    arguments = dict(job.arguments, history=(), pinned_facts=original_pins)
    for enabled in (False, True):
        result = assemble_context(**arguments, options=AssemblyOptions(pins=enabled))
        block = next(b for b in result.blocks if b.kind == BlockKind.PINNED)
        assert (fixture["value"] in block.content) is enabled
        assert original_pins.pins[0].value == fixture["value"]
    with pytest.raises(ContractError):
        AssemblyOptions(cap="yes")
    with pytest.raises(ContractError):
        assemble_context(**arguments, options={})


@pytest.mark.parametrize(
    "field,value",
    [
        ("fact_present", False),
        ("model", "different"),
        ("input_allowance", 800),
        ("evidence_locations", ["window"]),
        ("state", "non_fit"),
        ("answer_correct", True),
    ],
)
def test_saved_result_tampering_invalidates_request_gate(
    bundle, frozen, manifest, records, field, value
):
    changed = deepcopy(records)
    changed[-1][field] = value
    report = validate_run(bundle, frozen, manifest, changed)
    assert report["status"] == "INVALID"
    assert next(g for g in report["gates"] if g["gate"] == "V3")["status"] == "FAIL"


def test_request_tokens_duplicate_slots_unknown_slots_and_oversized_admission(
    bundle, frozen, manifest, records
):
    variants = [deepcopy(records) for _ in range(4)]
    variants[0][-1]["request"]["messages"][0]["content"] += "tampered"
    variants[1][-1]["estimate"]["estimated_tokens"] -= 1
    variants[2].append(deepcopy(records[-1]))
    variants[3][-1]["probe_id"] = "unknown"
    for rows in variants:
        assert validate_run(bundle, frozen, manifest, rows)["status"] == "INVALID"
    raw = deepcopy(records[0])
    raw["state"] = "prepared"
    assert validate_run(bundle, frozen, manifest, [raw, records[1]])["status"] == "INVALID"


@pytest.mark.parametrize(
    "answer,correct", [("shard-19", True), ("shard-1", False), ("UNKNOWN", False)]
)
def test_fact_presence_and_answer_grade_are_independent(
    bundle, frozen, manifest, records, answer, correct
):
    response = record_response(
        bundle, records[-1], answer=answer, finish_reason="stop", origin="test"
    )
    assert response["fact_present"] and response["answer_correct"] is correct
    result = validate_run(bundle, frozen, manifest, [records[0], response])
    assert result["status"] == "TEST_ONLY"
    assert all(g["status"] == "PASS" for g in result["gates"])
    assert assess_targets(manifest, [records[0], response], result)["status"] == "NOT_EVALUATED"


def test_guess_without_evidence_remains_distinct(bundle, frozen):
    m = make_manifest(
        bundle,
        frozen,
        facts=["shard"],
        variants=["A1"],
        budgets=[900],
        models=["openai/gpt-oss-120b"],
    )
    prepared = prepare_probe(bundle, frozen, m, m.slots[0]["probe_id"])
    assert not prepared["fact_present"]
    for answer in ("shard-19", "wrong"):
        response = record_response(
            bundle, prepared, answer=answer, finish_reason="stop", origin="test"
        )
        assert response["answer_correct"] is (answer == "shard-19")
        assert not response["retained_evidence"]


def test_truncation_missing_dispositions_errors_and_replay_provenance(
    bundle, frozen, manifest, records
):
    truncated = record_response(
        bundle, records[-1], answer="shard-", finish_reason="length", origin="test"
    )
    report = validate_run(bundle, frozen, manifest, [records[0], truncated])
    assert report["status"] == "INVALID"
    assert next(g for g in report["gates"] if g["gate"] == "V4")["status"] == "FAIL"
    missing = validate_run(bundle, frozen, manifest, [records[0]])
    assert missing["status"] == "INTERRUPTED" and len(missing["pending_probe_ids"]) == 1
    error = record_response(
        bundle, records[-1], answer=None, finish_reason="error", origin="test", error_code="timeout"
    )
    assert error["answer_correct"] is None and error["provider_usage"] is None
    rows = [records[0], error]
    assert validate_run(bundle, frozen, manifest, rows)["status"] == "TEST_ONLY"
    stat = statistics(manifest, rows)[-1]
    assert stat["errors"] == 1 and stat["answer_correct_all_planned"]["rate"] == 0
    assert stat["answer_correct_completed"]["rate"] is None
    with pytest.raises(BenchmarkError):
        record_response(
            bundle,
            records[-1],
            answer="shard-19",
            finish_reason="stop",
            origin="replay",
            provider_request_id="r1",
        )
    with pytest.raises(BenchmarkError):
        record_response(bundle, records[-1], answer="shard-19", finish_reason="stop", origin="live")
    with pytest.raises(BenchmarkError):
        record_response(
            bundle,
            records[-1],
            answer="shard-19",
            finish_reason="stop",
            origin="test",
            provider_usage={"input_tokens": 10, "output_tokens": 2, "cached_input_tokens": 11},
        )


def test_resume_roundtrip_pending_ids_no_overwrite_and_tamper_rejection(
    tmp_path, bundle, frozen, manifest, records
):
    path = tmp_path / "run.json"
    save_run(path, bundle, frozen, manifest, records)
    loaded, saved, validation = load_run(path, bundle, frozen)
    assert loaded == manifest and saved == records
    assert validation["pending_probe_ids"] == [records[-1]["probe_id"]]
    before = path.read_bytes()
    with pytest.raises(InspectionError, match="already exists"):
        save_run(path, bundle, frozen, manifest, records)
    assert path.read_bytes() == before
    raw = json.loads(before)
    raw["records"][-1]["request"]["messages"][-1]["content"] = "corrupt"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(BenchmarkError):
        load_run(path, bundle, frozen)
    path.write_text(before.decode()[:120], encoding="utf-8")
    with pytest.raises(BenchmarkError):
        load_run(path, bundle, frozen)


def test_all_five_deliberate_corruptions_are_invalid(bundle, frozen, manifest, records):
    report = corruption_demo(bundle, frozen, manifest, records)
    assert len(report) == 5 and all(r["status"] == "INVALID" for r in report.values())
    assert "V1" in report["malformed_fixture"]["failed_gates"]
    assert "V2" in report["summary_answer_leak"]["failed_gates"]
    assert "V5" in report["configuration_drift"]["failed_gates"]


def test_offline_benchmark_cli_ignores_environment_config_drift(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_BUDGET_TOKENS", "bad-unrelated-config")
    monkeypatch.setenv("GROQ_API_KEY", "PRIVATE_KEY")
    result = subprocess.run(
        [sys.executable, "-m", "context_engine", "benchmark-check"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "PREPARED" and report["inference_calls"] == 0
    assert all("request" not in row for row in report["probes"])
    assert "PRIVATE_KEY" not in result.stdout + result.stderr
    plan = subprocess.run(
        [sys.executable, "-m", "context_engine", "benchmark-plan"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(plan.stdout)["planned_slots"] == 744


def test_every_primary_probe_can_be_prepared_without_answer_generation(bundle, frozen):
    from context_engine.evaluation.harness import _prepare_validated

    manifest = make_manifest(
        bundle, frozen, variants=["A5"], budgets=[900], models=["openai/gpt-oss-120b"]
    )
    for slot in manifest.slots:  # One validated immutable bundle; never infer an answer.
        record = _prepare_validated(bundle, slot)
        assert record["state"] == "prepared"
        assert record["estimate"]["estimated_tokens"] <= 900
        assert record["answer_correct"] is None


@pytest.mark.parametrize(
    "name,mutation",
    [
        ("summary_fixture", {"created_at": "2099-01-01T00:00:00Z"}),
        ("summary_fixture", {"created_at": "2026-09-07"}),
        ("pin_retention", {"question": "Is it PostgreSQL?"}),
        ("pin_retention", {"value": None}),
    ],
)
def test_summary_time_and_separate_pin_contracts(bundle, frozen, name, mutation):
    value = bundle.get(name)
    value.update(mutation)
    changed = altered_bundle(bundle, name, value)
    assert next(g for g in preflight(changed, frozen) if g.gate == "V1").status == "FAIL"


def test_cli_opt_in_export_and_invalid_custom_fixture(tmp_path):
    import shutil

    target = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "context_engine",
            "benchmark-check",
            "--show-content",
            "--output",
            str(target),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert json.loads(target.read_text()) == report
    assert report["content_included"] and all("request" in r for r in report["probes"])
    directory = tmp_path / "corrupt"
    shutil.copytree(DATA, directory)
    summary = json.loads((directory / "summary_fixture.json").read_text())
    summary["content"] = "The answer is shard-19."
    (directory / "summary_fixture.json").write_text(json.dumps(summary))
    completed = subprocess.run(
        [sys.executable, "-m", "context_engine", "benchmark-check", "--data-dir", str(directory)],
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["status"] == "INVALID" and report["inference_calls"] == 0
    assert next(g for g in report["gates"] if g["gate"] == "V2")["status"] == "FAIL"
