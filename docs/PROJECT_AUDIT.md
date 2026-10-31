# Project audit — 2026-10-31

Scope: whole repository at `3e3e0e4` plus uncommitted work present on disk. Findings
come from reading source, running the test suite, running the offline benchmark
check and a new offline strategy comparison. No model calls were made.

## 1. Executive summary

The directive describes a "partially completed" engine. The repository is further
along than that: a typed Python package (`context-engineering-core`, 0.9.6 at audit
time), five context layers, a one-call assembly API, SQLite durable memory with
deletion-safe restore, an authenticated local FastAPI service, a Groq provider
adapter with a replay cache and quota ledger, and a frozen benchmark harness.
There are 66 test modules (~14.7k lines) against ~9.5k lines of source, plus 106
recorded owner decisions and checkpoint reports C00–C12.

What was actually missing or broken for a developer-ready core:

| # | Finding | Priority |
|---|---|---|
| F1 | SUMMARIZE never produces a summary. It only reuses a caller-supplied snapshot whose coverage must *exactly* equal the omitted history. That history changes on every new turn, so in real conversations no summary ever applies. The SDK quickstart sets `summary_reserve=0`. | Critical |
| F2 | `MemoryStore` deletes the stored summary on every turn append, so even a correct summary could not survive one turn. | Critical (with F1) |
| F3 | No baseline comparison besides the cumulative A0–A5 ladder. The directive's summary-only and retrieval-only baselines did not exist; retrieval precision/recall was not measured. | High |
| F4 | The default pipeline loses evidence at larger budgets: CAP trims facts inside WINDOW turns and RETRIEVE skips WINDOW turns. Measured offline: 29/31 facts at 900 tokens, **19/31 at 3000 (0/10 late facts)**. The opt-in `recover_capped_window=True` restores 31/31 at both budgets. Recorded earlier as S11 without a root cause. | High (default change needs owner decision) |
| F5 | `uv run --locked pytest -q` (the README command) fails at collection: tests import `examples/`, which is only on `sys.path` under `python -m pytest`. CI uses the latter, so CI was green. | Medium |
| F6 | Combined assembly costs ~240 ms median locally against ~16 ms for retrieval+window. Most of the gap is CAP plus one extra assembly when a summary is generated. | Medium |
| F7 | Answer correctness and faithfulness can only be measured with model inference. All approved inference budgets are exhausted; live quality targets (C09) failed. | High, owner-gated |
| F8 | No hosted product surface (multi-tenant signup, API keys self-service, per-tenant rate limits, billing). The service is a self-hosted local API with operator-configured identities. | Expected at this stage |

Not found: placeholder functions, `TODO`/`FIXME`/`NotImplementedError` markers, or
broken imports in `src/`. The code is consistently typed, validates inputs, fails
closed with typed errors, and redacts provider/caller exceptions.

## 2. Repository structure

```
src/context_engine/        core package (installable)
  models.py context.py     immutable messages/turns/pins/blocks, source refs, carrier
  config.py budget.py      validated budgets, reserves, CAP/retrieval/tokenizer config
  tokens.py                tiktoken o200k_harmony full-request estimator + calibration
  layers/                  cap, pin, retrieve (BM25Plus chunks), window, summarize
  pipeline.py              assemble_context(): order, shrink, final admission, diagnostics
  summaries.py             NEW 0.10.0: explicit rolling summary generation
  inspection.py cli.py     offline inspect/probe, CLI entry point
  answers.py work.py       optional answer contracts, cooperative cancellation
  memory/                  SQLite durable store, codec, deletion/restore, index lifecycle
  providers/               Groq transport, client, replay cache, quota ledger, credentials
  service/                 FastAPI /v1 API, auth (JWT RS256 / hashed tokens), workers
  evaluation/              frozen corpus, protocol, harness, execution, reporting,
                           heldout/, strategies.py (NEW 0.10.0)
tests/                     unit, property (hypothesis), integration, process tests
scripts/                   brain.py, demos, frozen historical experiment runners
docs/                      architecture, contracts, checkpoint reports, protocols
brain/                     project memory: STATE, INDEX, DECISIONS, JOURNAL
archives/                  preserved wheels + freezes for every runtime change
experiments/ output/       frozen experiment inputs, saved evidence (private/ ignored)
examples/                  SDK quickstart, answer-policy examples, sample inputs
```

