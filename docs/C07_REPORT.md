# C07 checkpoint report

Date: 2026-09-08. Package: 0.7.0. Status: READY for owner review, not owner-accepted.

## What was done

- Added transactional scoped history, revisioned pins, reusable summaries and explicit content export.
- Added idempotent ingestion, conflict detection, persistent chunks and resumable incremental indexing.
- Added retention/deletion invalidation, optional memory-managed provider replay, and restore that reapplies current deletion records before serving data.
- Preserved C06 wheel/freeze/results and saved the owner's deferral/reminder in the project brain.

## Verification

406 tests pass, including 52 new memory cases. Lint/format, lock/dependency checks and wheel/source builds pass. A clean core-only installation runs setup, memory demo and benchmark checks with networking disabled; no HTTPX or Matplotlib is required. The unchanged flagship context remains 804/900 estimated tokens.

The [synthetic demo](../output/c07-memory-demo.json) reopens 12 turns, resumes 9 remaining index tasks, reuses unchanged chunks, retrieves the original fact, revises a pin and restores an old backup without the deleted turn, derived pin or cached answer. Tests also cover expiry, competing updates, corrupt storage, stale/missing recovery authority and deletion during inference. Zero live inference or spending.

## Limits and next step

This is a local trusted SDK, not yet an authenticated or production-qualified enterprise service. BM25 scoring still builds per query; PostgreSQL, cross-platform recovery and production load gates remain ahead. Backup safety requires the current deletion ledger plus a trusted minimum watermark; it does not erase external backups or provider copies. See [memory contracts](MEMORY.md).

Next: C08 authenticated self-hosted API and integrations, initially offline with synthetic data. **Reminder: C06 remains incomplete and must be revisited before C09 real-world quality checks, C11 measured model-cost work or C12 release.** Needed then: target approval, authorized spending cap, actual account quotas/prices and a locally supplied API key. The reminder is persisted for checkpoint handoffs, not scheduled in the background.
