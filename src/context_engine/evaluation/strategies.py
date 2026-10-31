"""Offline baseline comparison on the frozen 31-fact corpus. No inference is performed.

Strategies (same frozen corpus, tokenizer and per-budget allowance):

- full_history: the raw chronological request; non-fit when over the allowance.
- recent_window: WINDOW only.
- summary_window: WINDOW + a generated extractive summary of omitted turns.
- retrieval_window: WINDOW + BM25 retrieval of omitted originals.
- combined: CAP + PIN + RETRIEVE + WINDOW + generated summary (SDK defaults, which
  since 0.11.0 include `recover_capped_window=True`: RETRIEVE restores original
  evidence that CAP removed from WINDOW turns).
- combined_no_recover: combined with `recover_capped_window=False`, the default
  before 0.11.0 and the frozen-protocol setting.

Summary and retrieval strategies receive the same optional allocation (the frozen
retrieval + summary reserves), so they compete for equal space. Ground truth is
used only after assembly, for scoring. Answer correctness needs model inference
and is reported NOT_EVALUATED here; this measures what context reaches the model.
"""

import re
import statistics
import time

from ..config import BudgetConfig, CapConfig, RetrievalConfig, TokenizerConfig
from ..errors import BenchmarkError
from ..layers.retrieve import lexical_tokens
from ..layers.summarize import PrefixSummaryPolicy
from ..models import BlockKind, ChatRequest, Message, Role
from ..pipeline import AssemblyOptions, assemble_context
from ..summaries import ExtractiveSummarizer, update_summary
from ..tokens import TiktokenCounter
from .corpus import Bundle, aliases, read_resource, strict_json
from .grading import present
from .harness import evidence_locations

SUMMARY_POLICY_VERSION = "extractive-v1"
STRATEGIES = {
    "recent_window": AssemblyOptions(cap=False, pins=False, retrieve=False, summarize=False),
    "summary_window": AssemblyOptions(cap=False, pins=False, retrieve=False, summarize=True),
    "retrieval_window": AssemblyOptions(cap=False, pins=False, retrieve=True, summarize=False),
    "combined": AssemblyOptions(),
    "combined_no_recover": AssemblyOptions(),
}
NO_RECOVER = {"combined_no_recover"}
ORDER = ("full_history", *STRATEGIES)


def _budget(protocol: dict, allowance: int, strategy: str) -> BudgetConfig:
    reserves = protocol["budget"]
    optional = reserves["retrieval_reserve"] + reserves["summary_reserve"]
    settings = dict(reserves)
    if strategy == "summary_window":
        settings.update(retrieval_reserve=0, summary_reserve=optional)
    elif strategy == "retrieval_window":  # Same optional space, all for evidence.
        settings.update(retrieval_reserve=optional, summary_reserve=0)
    return BudgetConfig(
        input_cap=allowance,
        completion_reservation=protocol["generation"]["max_completion_tokens"],
        **settings,
    )


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def _assemble(job, protocol, counter, fact, allowance, strategy, question):
    """Assemble one strategy's request; returns (result, summary source tokens)."""
    history = job.arguments["history"]
    budget = _budget(protocol, allowance, strategy)
    options = STRATEGIES[strategy]
    arguments = dict(
        system=job.arguments["system"],
        at=job.arguments["at"],
        token_counter=counter,
        cap_config=CapConfig(**protocol["cap"]),
        retrieval_config=RetrievalConfig(
            **protocol["retrieval"], recover_capped_window=strategy not in NO_RECOVER
        ),
        options=options,
    )
    pins = job.arguments["pinned_facts"]
    result = assemble_context(history, question, pins, budget, **arguments)
    summary_tokens = 0
    if options.summarize:
        reserve = budget.summary_reserve
        snapshot = update_summary(
            history,
            result.diagnostics.kept_turn_ids,
            ExtractiveSummarizer(max_characters=max(1, reserve * 3)),
            scope=pins.scope,
            policy_version=SUMMARY_POLICY_VERSION,
            created_at=job.arguments["at"],
            min_new_turns=1,
        )
        if snapshot is not None:
            covered = set(snapshot.covered_turn_ids)
            summary_tokens = sum(
                counter.count_text(m.content)
                for t in history
                if t.turn_id in covered
                for m in t.messages
            )
            result = assemble_context(
                history,
                question,
                pins,
                budget,
                summary_policy=PrefixSummaryPolicy(snapshot),
                **arguments,
            )
    return result, summary_tokens


