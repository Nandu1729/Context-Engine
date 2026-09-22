"""Offline probe preparation through the public engine, with independent evidence grading."""

import json
from dataclasses import dataclass
from datetime import datetime

from ..config import BudgetConfig, CapConfig, RetrievalConfig, TokenizerConfig
from ..layers.summarize import SummarySnapshot
from ..models import BlockKind, ChatRequest, Message, Role, canonical_json
from ..pipeline import AssembledContext, assemble_context
from ..tokens import TiktokenCounter
from .corpus import Bundle, aliases, strict_json
from .grading import present
from .protocol import Manifest, check_manifest, variant_options


@dataclass(frozen=True)
class BackgroundPolicy:
    content: str
    version: str
    created_at: datetime

    def get_summary(self, history, scope, at):
        return SummarySnapshot.from_history(
            scope=scope,
            content=self.content,
            history=history,
            policy_version=self.version,
            created_at=self.created_at,
        )


def evidence_locations(result: AssembledContext, fact: dict, history) -> tuple[str, ...]:
    """Match the actual rendered evidence at the declared source, not just any lineage tag."""
    values = aliases(fact)
    original = next(t for t in history if t.turn_id == fact["source_turn_id"])
    index = next(
        i for i, m in enumerate(original.messages) if m.message_id == fact["source_message_id"]
    )
    locations = []
    for block in result.blocks:
        sources = [
            s
            for s in block.sources
            if (s.turn_id, s.message_id) == (fact["source_turn_id"], fact["source_message_id"])
        ]
        if not sources or not block.content:
            continue
        for source in sources:
            source.extract(original)
        if block.kind == BlockKind.RETRIEVED:
            for item in json.loads(block.content):
                if (item["turn"], item["message"]) != (
                    fact["source_turn_id"],
                    fact["source_message_id"],
                ):
                    continue
                if any(
                    (s.start, s.end) == (item["start"], item["end"])
                    and s.extract(original) == item["text"]
                    for s in sources
                ) and present(item["text"], values):
                    locations.append("retrieved")
        elif block.kind == BlockKind.WINDOW:
            for item in json.loads(block.content):
                if item["turn"] == fact["source_turn_id"] and present(
                    item["messages"][index]["content"], values
                ):
                    locations.append("window")
    return tuple(dict.fromkeys(locations))


def prepare_probe(bundle: Bundle, frozen: dict, manifest: Manifest, probe_id: str) -> dict:
    check_manifest(bundle, frozen, manifest)
    return _prepare_validated(bundle, manifest.slot(probe_id))


def _prepare_validated(bundle: Bundle, slot: dict) -> dict:
    """Internal after manifest/preflight. No expected values are passed to the engine."""
    fact, p, summary = (
        bundle.fact(slot["fact_id"]),
        bundle.get("protocol"),
        bundle.get("summary_fixture"),
    )
    job = bundle.job(fact["question"])
    history, pins = job.arguments["history"], job.arguments["pinned_facts"]
    counter = TiktokenCounter(TokenizerConfig(**p["tokenizer"]))
    budget = BudgetConfig(
        input_cap=slot["budget"],
        completion_reservation=p["generation"]["max_completion_tokens"],
        **p["budget"],
    )
    raw_request = ChatRequest(
        (
            Message("raw:system", Role.SYSTEM, job.arguments["system"]),
            *(m for turn in history for m in turn.messages),
            Message("raw:question", Role.USER, fact["question"]),
        )
    )
    raw_estimate = counter.count_request(raw_request)
    diagnostics = None
    if slot["variant"] == "A0":
        request, estimate = raw_request, raw_estimate
        locations = (
            ("raw",)
            if present(
                next(
                    m.content
                    for t in history
                    if t.turn_id == fact["source_turn_id"]
                    for m in t.messages
                    if m.message_id == fact["source_message_id"]
                ),
                aliases(fact),
            )
            else ()
        )
    else:
        result = assemble_context(
            history,
            fact["question"],
            pins,
            budget,
            system=job.arguments["system"],
            at=job.arguments["at"],
            token_counter=counter,
            cap_config=CapConfig(**p["cap"]),
            retrieval_config=RetrievalConfig(**p["retrieval"]),
            summary_policy=BackgroundPolicy(
                summary["content"],
                summary["policy_version"],
                datetime.fromisoformat(summary["created_at"]),
            ),
            options=variant_options(bundle, slot["variant"]),
        )
        request, estimate, diagnostics = (
            result.request,
            result.diagnostics.estimate,
            result.diagnostics.to_dict(),
        )
        locations = evidence_locations(result, fact, history)
    fits = estimate.estimated_tokens <= budget.input_allowance
    record = {
        **slot,
        "state": "prepared" if fits else "non_fit",
        "request": request.to_wire(),
        "estimate": estimate.to_dict(),
        "input_allowance": budget.input_allowance,
        "raw_estimated_tokens": raw_estimate.estimated_tokens,
        "raw_serialized_tokens": raw_estimate.serialized_tokens,
        "fact_present": any(present(m.content, aliases(fact)) for m in request.messages),
        "retained_evidence": bool(locations),
        "evidence_locations": list(locations),
        "diagnostics": diagnostics,
        "answer": None,
        "answer_correct": None,
        "finish_reason": None,
        "error_code": None,
        "response_origin": None,
        "provider_request_id": None,
        "replay_of": None,
        "provider_usage": None,
    }
    return strict_json(canonical_json(record))