## 3. Module-level implementation audit

| Area | Files | Status | Notes |
|---|---|---|---|
| Contracts | models, context, errors, config, budget | Complete | Immutable dataclasses, strict validation, structured errors. |
| Token accounting | tokens.py | Complete, estimate only | Counts the full serialized request incl. framing/tools. 1.07 calibration is not a proven bound; 12 historical provider overruns (max actual/estimate 1.78). |
| CAP | layers/cap.py | Complete | Head/tail trimming of working copies; originals untouched. Root of F4 at larger budgets. |
| PIN | layers/pin.py | Complete | Mandatory reservation; overflow raises `RequiredContextTooLarge`. |
| RETRIEVE | layers/retrieve.py | Complete (lexical) | BM25Plus over original chunks with provenance. No semantic/hybrid retrieval (C11 preflight designed, 134 MB model not installed). |
| WINDOW | layers/window.py, common.py | Complete | Shared contiguous-suffix plan with RETRIEVE. |
| SUMMARIZE | layers/summarize.py | **Was non-functional (F1)** → fixed opt-in in 0.10.0 | Exact-match reuse kept as default; prefix reuse via `PrefixSummaryPolicy`. |
| Assembly | pipeline.py | Complete | Deterministic shrink order, per-block accounting, fingerprints. |
| Memory | memory/store.py, codec.py | Complete; **F2** fixed in 0.10.0 | Revisioned writes, tombstones, backup/restore, ACLs on Windows. |
| Providers | providers/* | Complete for Groq | Replay cache, quota reservations, uncertain-usage holds. Single provider. |
| Service | service/* | Complete for self-hosting | Tenant authorization before work; bounded process workers; no per-tenant rate limits or billing. |
| Evaluation | evaluation/* | Complete for frozen corpus; F3 added | Five validity gates, leakage gate, resumable runs, reports. One synthetic scenario. |
| Historical runners | scripts/c06_*, c09_* | Frozen | Must run under archived runtimes only; not product code. |

## 4. Where development stopped

Last commit `3e3e0e4` (2026-09-28) records Windows CI success. Work after it is on
disk but uncommitted: docs/brain updates for D097–D106, many new scripts and tests
(LongMemEval demo/review, sample app, retrieval candidates), all offline. The last
recorded next action was "approve isolated 134 MB semantic model/runtime setup"
(C11). The SDK/demo milestone was declared usable by the owner (D104); C09 quality,
C10 operations, C11 cost and C12 release remained open.

## 5. Five-stage pipeline evaluation

- **CAP:** useful for oversized tool outputs, but trimming WINDOW turns removes
  evidence that RETRIEVE then never looks for. Recommend enabling
  `recover_capped_window` by default (owner decision; see TECHNICAL_DECISIONS T2).
- **PIN:** sound. Keep.
- **RETRIEVE:** the strongest stage on this corpus (31/31 at both budgets when
  given the full optional allocation). Chunk precision ~0.33: about one in three
  retrieved chunks comes from the fact's source turn. Hybrid retrieval should be
  added only if a real-data evaluation shows lexical misses.
- **WINDOW:** sound. Alone it keeps 1/31 (900) and 4/31 (3000) facts.
- **SUMMARIZE:** now usable. The deterministic extractive summarizer adds nothing
  on this corpus (facts sit mid-message). Model summaries need inference to evaluate.

## 6. Security and reliability

See [SECURITY_AUDIT](SECURITY_AUDIT.md). No critical issue found in code review;
the main gaps are deployment-level (rate limits, TLS, audit retention, IdP).

## 7. Recommendations

1. Ship the SDK first (open source core). It works offline, needs no hosted
   infrastructure, and is the only surface with evidence behind it.
2. Make `recover_capped_window=True` the default after owner review (F4).
3. Build a small real-conversation evaluation set (with consent/synthetic rewrite)
   before any quality or savings claim. The single synthetic scenario was authored
   alongside the engine.
4. Fund a bounded answer-quality run (owner approval) using `strategy-eval`'s
   strategies so token savings can be tied to answer accuracy.
5. Defer hosted API, dashboard and billing until developers use the SDK.

See [IMPLEMENTATION_ROADMAP](IMPLEMENTATION_ROADMAP.md) and
[PRODUCT_STRATEGY](PRODUCT_STRATEGY.md).