def _probe(bundle, protocol, counter, fact, allowance, strategy, question) -> dict:
    job = bundle.job(fact["question"])
    history = job.arguments["history"]
    values = aliases(fact)
    raw = counter.count_request(
        ChatRequest(
            (
                Message("raw:system", Role.SYSTEM, job.arguments["system"]),
                *(m for turn in history for m in turn.messages),
                Message("raw:question", Role.USER, question),
            )
        )
    )
    base = {"fact_id": fact["fact_id"], "zone": fact["zone"], "raw_tokens": raw.estimated_tokens}
    if strategy == "full_history":
        fits = raw.estimated_tokens <= allowance
        return {
            **base,
            "fits": fits,
            "input_tokens": raw.estimated_tokens if fits else None,
            # Oversized raw input cannot be sent, so it retains nothing usable.
            "fact_present": fits,
            "evidence_at_source": fits,
            "fact_in_summary": False,
            "retrieved_chunks": 0,
            "source_chunks": 0,
            "source_retrieved": False,
            "summary_source_tokens": 0,
            "latency_ms": 0.0,
        }
    started = time.perf_counter()
    result, summary_tokens = _assemble(job, protocol, counter, fact, allowance, strategy, question)
    latency = (time.perf_counter() - started) * 1000
    source = fact["source_turn_id"]
    chunks = [b for b in result.blocks if b.kind == BlockKind.RETRIEVED and b.content]
    sources = [s for b in chunks for s in b.sources]
    summary = next((b for b in result.blocks if b.kind == BlockKind.SUMMARY), None)
    return {
        **base,
        "fits": True,
        "input_tokens": result.diagnostics.estimate.estimated_tokens,
        "fact_present": any(present(m.content, values) for m in result.request.messages),
        "evidence_at_source": bool(evidence_locations(result, fact, history)),
        "fact_in_summary": bool(summary and present(summary.content, values)),
        "retrieved_chunks": len(result.diagnostics.retrieved_chunk_ids),
        "source_chunks": sum(1 for s in sources if s.turn_id == source),
        "source_retrieved": source in result.diagnostics.retrieved_turn_ids,
        "summary_source_tokens": summary_tokens,
        "latency_ms": latency,
    }


def _aggregate(probes: list[dict]) -> dict:
    count = len(probes)
    fit = [p for p in probes if p["fits"]]
    retrieving = [p for p in fit if p["retrieved_chunks"]]
    reductions = [1 - p["input_tokens"] / p["raw_tokens"] for p in fit]
    latencies = [p["latency_ms"] for p in fit]
    by_zone: dict[str, list[int]] = {}
    for p in probes:
        tally = by_zone.setdefault(p["zone"], [0, 0])
        tally[0] += p["evidence_at_source"]
        tally[1] += 1
    return {
        "probes": count,
        "fit": len(fit),
        "fact_present": sum(p["fact_present"] for p in probes),
        "evidence_at_source": sum(p["evidence_at_source"] for p in probes),
        "fact_in_summary": sum(p["fact_in_summary"] for p in probes),
        "evidence_by_zone": {zone: f"{hit}/{total}" for zone, (hit, total) in by_zone.items()},
        "median_input_tokens": statistics.median(p["input_tokens"] for p in fit) if fit else None,
        "median_raw_tokens": statistics.median(p["raw_tokens"] for p in probes),
        "median_token_reduction": round(statistics.median(reductions), 4) if fit else None,
        # Chunk precision: share of retrieved chunks that come from the fact's source turn.
        "retrieval_precision": (
            round(
                statistics.mean(p["source_chunks"] / p["retrieved_chunks"] for p in retrieving), 4
            )
            if retrieving
            else None
        ),
        # Turn recall: share of probes whose source turn was retrieved at all.
        "retrieval_recall": (
            round(sum(p["source_retrieved"] for p in fit) / len(fit), 4) if retrieving else None
        ),
        "summary_source_tokens_total": sum(p["summary_source_tokens"] for p in probes),
        "median_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
        "p95_latency_ms": round(_percentile(latencies, 0.95), 3) if latencies else None,
        "answer_correct": "NOT_EVALUATED",
    }


def assemble_strategy(
    bundle: Bundle, fact: dict, allowance: int, strategy: str, *, question: str | None = None
):
    """The exact request a strategy sends for one frozen fact (for bounded live runs).

    `full_history` is not assembled; it either fits raw or is a non-fit.
    """
    if strategy not in STRATEGIES:
        raise ValueError("Unknown or non-assembled strategy")
    protocol = bundle.get("protocol")
    counter = TiktokenCounter(TokenizerConfig(**protocol["tokenizer"]))
    job = bundle.job(fact["question"])
    asked = fact["question"] if question is None else question
    result, _ = _assemble(job, protocol, counter, fact, allowance, strategy, asked)
    return result, _budget(protocol, allowance, strategy)


