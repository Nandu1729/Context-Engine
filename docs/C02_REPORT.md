# C02 — Five context layers

Status: READY for owner review · 2026-09-07 · package 0.2.0

What was done:

- CAP shortens oversized message content to a counted head/marker/tail while preserving originals.
- PIN protects supplied instructions and active facts, supports immutable keyed updates, and reserves space for the question and tools.
- RETRIEVE uses BM25+ over original chunks, with stable source references, overlap deduplication and recent-window exclusion.
- WINDOW uses the shared plan to keep a contiguous recent suffix.
- SUMMARIZE reuses source-matched snapshots; stale, expired or oversized summaries are omitted. Benchmark fixture validation rejects declared answer leakage.
- Saved your preference for a short report after every checkpoint.

Verification: **89 tests passed**, lint/format and lock checks passed; package built successfully. Tests also corrected the brain fixture to include newly added report files. Final wheel installation evidence is recorded in the project journal.

Demo: a 373-token tool message becomes 35 tokens; its removed `shard-19` fact is recovered from the original. The five-layer request uses **637 estimated tokens out of 900**, with zero inference calls.

```bash
uv run --locked context-engine demo-layers
uv run --locked pytest -q
```

Limitations: token counts still need provider calibration. Summaries are supplied/reused; no automatic LLM summarization or benchmark quality claim. [Contract details](LAYERS.md) document behavior and configuration.

Next: **C03 — public one-call assembly, final validation/shrinking, and offline inspection.**
