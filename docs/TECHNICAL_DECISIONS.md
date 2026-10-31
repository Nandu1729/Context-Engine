# Technical decisions

Owner decisions remain in [brain/DECISIONS.md](../brain/DECISIONS.md) (D001–D108);
they take precedence. This file records engineering decisions and the trade-offs
behind them. "Proposed" means it needs an owner decision.

## T1 — Rolling prefix summaries are opt-in (0.10.0, implemented)

**Problem.** A summary was reused only when it covered exactly the omitted history,
which changes every turn, and the memory store deleted summaries on every append.
SUMMARIZE never contributed in real use.

**Decision.** Add `SummarySnapshot.covers_prefix`, `PrefixSummaryPolicy` and
`context_engine.summaries.update_summary`. A summary may cover the oldest omitted
turns; newer omitted turns stay unsummarized (RETRIEVE can still recover them) until
the caller refreshes it. Generation is an explicit caller step between assemblies,
so `assemble_context` still never calls a model.

**Alternatives.** (a) Regenerate the summary inside assembly: hides a model call and
its cost/latency in the hot path, against the "no hidden inference" rule. (b) Relax
exact matching for all policies: silently changes default behavior and historical
reproducibility. (c) Summaries keyed by turn watermark only: weaker lineage; the
prefix rule still verifies every covered source hash.

**Default behavior.** `FrozenSummaryPolicy` and `MemoryStore.assemble()` without
`summary_prefix=True` are unchanged except one storage rule: appending or deleting a
turn the summary does not cover no longer deletes the summary (lineage is still
re-verified on every read, and changing a covered turn still removes it).

## T2 — Enable `recover_capped_window` by default (accepted: D109, 0.11.0)

**Evidence.** `strategy-eval`: combined retention 29/31 → 31/31 at 900 tokens and
19/31 → 31/31 at 3000 tokens; turn recall 0.61 → 1.00 at 3000; ~+5–15% latency.
**Risk.** Changes default assembly output (D078 had kept it opt-in); answer
accuracy with the change is unmeasured until the approved free-tier run.
**Decision.** Owner approved (D109). The frozen harness pins `False`, so A0–A5 and
historical gates still reproduce; `strategy-eval` reports the old behavior as
`combined_no_recover`. Existing `MemoryStore` chunk indexes rebuild once, because
the index profile hashes the full retrieval config.

## T3 — Provider-independent summarizer interface (implemented)

`Summarizer` is a plain callable `(turns, previous_text) -> str`. `PromptSummarizer`
takes a `complete(messages) -> str` function, so any SDK (Groq, OpenAI, Anthropic,
local) can be wrapped without adding provider dependencies to the core.
`ExtractiveSummarizer` is a deterministic offline baseline; its weakness on
mid-message facts is documented and measured.

## T4 — Strategy comparison is separate from the frozen protocol (implemented)

`evaluation/strategies.py` reuses the frozen corpus and its configuration but is not
part of the owner-approved A0–A5 protocol, its gates, or any historical claim. It
measures context retention only and reports answer correctness as `NOT_EVALUATED`.

## T5 — Keep SQLite; defer PostgreSQL (proposed)

SQLite with WAL is right for the SDK and self-hosted service. PostgreSQL only
becomes necessary with a hosted multi-tenant API (Phase 4). The storage interface
is concentrated in `memory/store.py`; port behind the same tests when needed.

## T6 — Add semantic/hybrid retrieval (implemented as opt-in, 0.14.0, D113)

BM25 retains 31/31 on the frozen questions but only 6–7/31 (retrieval alone) and
3/31 (defaults) when the same questions are reworded with no shared words
(0.13.0 stress test). This is the lexical miss the earlier deferral waited for.
**Decision (D113).** The owner asked for the best fit rather than the earlier
BGE-small design. A measured bake-off of six models chose Model2Vec
`potion-base-8M` (MIT, ~30 MB, ~0.1 ms/chunk) with per-query min-max score fusion
(0.7 meaning + 0.3 keyword); see BENCHMARK_REPORT. It is opt-in
(`embedder=`, extra `[semantic]`), so default output is byte-identical to 0.13.0.
`FastEmbedEmbedder` (bge-small) is offered for accuracy; `FunctionEmbedder` wraps
any other model or API. **Not chosen as default:** bge-small (slower indexing,
ONNX runtime), EmbeddingGemma (1.24 GB, Gemma license), RRF fusion (hurt).
**Open:** whether hybrid should become the default once the engine can ship or
fetch a model safely, and a live accuracy run with reworded questions.

## T7 — Version bump ritual

Every source change bumps the package version, archives the previous wheel and
freeze under `archives/`, and refreezes `evaluation/data/freeze.json`, so
historical experiments keep rejecting new code. 0.10.0 archived 0.9.6 under
`archives/c11-summaries-0100/` (rebuilt from unchanged committed source).