# Function words allowed in a paraphrase; everything else must differ from the evidence.
FUNCTION_WORDS = frozenset(
    "a again and at be before did for got how in is it many of off on once or out set the "
    "they things this to together up was were what where which with".split()
)


def _words(text: str) -> set[str]:
    tokens = lexical_tokens(text)
    parts = {p for t in tokens for p in re.split(r"[-.]", t) if p}
    return (set(tokens) | parts) - FUNCTION_WORDS


def evidence_sentence(bundle: Bundle, fact: dict) -> str:
    history = bundle.job(fact["question"]).arguments["history"]
    content = next(
        m.content for t in history for m in t.messages if m.message_id == fact["source_message_id"]
    )
    return next(s for s in re.split(r"(?<=\.)\s+", content) if fact["expected"] in s)


def paraphrase_overlaps(bundle: Bundle, questions: dict) -> dict:
    """Shared words, or shared 4-letter starts of 5+ letter words, per paraphrase."""
    found = {}
    for fact in bundle.facts:
        asked = _words(questions[fact["fact_id"]])
        evidence = _words(evidence_sentence(bundle, fact))
        shared = sorted(asked & evidence) + sorted(
            f"{a}~{e}"
            for a in asked
            for e in evidence
            if a != e and len(a) >= 5 and len(e) >= 5 and a[:4] == e[:4]
        )
        if shared:
            found[fact["fact_id"]] = shared
    return found


def load_paraphrases(bundle: Bundle) -> dict[str, str]:
    """Validated paraphrased questions for the frozen corpus (no evidence word overlap)."""
    data = strict_json(read_resource("paraphrases.json"))
    questions = data.get("questions") if isinstance(data, dict) else None
    if (
        data.get("schema_version") != 1
        or data.get("scenario_id") != bundle.get("protocol")["scenario_id"]
        or not isinstance(questions, dict)
        or set(questions) != {f["fact_id"] for f in bundle.facts}
        or not all(isinstance(q, str) and q.strip() for q in questions.values())
    ):
        raise BenchmarkError("Malformed paraphrase question set")
    if paraphrase_overlaps(bundle, questions):
        raise BenchmarkError("Paraphrased questions share words with their evidence")
    return dict(questions)


def compare_strategies(
    bundle: Bundle,
    budgets: tuple[int, ...] | None = None,
    *,
    include_probes: bool = False,
    questions: str = "original",
) -> dict:
    """Run every strategy on every frozen fact at each budget. Deterministic except latency.

    `questions="paraphrased"` asks reworded questions that share no content words with
    the evidence (lexical-retrieval stress test); scoring is unchanged.
    """
    if questions not in ("original", "paraphrased"):
        raise ValueError("questions must be 'original' or 'paraphrased'")
    asked = (
        load_paraphrases(bundle)
        if questions == "paraphrased"
        else {f["fact_id"]: f["question"] for f in bundle.facts}
    )
    protocol = bundle.get("protocol")
    budgets = tuple(protocol["budgets"]) if budgets is None else tuple(budgets)
    if not budgets or any(type(b) is not int or b <= 0 for b in budgets):
        raise ValueError("Budgets must be positive integers")
    counter = TiktokenCounter(TokenizerConfig(**protocol["tokenizer"]))
    results = []
    for allowance in budgets:
        for strategy in ORDER:
            probes = [
                _probe(bundle, protocol, counter, fact, allowance, strategy, asked[fact["fact_id"]])
                for fact in bundle.facts
            ]
            entry = {"budget": allowance, "strategy": strategy, **_aggregate(probes)}
            if include_probes:
                entry["probe_results"] = [
                    {**p, "latency_ms": round(p["latency_ms"], 3)} for p in probes
                ]
            results.append(entry)
    return {
        "status": "COMPLETE",
        "mode": "offline_strategy_comparison",
        "inference_calls": 0,
        "corpus": {"scenario_id": protocol["scenario_id"], "facts": len(bundle.facts)},
        "question_set": questions,
        "fixture_hashes": bundle.hashes,
        "summary_policy": SUMMARY_POLICY_VERSION,
        "results": results,
        "limitations": [
            "Synthetic single-scenario corpus authored with the engine; not real-world quality.",
            "Context retention only: answer correctness and faithfulness need model inference.",
            "Token counts are local estimates, not provider-billed tokens.",
            "Latency is local wall time and varies by machine.",
        ],
    }


__all__ = [
    "NO_RECOVER",
    "ORDER",
    "STRATEGIES",
    "assemble_strategy",
    "compare_strategies",
    "load_paraphrases",
    "paraphrase_overlaps",
]
