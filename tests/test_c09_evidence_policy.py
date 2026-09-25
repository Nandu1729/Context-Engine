"""Development-only prompt preservation/accounting, NOT model accuracy tests."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

from context_engine.answers import AnswerContract
from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.errors import ContractError, RequiredContextTooLarge
from context_engine.models import KeyedPins, Message, Role, Scope, Turn
from context_engine.pipeline import AssemblyOptions, assemble_context
from context_engine.tokens import TiktokenCounter
from examples.evidence_answer_policy import EVIDENCE_POLICY, evidence_answer_policy
from examples.structured_answers import StructuredGeneration, StructuredSerializer

AT = datetime(2026, 9, 24, tzinfo=UTC)
SCOPE = Scope("policy-development", "offline")
CONTRACT = AnswerContract("ascii_identifier")
GENERATION = StructuredGeneration(model="openai/gpt-oss-20b", contract=CONTRACT)


def assemble(facts, budget, recovery):
    turns = tuple(
        Turn(f"t{i}", SCOPE, (Message(f"m{i}", Role.USER, fact),), timestamp=AT)
        for i, fact in enumerate(facts)
    )
    counter = TiktokenCounter(serializer=StructuredSerializer(GENERATION))
    result = assemble_context(
        turns, "What is the current deployment code?", KeyedPins(SCOPE),
        BudgetConfig(input_cap=budget, retrieval_reserve=0, summary_reserve=0),
        system=evidence_answer_policy(CONTRACT), at=AT, token_counter=counter,
        retrieval_config=RetrievalConfig(recover_capped_window=recovery),
        options=AssemblyOptions(summarize=False),
    )
    return result, counter


@pytest.mark.parametrize("budget", [900, 3000])
@pytest.mark.parametrize("recovery", [False, True])
@pytest.mark.parametrize("facts", [
    ("Deployment code AX-11, approved.", "Deployment code BX-22; equal conflicting record."),
    ("Old deployment code AX-11.", "Explicit update: BX-22 replaces AX-11."),
    ("Deployment code AX-11.",),
    ("Telemetry healthy. No deployment code supplied.",),
])
def test_policy_and_all_short_facts_survive_budgeting(facts, budget, recovery):
    result, counter = assemble(facts, budget, recovery)
    assert result.messages[0] == {"role": "system", "content": evidence_answer_policy(CONTRACT)}
    assert result.messages[-1]["content"] == "What is the current deployment code?"
    wire = counter.serializer.serialize(result.request)
    for fact in facts:
        assert fact in wire
    assert "response_format" in wire
    assert result.diagnostics.estimate.estimated_tokens <= budget
    assert result.diagnostics.estimate == counter.count_request(result.request)


def test_required_policy_cannot_be_silently_dropped():
    with pytest.raises(RequiredContextTooLarge):
        assemble(("Deployment code AX-11.",), 50, False)


def test_policy_is_generic_and_has_no_evidence_or_truth_argument():
    assert "OT-417" not in EVIDENCE_POLICY and "q2-" not in EVIDENCE_POLICY
    assert "mere recency is insufficient" in EVIDENCE_POLICY
    assert "explicit applicable update" in EVIDENCE_POLICY
    with pytest.raises(ContractError):
        evidence_answer_policy("untrusted text")


def test_format_validation_does_not_claim_semantic_correctness():
    # Both plausible values and UNKNOWN conform. Only external evidence can decide.
    for value in ("AX-11", "BX-22", "UNKNOWN"):
        assert CONTRACT.parse('{"answer":"' + value + '"}') == value


def test_author_visible_development_matrix_retention_does_not_regress():
    # Existing cases are development evidence, not new held-out quality scores.
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "policy_dev", root / "scripts/c09_qualification.py"
    )
    q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q)
    cases, truth, _ = q.load()  # Verifies immutable fixture/runtime hashes.
    at = datetime(2026, 9, 23, tzinfo=UTC)
    for case in cases:
        contract = AnswerContract(case["kind"])
        counter = TiktokenCounter(serializer=StructuredSerializer(
            StructuredGeneration(model="openai/gpt-oss-20b", contract=contract)
        ))
        scenario = {k: case[k] for k in (
            "id", "question", "messages", "middle_padding", "filler_turns"
        )}
        history, pins, question = q.engine_inputs(scenario, at)
        for budget in (900, 3000):
            for variant in ("CONTROL", "PRIMARY"):
                before = q.assemble(case, budget, variant, counter)
                result = assemble_context(
                    history, question, pins, BudgetConfig(input_cap=budget),
                    system=evidence_answer_policy(contract), at=at, token_counter=counter,
                    retrieval_config=RetrievalConfig(recover_capped_window=variant == "PRIMARY"),
                    options=AssemblyOptions(summarize=False),
                )
                assert result.diagnostics.estimate.estimated_tokens <= budget
                assert q.retained(case, truth[case["id"]], result) == q.retained(
                    case, truth[case["id"]], before
                )
