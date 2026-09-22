"""Bounded offline owner demonstrations, not a model benchmark runner."""

from copy import deepcopy
from dataclasses import asdict

from ..models import canonical_json
from .corpus import Bundle, load_bundle
from .harness import prepare_probe
from .protocol import load_freeze, make_manifest, preflight
from .results import assess_targets, record_response, statistics, validate_run


def altered_bundle(bundle: Bundle, name: str, value: dict) -> Bundle:
    return Bundle(
        tuple((key, canonical_json(value) if key == name else raw) for key, raw in bundle.parts)
    )


def corruption_demo(bundle, frozen, manifest, records) -> dict:
    """Synthetic fault injection on detached copies; never rewrite frozen resources."""
    result = {}
    for label, name, mutate in (
        ("malformed_fixture", "scenario", lambda data: data["history"].pop()),
        ("summary_answer_leak", "summary_fixture", lambda data: data.update(content="shard-19")),
        ("configuration_drift", "protocol", lambda data: data["cap"].update(max_tokens=36)),
    ):
        value = bundle.get(name)
        mutate(value)
        gates = preflight(altered_bundle(bundle, name, value), frozen)
        result[label] = {
            "status": "INVALID" if any(g.status == "FAIL" for g in gates) else "UNEXPECTED_PASS",
            "failed_gates": [g.gate for g in gates if g.status == "FAIL"],
        }
    bad = deepcopy(records)
    bad[-1]["request"]["messages"][-1]["content"] = "Tampered question"
    result["changed_request"] = validate_run(bundle, frozen, manifest, bad)
    bad = deepcopy(records)
    bad[-1] = record_response(
        bundle, bad[-1], answer="synthetic partial response", finish_reason="length", origin="test"
    )
    result["truncated_test_response"] = validate_run(bundle, frozen, manifest, bad)
    return result


def benchmark_check(
    *, fact="shard", budget=900, model=None, show_content=False, data_dir=None
) -> dict:
    bundle, frozen = load_bundle(data_dir), load_freeze()
    gates = preflight(bundle, frozen)
    if any(g.status == "FAIL" for g in gates):
        return {"status": "INVALID", "gates": [asdict(g) for g in gates], "inference_calls": 0}
    model = model or bundle.get("protocol")["models"][0]
    manifest = make_manifest(
        bundle, frozen, facts=[fact], budgets=[budget], variants=["A0", "A5"], models=[model]
    )
    records = [prepare_probe(bundle, frozen, manifest, slot["probe_id"]) for slot in manifest.slots]
    validation = validate_run(bundle, frozen, manifest, records)
    exported = (
        records
        if show_content
        else [{k: v for k, v in row.items() if k != "request"} for row in records]
    )
    return {
        **validation,
        "run_id": manifest.run_id,
        "fixture_hashes": bundle.hashes,
        "protocol_approval": bundle.get("protocol")["approval"],
        "inference_calls": 0,
        "content_included": show_content,
        "probes": exported,
        "statistics": statistics(manifest, records),
        "quality_acceptance": assess_targets(manifest, records, validation),
        "deliberately_invalid": corruption_demo(bundle, frozen, manifest, records),
    }


def benchmark_plan(*, data_dir=None) -> dict:
    bundle, frozen = load_bundle(data_dir), load_freeze()
    manifest = make_manifest(bundle, frozen)
    completion = bundle.get("protocol")["generation"]["max_completion_tokens"]
    return {
        "status": "PLANNED",
        "run_id": manifest.run_id,
        "manifest": manifest.data,
        "slots": list(manifest.slots),
        "planned_slots": len(manifest.slots),
        "conservative_tokens_before_retries": sum(s["budget"] + completion for s in manifest.slots),
        "inference_calls": 0,
        "spending_authorized": False,
    }
