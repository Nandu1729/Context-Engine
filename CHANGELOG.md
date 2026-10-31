# Changelog

Earlier versions (0.1.0–0.9.6) are documented in `docs/C01_REPORT.md` through
`docs/C10_STORAGE_ACL_REPORT.md` and preserved as wheels under `archives/`.

## 0.12.0 — 2026-10-31 (unreleased)

### Added
- `context_engine.adapters`: `openai_chat`, `anthropic_messages`,
  `langchain_messages` and `turns_from_openai`. No new core dependencies; optional
  `[langchain]` extra (`langchain-core>=1.0,<2`).
- Inception (Mercury) provider: `InceptionGenerationConfig` (mercury-3/2.5/2,
  temperature 0.5–1, reasoning instant–high) and `InceptionTransport`, reusing the
  bounded client, ledger and metered spend cap. `scripts/inception_smoke.py` makes
  one capped call only with `--allow-live`; live smoke passed (D111).
- `context-engine-mcp`: prototype MCP server over `MemoryStore` (stdio JSON-RPC,
  standard library only) with `add_message`, `pin_fact`, `get_context`, `forget`.
  See `docs/MCP.md`.

### Changed (performance)
- Bounded process-wide token-count cache (32,768 entries, texts up to 4,096
  characters). Counts and assembly output are identical; benchmark gates unchanged.
  All-layers assembly on the 100-turn benchmark (same history, new questions):
  median 247 → 95 ms at 900 tokens, 481 → 208 ms at 3000 tokens.

### Changed
- Provider transports carry their own endpoint/adapter identity (Groq request keys
  are unchanged). HTTP 402 now maps to `billing_or_quota`.

### Unchanged
- Assembly output and defaults. 0.11.0 wheel/freeze archived in
  `archives/c12-adapters-0120/`.

## 0.11.0 — 2026-10-31 (TestPyPI)

### Changed (behavior)
- `RetrievalConfig.recover_capped_window` now defaults to `True` (owner decision
  D109). RETRIEVE can restore original evidence that CAP removed from recent
  WINDOW turns. Offline retention on the frozen corpus: 31/31 at 900 and 3000
  tokens (was 29/31 and 19/31), for about 5–15% more assembly latency. Pass
  `RetrievalConfig(recover_capped_window=False)` for the old behavior.
- Existing `MemoryStore` chunk indexes are rebuilt once after upgrading, because
  the index profile hashes the full retrieval configuration.
- `strategy-eval`: `combined` now uses the new defaults; `combined_recover` is
  replaced by `combined_no_recover` (the 0.10.0 defaults).

### Added
- Apache-2.0 `LICENSE`; license, classifiers and project URLs in package metadata.
- Newcomer README with a tested quick example (`tests/test_readme_example.py`).

### Unchanged
- The frozen benchmark harness pins `recover_capped_window=False`, so A0–A5 and
  historical gates reproduce. 0.10.0 wheel/freeze archived in
  `archives/c11-recover-default-0110/`.

## 0.10.0 — 2026-10-31 (unreleased)

### Added
- `context_engine.summaries`: `update_summary` for explicit, amortized summary
  refresh; `ExtractiveSummarizer` (deterministic, model-free); `PromptSummarizer`
  (wraps any `complete(messages) -> str` function; no provider SDK imported).
- `PrefixSummaryPolicy` and `SummarySnapshot.covers_prefix`: opt-in reuse of a
  summary that covers the oldest omitted turns. New diagnostic reason
  `summary_reused_prefix`.
- `MemoryStore.assemble(..., summary_prefix=True)`.
- `context-engine strategy-eval`: offline comparison of full history, WINDOW,
  WINDOW+summary, WINDOW+retrieval, all layers, and all layers with
  `recover_capped_window`, with retention, chunk precision, turn recall, token
  reduction and latency.
- `examples/rolling_summary.py`.

### Changed
- `MemoryStore` keeps a stored summary when the appended, updated or deleted turn
  is not covered by it. Changing or deleting a covered turn still removes it, and
  lineage is still re-verified on every read.
- `pytest` now works without `python -m` (`pythonpath = ["."]`).

### Unchanged
- Default `assemble_context` output, `FrozenSummaryPolicy` exact matching, and
  `recover_capped_window=False` default.
- Historical experiments: 0.9.6 wheel/freeze archived in `archives/c11-summaries-0100/`.
