# C04 checkpoint report

Status: implementation READY for owner review — 2026-09-08, package 0.4.0. Pre-registration approval remains pending.

What was done:

- Built the frozen 100-turn/31-fact benchmark, separate ground truth, background summary and PIN fixture.
- Added six declared variants, deterministic answer/evidence grading, five validity gates and immutable resume snapshots.
- Added offline benchmark-check/plan commands with reproducible hashes and privacy-safe default output.
- Updated the persistent brain, checkpoint evidence and owner review documents.

Verification: 233 tests pass, including 84 new C04 cases. All 31 primary probes fit 900 estimated input tokens. The flagship retrieves `shard-19` from Turn 82 at **804/900**, versus **16,608** estimated raw tokens. Five deliberately corrupted cases are INVALID. Lint, formatting, lock/dependencies, build and a separate installed-wheel check pass.

Limitations: zero inference calls; answer accuracy and provider savings are unmeasured. This synthetic corpus does not establish enterprise readiness. [Proposed success targets](PREREGISTRATION.md) still need owner approval and a separate spending limit before live runs.

Evidence: [benchmark guide](BENCHMARK.md), [saved offline check](../output/c04-benchmark-check.json).

Next: C05 — provider adapter, replay cache, usage ledger and quota/retry safety, beginning with offline provider tests.
