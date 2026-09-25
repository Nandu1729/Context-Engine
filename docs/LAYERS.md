# C02 layer contracts

These independent layers are composed by the [C03 public pipeline](PIPELINE.md). This document is separate from the owner's short checkpoint reports. All layers implement `apply(ContextCarrier) -> ContextCarrier`; source turns remain immutable and each stage adds a diagnostic. Run order: CAP → PIN → RETRIEVE → WINDOW → SUMMARIZE.

## CAP

`CapLayer(counter, CapConfig(max_tokens=35, head_tokens=22, tail_tokens=8))` compresses each message's content independently. Head/tail sizes are targets; the final measured cap includes newlines and an explicit `N tokens elided` marker. N counts the actual removed substring. Source content, tool-call arguments and metadata remain unchanged.

Slices use Unicode code points and never split UTF-8 bytes. Grapheme-cluster preservation is not guaranteed. The search for fitting endpoints is deterministic and verifies the final count; it need not maximize retained text when BPE counts are non-monotone. If even one original code point at each end plus the marker cannot fit, raise `CapBudgetError`; never remove the whole turn. CAP must run before PIN.

## PIN and keyed updates

`PinLayer(counter, budget, system, at, tools=())` uses an explicit timezone-aware time, filters expired/future facts and produces stable SYSTEM/PINNED blocks. Facts are JSON data in a user message, not instructions. System text is preserved exactly. The mandatory request also contains the question and tool definitions; overflow is a typed error.

`KeyedPins.upsert(pin, expected_revision=...)` returns a new set. New keys start at revision 1; replacement requires the current revision and advances exactly once. No extraction or transactional database update happens here.

PIN snapshots the input identities/content/pins/question and token estimate. Re-running it deliberately discards downstream blocks and membership. Subsequent layers reject changed inputs, mandatory blocks or a changed counting profile instead of silently using stale reservations.

## Shared WINDOW planning and rendering

`layers.common.plan_window` walks capped turns newest backward, stopping at the first non-fitting turn. RETRIEVE and WINDOW use this same function and stored membership. When membership is already present, consistency is checked against the shared selection logic. Unused retrieval/summary space is not donated to WINDOW in C02.

All optional blocks are measured as incremental calibrated request cost, including their framing. Candidate retrieval includes the planned window in its combined-request fit check even before WINDOW runs. Each admitted optional block also fits the complete current request. The C03 public pipeline performs a final recount and owns defensive shrink/error behavior.

Historical messages are quoted JSON inside a user-data WINDOW block. This retains historical role/tool metadata without creating active system messages or orphan tool executions. Source authorization must be enforced by the caller/service; labels and scope checks do not authenticate anyone.

`layers.common.render_request` is an internal accounting primitive that follows SYSTEM/PINNED/SUMMARY/WINDOW/RETRIEVED/QUESTION order. Call the public `assemble_context` boundary for final admission and diagnostics.

## RETRIEVE

0.9.2 optional extension:`RetrievalConfig(recover_capped_window=True)` also searches
original chunks missing from changed messages within WINDOW. Fully represented
chunks in the same source message are excluded;partial boundary chunks can overlap
visible text. Source validation,reserves and final accounting remain unchanged.
DefaultFalse preserves the original contract below. SDK opt-in only;not a new
service request field or environment setting. See [repair design](C09_REPAIR_DESIGN.md).

`RetrieveLayer(counter, RetrievalConfig(...))` indexes original message text only from turns outside the planned WINDOW. It does not search tool-call argument metadata. Chunking uses Unicode code-point ranges: 360 characters with 80-character overlap by default. IDs incorporate scope, source IDs, revision, content hash, range and chunker version. Provenance is retained outside the prompt; short turn/message/range references accompany evidence in the prompt.

Baseline variant: rank-bm25 0.2.2 `BM25Plus`, k1=1.5, b=0.75, delta=1.0. BM25+ provides useful scores for tiny corpora; because its delta can also give nonmatches positive scores, candidates must have lexical overlap with the query. Normalization is NFKC + casefold + Unicode word/identifier tokenization. This is lexical retrieval, not semantic search or a comprehensive multilingual tokenizer.

Default top-k=4, score floor=0.0 with strict greater-than admission. Sort by descending score and stable chunk ID. Skip overlapping ranges from the same source and chunks that cannot fit; do not cut returned evidence arbitrarily. Queries with no lexical terms, empty/unsuitable history, zero reserves and no matches return empty evidence with a reason code. No LLM calls.

## SUMMARIZE and fixture validation

`SummarySnapshot.from_history` binds supplied summary text to the exact omitted original turns, scope, revision/content digest, source ranges, policy version and creation/expiry times. `FrozenSummaryPolicy` reuses that object only when its lineage and validity period match. `SummaryLayer(counter, policy, at)` omits unavailable/stale/empty/oversized summaries with diagnostics. A None policy disables summarization. No per-turn summary generation or hidden cache storage is introduced.

For benchmarks, `evaluation.fixtures.validate_frozen_summary(snapshot, forbidden_answers)` validates before creating the frozen policy. It conservatively normalizes case, compatibility characters, whitespace and punctuation to detect declared aliases. Short aliases may cause false positives; semantic paraphrase leakage is not detected. Ground-truth aliases stay in the evaluation helper and are never supplied to the core layer.

## Configuration and verification

Settings expose CAP and retrieval configuration from `config.py`; `.env.example` lists supported environment keys. The synthetic demo fixes its own documented stress configuration for repeatability. Runtime dependencies are tiktoken 0.14.0 and rank-bm25 0.2.2, with NumPy 2.5.3 resolved transitively in `uv.lock`.

```bash
uv sync --locked --python 3.12
uv run --locked context-engine check
uv run --locked context-engine demo-layers
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv lock --check --offline
uv pip check
uv build --offline
```

C02 tests: `tests/test_layers.py`. They exercise each layer independently, original-source immutability, source range/revision/scope, exact retrieval exclusion, budget conservation, Unicode, pin revisions, summary lifecycle and leakage. The memory test fixture now copies all project Markdown so adding a checkpoint report cannot create false missing-link failures.

The C04 fixture/harness is implemented; [pre-registration](PREREGISTRATION.md) awaits owner approval. Remaining work: C05/C06 provider integration/calibration and measured results; C07 persisted/indexed memory. No latency, cache savings or model accuracy is asserted from this layer demo.
