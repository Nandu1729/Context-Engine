# Architecture baseline

Status: C01–C07 core, layers, evaluation, provider and persistent memory are implemented, with C06 live qualification unfinished. C08 adds an optional authenticated local service around the unchanged core. See [service contracts](SERVICE.md), [public API](PIPELINE.md), [benchmark contracts](BENCHMARK.md), [provider contracts](PROVIDER.md) and [runner boundaries](RUNNER.md). Preserve PRD behavior unless a recorded amendment says otherwise.

## Boundaries

```text
Agent / application
  -> authorized ingestion -> original history store -> chunk index
  -> assemble_context(request, stores, policies)
       CAP -> PIN -> RETRIEVE -> WINDOW -> SUMMARIZE
       -> SYSTEM / PINNED / SUMMARY / WINDOW / RETRIEVED / QUESTION
       -> serialized-request token validation
  -> caller's inference integration OR provider adapter
       -> replay lookup -> quota admission -> inference -> usage reconciliation

Evaluation harness -> same public engine interface -> saved results -> offline reports
```

Start as a modular Python package. The public library imports no benchmark runner or provider SDK. Optional integrations are adapters. Use one service and a background worker when persistence requires it; split into services only after measured workload or isolation needs justify that operational cost.

C06 execution composes the public engine and provider adapter outside the reusable core. Its private run journal commits dispatch intent before calling the separate account ledger/transport. A cross-database crash leaves uncertainty and halts automatic resend; this is not distributed exactly-once processing. Reports validate frozen requests and captured receipts, then render offline with optional Matplotlib. Configuration/price/provider dependency identity is distinct from model-quality acceptance.

Package layout: `src/context_engine/{models,budget,tokens,pipeline,layers,inspection,providers,memory}`. Provider-local accounting lives in `providers/store.py`; C07 conversation/index storage lives separately in `memory/`. Evaluation helpers remain separate. This is a documented packaging refinement of PRD §47, not a change to its behavior. `uv.lock` captures tested dependencies. Do not blindly copy the PRD's version lower bounds.

## Public contract

`assemble_context(history, question, pinned_facts, budget, *, system, at=None, token_counter=None, cap_config=None, retrieval_config=None, summary_policy=None, tools=(), options=None) -> AssembledContext`.

`AssemblyOptions` controls optional CAP/PIN/RETRIEVE/SUMMARIZE behavior explicitly; defaults enable all. Evaluation variants A1–A5 share this public boundary. The CLI may compose evaluation commands; reusable contracts, tokens, budget, layers and pipeline remain independent of evaluator metadata and provider SDKs.

The production service resolves identity and an authorized, versioned history snapshot before calling the core. A caller-provided tenant ID alone is not authorization. In-process SDK users remain responsible for supplying authorized data.

| Model | Required semantics |
|---|---|
| Message / Turn | Immutable original messages; stable IDs, roles, timestamps, tool-call IDs, tenant/session scope, content hash. A turn can contain multiple tool messages. |
| SourceRef / Chunk | Original turn/message ID, start/end offsets, revision and chunker version. Trace every retrieved excerpt back to original content. |
| Pin | Key/value, revision, origin, scope, effective/expiry times. Upsert supersedes old value; stale concurrent updates conflict. |
| BudgetConfig | Input cap, model capacity, completion reservation, adapter overhead, optional request ceiling, layer reserves; validate all values. |
| TokenCounter | Count complete adapter-rendered messages and tool schemas; expose tokenizer/version/calibration and estimate confidence. |
| BudgetPlan | Immutable allocation and exact planned WINDOW IDs shared by RETRIEVE and WINDOW. |
| ContextCarrier | Original/capped turns, plan, blocks, sources, diagnostics; layers only alter their own outputs. |
| AssembledContext | API-ready messages, total/per-block accounting, kept/omitted/retrieved IDs, selection reasons, source lineage, config/snapshot hash. |
| ModelResult | Success/failure, answer, finish reason, usage, cached tokens, request ID, retries and replay status; no secret-bearing raw exceptions. |

## Budget rules

Use `B = min(application_input_cap, model_capacity - completion_reservation, optional_provider_per_request_input_cap)` with framing and tool schemas included in counted input. TPM/TPD are separate quota controls, not immutable model input ceilings. A request that cannot be admitted before its deadline gets a quota error or reschedulable outcome.

