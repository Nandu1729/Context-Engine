# C06 progress report

Date: 2026-09-08. Package: 0.6.0. **Status: offline implementation delivered; checkpoint incomplete pending live prerequisites.**

## Update — 2026-09-13, package 0.7.1

Latest live update (package 0.7.2): owner supplied both organization-limit screenshots. Each GPT-OSS model has 30 RPM / 8,000 TPM / 1,000 RPD / 200,000 TPD. Configured private zero-price Free-tier testing with one shared ledger, conservatively aggregating those caps across both models. No paid upgrade is authorized. Project-specific limits and other traffic can still throttle.

First live smoke succeeded: A5/900 on 120b answered `shard-19` correctly, stopped normally, and retained the original t82 evidence. Estimated input was 804; provider receipt records 752 input and 42 output tokens (29 reasoning). Configured charge is $0, not an independently verified billing statement. Evidence: `output/c06-live-smoke.json`; execution `9463cbc769ecb56e68a7eb1e350de3ab3a34c5951dce83b2a8abe55af7105f0c`. Full matrix now runs separately in `output/private/c06-live-matrix` using the same account ledger. C06 remains incomplete; one successful answer does not establish the 31-probe targets. The prerequisite/no-inference statements below are historical.

Full-matrix progress: [latest snapshot](../output/c06-live-batch-004.json), execution `dd8c88217a8a2b3d2ba4635b9a126f5cdb4776ee283047425603ce8a0b30de77`. Saved 58/744 terminal dispositions: 31 A0 non-fits without inference and 27 live A1/900/120b answers; 686 slots remain pending (including 593 expected fitting calls). These first 27 baseline contexts retained none of their tested facts and scored 0/27 correct, with no transport errors or truncations. This is not A5's quality score. Provider receipts total 20,885 input + 1,093 output tokens for the matrix; including the independent smoke, 28 completed inference requests and 22,772 total tokens, configured charge $0.

Batches 001, 002 and 004 each saved nine new answers before local TPM admission paused. Batch 003, attempted before the minute window cleared, dispatched zero requests. Completed entries remain identical across resumes; no ledger resets or terminal retries. Smoke report passes all five integrity gates; its files regenerate with socket networking disabled and identical hashes, and both plots were visually inspected. Partial matrix reports correctly remain INTERRUPTED / quality NOT_EVALUATED, not accepted.

Next bounded resume after the rolling minute window clears (same ledger/config, new snapshot):

```bash
output/private/c06-frozen-env/bin/context-engine benchmark-run --mode live --allow-live --env-file .env --live-config output/private/c06-live-config.json --run-dir output/private/c06-live-matrix --snapshot output/c06-live-batch-005.json --max-calls 10
```

Continue incrementing unused snapshot names, preserving all prior artifacts. Minute throttling is temporary, not a missing owner input; the full workload may also span daily quota windows. No background runner is installed. C06 stays ACTIVE and incomplete; C08 has not started. Verification this session: all 31 execution tests pass (37.85 seconds); validated [partial leaderboard](../output/c06-live-progress-report/leaderboard.md) preserves pending results. The last full regression remains 454 passing tests; no source code changed this session.

Subsequent C08 handoff (D050–D051): owner now explicitly requests C08 offline and a C06 reminder. Before C08 source edits, archived 0.7.2 wheel/freeze/protocol and dependency hashes under `archives/c06-live/`, installed `output/private/c06-frozen-env`, and validated snapshot004 there. A zero-call resume saved `output/c06-preserved-resume-check.json` with the unchanged matrix execution ID and no inference; the shared provider ledger remains 28 completed requests / 22,772 tokens / configured $0. The command above now deliberately uses that isolated environment. Do not run old C06 journals through the evolving 0.8.0 workspace, alter quotas, or reset intents. Return here before C09 quality, C11 measured costs or C12 release. No automatic/background resumption.

Subsequent approval update, package 0.7.2: owner explicitly approved the targets and Free-plan-only testing with $0 paid spending (D047). The saved key authenticated successfully against Groq's read-only model list; both required models are available. No inference was performed. Approved protocol and planned probes are frozen; 454 tests pass. Actual account limits remain needed before configuring the live run. The model endpoint exposes no quota headers, and the Browser skill found no connected browsers. Requested a Console Limits screenshot; do not request the key again or repeat the target-approval question. The pending-approval statements below are historical.

The owner requested returning to C06 and saved a local key. Added explicit free-tier accounting (zero prices/caps with request/token quotas still enforced), private `--env-file` loading without shell evaluation, and free-tier report warnings. Archived the C07 wheel/freeze; corpus and unapproved targets remain unchanged.

454 tests pass, including 48 new cases for zero-price requests, quota/restart/replay behavior, paid-rate rejection, credential privacy and live preflight before database creation. Lint/format/lock/build pass; clean core-only installed provider/memory/benchmark checks pass with networking disabled. Flagship context remains 804/900 estimated input tokens. Detailed evidence is recorded in the journal.

**C06 is still incomplete: no live calls have been made.** Await explicit owner target approval, Free-plan/$0-spending confirmation and actual account limits. A populated key alone does not establish any of these. Free-tier mode is local accounting, not automatic account-tier detection or a provider billing lock. See [runner safeguards](RUNNER.md).

The remainder below preserves the original C06 offline delivery evidence.

## What was done

- Connected the frozen benchmark to the controlled provider adapter, with model-swap and full run/profile identities.
- Added durable per-probe dispatch journaling, quota-aware pause/resume, cumulative local run-spend admission and checked ledger receipts. Uncertain dispatches are never automatically resent.
- Added reproducible scorecards, model-specific result summaries, leaderboard and two PNG figures from saved evidence without inference.
- Preserved C04/C05 references and updated the project brain. The source PRD and pending benchmark targets remain unchanged.

## Verification

The full 744-slot offline matrix finished: 620 synthetic responses and 124 raw non-fit outcomes. Resume made zero additional calls. Synthetic responses are always `UNKNOWN`; results are `TEST_ONLY`, not model-quality evidence. No live inference or actual spending occurred.

Important finding: A5 retains 29/31 source facts at 900 tokens but only 19/31 at 3,000. The larger window can include CAP-shortened turns that retrieval then excludes. This limitation is recorded as experiment proposal S11; the frozen algorithm/targets were not tuned after seeing results.

354 tests pass, including 31 new C06 cases. Coverage includes receipt/request tampering, concurrent dispatch admission, cancellation, uncertain usage, quota rollover, replay and bounded exports. Lint/format/lock checks and clean wheel/core-only installs pass. Full-matrix reports regenerate with networking disabled and identical file hashes; both figures were visually inspected. Detailed evidence is in the project journal.

Review the [generated leaderboard](../output/c06-report/leaderboard.md), [context/cost figure](../output/c06-report/context_cost.png), [retention/answer figure](../output/c06-report/recall_by_zone.png) and [runner guide](RUNNER.md).

## What is still needed

C06 cannot be marked complete without live results and the flagship real answer. Required inputs: explicit target approval, an authorized total inference spending limit, actual account quotas/prices and a locally supplied API key. Do not paste the key into chat.

Next action is to finish C06 once these prerequisites are supplied—not to start C07 or declare V1/enterprise acceptance. Local estimated reservation caps remain distinct from provider billing guarantees.

Sequencing amendment, 2026-09-08 (D037–D038): the owner subsequently approved deferring C06 live work and proceeding with offline C07/C08. The preceding next-action statement is historical. Remind at those handoffs and return to C06 before C09 real-world quality qualification, C11 measured model-cost work or C12 release. C06 remains incomplete; no target/spending approval was granted.