1. Reserve system, required pins, current question, framing and tool schemas. If these exceed B, raise `RequiredContextTooLarge` with counts and no inference.
2. Reserve configured summary and retrieval allocations; allocate the remaining amount to WINDOW. Validate allocations rather than accepting negative budgets.
3. Determine WINDOW once from capped, complete recent turns, newest backward, stopping at the first non-fitting turn. Keep chronological order in the rendered block.
4. Retrieve only from originals outside that planned window. Stable chunk IDs, deterministic score tie-breaking, configurable normalization, top-k and relevance floor prevent arbitrary filler. Deduplicate overlapping evidence.
5. Use summary of history omitted by WINDOW. Empty history produces no summary. Frozen benchmark summaries are a separate policy from amortized production summaries.
6. For V1, unused reserved space may remain unused; never expand WINDOW after retrieval without recomputing both membership and retrieval exclusion. Optimization can follow correctness.
7. Render once in the PRD order and recount the entire request. If estimated overflow remains, deterministically reduce optional summary, oldest window turns, then lowest-ranked evidence; record drops. If protected content still cannot fit, return a structured error.

The sum of nominal block counts may differ from actual serialization due to delimiters and framing; record framing separately and use the full count for admission. The final validation path must terminate and must never enlarge the budget silently. Calibration is measured against provider usage, including Unicode, tool schemas and reasoning/output accounting.

## Layer behavior

CAP is per-message, deterministic, and includes its elision marker within its allocation. Retain head and tail without cutting invalid Unicode or changing original source content. Working tool transcripts must preserve valid call/result relationships; historical quoted evidence is rendered as data rather than executable tool calls.

PIN protects application-supplied facts and system instructions. It performs no automatic extraction. PIN data is not allowed to redefine authorization policy.

RETRIEVE uses rank-bm25 over authorized original chunks. C07 persists versioned chunks and incremental coverage; BM25 still builds for each eligible old-history subset. Tests verify unchanged turns are not re-chunked and persisted assembly matches the core. Chunk-size and overlap are configurable and frozen for evaluation. No retrieval-quality tuning is included.

SUMMARIZE is optional at runtime, uses provenance and a history watermark, and cannot substitute for exact source evidence. C07 persists caller-supplied summaries with source history, policy version and expiry; it generates none. Future generated-summary integration must also record model/config/version and cost. No hidden per-turn LLM summarization. Deleting a source invalidates summaries derived from it.

## Persistence and cache correctness

Development fixtures and local replay/ledger use SQLite as in the PRD. A multi-instance service is proposed to use PostgreSQL for transactional state and shared quota coordination; use an object store only when blob size warrants it. Storage selection remains subject to service workload validation.

C05 uses one explicit SQLite file with separate tables, so replay creation and usage settlement are atomic. Replay bodies require opt-in; the default ledger is metadata-only. Unknown usage holds reservations across restarts/day rollover until evidence-backed reconciliation. This is local participating-worker coordination, not a provider invoice guarantee or distributed service. See [implemented limits and privacy lifecycle](PROVIDER.md).

Replay keys cover provider/endpoint/model, full request bytes, generation parameters, adapter/version, tenant/security scope and policy version. Memory-derived requests include snapshot revision. Tool-result execution is not replayed as a side effect. A cache hit records a replay event with zero new provider spend, distinct from the original call cost and estimated avoided cost. Do not cache partial failures as successful answers.

Quota reservations must be atomic across concurrent callers. Reconcile reservations against observed usage; preserve an uncertain state on timeouts where the provider may have processed the request. Bound retries by deadline and attempt cap; respect Retry-After and avoid double retries across SDK and wrapper.

Original records are preserved from CAP, not exempt from retention or authorized deletion. Maintain tombstones/invalidation for chunks, pins, summaries and replay references. Backup restore must reapply deletion records before serving traffic.

C07 implements local transactional memory and optional memory-managed provider replay. A separately retained deletion authority and minimum watermark are required for restore. See [memory contracts and recovery limitations](MEMORY.md). This SDK is not the C08 authentication boundary or C10 production recovery qualification.

## Security and diagnostics

Only authenticated application policy supplies instructions. Retrieved text, history, and summaries carry data labels and source attribution; delimiters alone are not a security boundary. Apply access checks before searching, caching, reading or exporting. Model output cannot authorize storage operations or tools.

Default telemetry contains IDs, counts, latency and error classes. Raw content inspection is a deliberate, access-controlled debug operation with expiry. Bound bytes, turns, chunk counts and CPU as well as prompt tokens. ENTERPRISE defines the release evidence for these controls.
