# Benchmark execution and reports — C06

Package 0.6.0 adds durable benchmark orchestration and offline report generation. The full synthetic matrix has 744 slots: 31 facts × six variants × two models × two budgets. **C06 remains incomplete until its required live evidence is collected.** An offline run finishing is not V1 or enterprise acceptance.

## Run a bounded offline demonstration

```bash
uv sync --locked --extra provider --extra reports --python 3.12.13
uv run --locked context-engine benchmark-run --run-dir output/private/my-run --snapshot output/my-first.json --fact shard --budget 900 --max-calls 1
uv run --locked context-engine benchmark-run --run-dir output/private/my-run --snapshot output/my-resumed.json --fact shard --budget 900
uv run --locked context-engine benchmark-report --snapshot output/my-resumed.json --output-dir output/my-report
```

The first command executes at most one fitting logical probe; the second resumes the same immutable selection/profile. Completed slots are skipped. Each export path must be new. Omitting selection flags schedules all 744 slots; `--fact`, `--model`, `--budget` and `--variant` are repeatable, frozen-protocol selections. `--max-calls` bounds logical probe evaluations per invocation (0–744), not HTTP retry attempts. A0 non-fit slots are recorded without inference and do not consume the batch count.

`model-swap` uses both declared models with the same chosen facts, budgets and variants:

```bash
uv run --locked context-engine model-swap --run-dir output/private/my-swap --snapshot output/my-swap.json --fact shard --budget 900
```

Offline mode is the default. Its transport receives only the request/generation payload and returns literal `UNKNOWN`, with explicitly synthetic usage/pricing; it cannot access ground truth. Completed synthetic runs are `TEST_ONLY`. The two provider model labels select profiles, not real inference. Estimated fit/retention are genuine engine measurements; synthetic answer grades and charges are not model-quality or billing evidence.

## Live prerequisites

Live execution requires `--mode live --allow-live`, an owner-approved registration in the frozen protocol, `GROQ_API_KEY` through the environment or explicit `--env-file`, and `--live-config` pointing to a private JSON file. No credentials belong in live-config JSON, command arguments, result files or project brain. These checks precede live CLI database creation or dispatch.

The configuration has exactly four keys:

- `quota`: the [QuotaPolicy](PROVIDER.md) fields `account_id`, `daily_budget_microusd`, `rpm`, `tpm`, `rpd`, `tpd`, explicitly supplied for the actual account.
- `prices`: one versioned PriceCard per selected model, with `version`, `input_per_million_microusd`, `cached_input_per_million_microusd`, `output_per_million_microusd`.
- `max_run_cost_microusd`: a positive cumulative local run-admission ceiling, separate from the account daily cap. Both use integer micro-USD; 1,000,000 micro-USD = $1.
- `ledger_path`: one absolute provider-account ledger path shared across participating runs/workers. Do not create a fresh account ID or ledger to bypass a limit.

### Free-tier execution — package 0.7.1

Metered mode remains the default: a zero daily budget still disables requests. For an owner-confirmed Groq Free-plan account, explicitly add `"billing_mode": "free_tier"` inside `quota`, set `daily_budget_microusd` and `max_run_cost_microusd` to **0**, and set all three rates in each price card to **0**. Use a version such as `owner-confirmed-free-2026-09-13`. Positive prices/caps in free-tier mode are rejected. The top-level four-field configuration shape is unchanged; the positive-cap statements above apply to metered mode.

This is explicit local accounting policy, **not an API-side billing lock or automatic account-tier detection**. Confirm Free-plan status and actual account quotas in Groq Console before every resumed live batch. Never use this mode on a paid account or upgrade while running. Groq's [published rate limits](https://console.groq.com/docs/rate-limits) are examples; account settings are authoritative. Free-tier runs retain request/token admission, daily/minute limits, uncertainty holds, durable resume and receipt validation. Configured zero charges are not independently verified bills or measured paid-plan savings. The full matrix may require multiple daily quota windows; there is no automatic background runner.

`--env-file .env` reads only that explicit private file, limited to 8 KiB. It accepts exactly one `GROQ_API_KEY=...` assignment, optional matching quotes, comments and blank lines. No shell execution/interpolation occurs; other assignments, duplicate/empty keys and conflicts with an existing environment key fail without echoing contents. Private files must be regular and mode 0600 on POSIX; leaf symlinks are refused. Parent directories are trusted. Nothing implicitly loads `.env` merely on package import. The live JSON configuration is likewise private and bounded to 64 KiB.

The new billing field is part of persisted account policy and execution identity. Existing ledgers lacking that field fail policy comparison rather than silently accepting a changed policy. Keep historical runs on their archived wheels; migration of a previously used live account requires reviewed policy/ledger handling, not a fresh ID to evade quota. The saved project key alone neither approves targets nor proves free-plan status.

All model clients share one quota policy/account ledger. Pricing is model-specific. The execution profile records endpoint/adapter, generation, retries, replay settings, security/snapshot revisions, ledger path and exact provider dependencies. Secrets are excluded. Credential rotation does not change the identity; changed prices/configuration/source/dependencies do and must not silently resume old work.

CLI replay is disabled; SDK clients can opt in. Reported usage and new charge are derived from the captured adapter ledger rows. Provider-cached input is distinct from local replay. Replay retains original usage but adds zero new cost and is not an independent answer sample. Unknown cached/reasoning details stay explicitly unknown. Prices calculate estimated charges, not independently verified invoices. Actual provider usage can exceed tokenizer-based reservations: local run/account limits are not an absolute provider-billing cap.

Targets are [owner-approved on 2026-09-13](PREREGISTRATION.md), alongside Free-plan-only testing and $0 paid spending (D047). Package 0.7.2 freezes the approved protocol; earlier owner-pending artifacts remain archived. Owner screenshots establish organization quotas for both models: 30 RPM, 8,000 TPM, 1,000 RPD, 200,000 TPD (D048). The private live config conservatively shares these caps across models and all runs through one ledger (D049); project limits or other traffic may still throttle. First live flagship passed; full qualification remains pending. Do not edit thresholds after observing model results or substitute synthetic results for live evidence.

## Durable execution and safe resume

`run.sqlite` stores an immutable manifest/profile and per-probe prepared records, dispatch phase, reserved cost and adapter receipt. It uses private local SQLite transactions. One dispatch intent across the journal may be active at a time, including concurrent callers. The separate provider ledger owns shared-account quota/attempt accounting. These are different transaction boundaries; C06 does not claim distributed exactly-once execution.

Before every call, the runner checks the frozen generation/tokenizer and complete request estimate, reserves the cumulative run allowance, and commits a dispatch intent. Successful/error/truncated outcomes and receipts are committed together afterward. Terminal outcomes are never silently retried on resume. A quota rejection with no attempt remains pending and pauses the batch; rerun the same command after quota becomes available, selecting a new snapshot output path. There is no background quota-wait daemon.

Cancellation, process death or a failed write between provider dispatch and journal settlement leaves a dispatch intent. Resume stops with `uncertain_dispatch`; a known terminal timeout with unknown usage stops further calls with `uncertain_usage`. **No automatic resend or time-based release occurs.** Preserve both databases and reconcile the provider ledger with external evidence. Automatic reconstruction of a missing benchmark answer or clearing a dispatch intent is not implemented; operator recovery requires an explicitly reviewed procedure. Do not delete the journal or mark an uncertain request pending to force progress.

Snapshots are immutable version-2 compact JSON, bounded to 32 MB. Compact output keeps the complete 744-slot fixture below that bound; pretty-printing the same evidence exceeds it. The journal remains authoritative if export fails. Snapshots contain the public synthetic assembled prompts and generated answers so results can be independently checked; they are deliberately not the default metadata-only provider log. Do not use this benchmark writer for private customer histories.

Loading or reporting rechecks the snapshot digest, manifest/freeze, complete request reconstruction, response grades, ledger ancestry, model/account/price/usage/content binding and the expected full request key. Invalid integrity is rejected; truncation remains exportable and visibly `INVALID`. Local hashes and captured ledger rows are integrity/audit checks, not signed provider attestations or protection against an attacker rewriting every trusted local artifact.

## Foreground completion controller — 2026-09-19

The owner requested completing all remaining C06 cases (D059), rather than stopping at each group. `scripts/c06_complete.py` orchestrates the existing archived CLI without changing core code, experiment identity, quota policy or results:

```bash
python3 scripts/c06_complete.py
python3 scripts/c06_complete.py --allow-live
```

The first command is read-only status and never reads the key. The second holds a nonblocking controller lock and launches only `output/private/c06-frozen-env/bin/context-engine` with the existing `.env`, private profile, shared account ledger, run directory and a new numbered snapshot per batch. The archived runner remains the final identity, credential, request and quota-admission authority; the controller reads the journal/ledger to avoid unnecessary dispatch attempts. It prints metadata-only progress, not provider bodies, secrets or subprocess stderr.

Minute quota waits are conservative, in at most 30-second intervals; the original 30 RPM /8,000 TPM /1,000 RPD /200,000 TPD policy remains unchanged. Daily exhaustion stops the controller with the next local UTC window, rather than resetting accounting or holding a day-long unattended task. Active/uncertain requests, unknown/nonzero charges, changed policy, terminal errors/truncation, abnormal runner results or clock rollback stop execution for review. Completed probes remain untouched. A full matrix still requires archived snapshot/report validation and honest quality evaluation.

This is an explicit foreground process, not a scheduled/background service or automatic next-day resume. Do not delete its lock file to start a competing controller, kill an in-flight child to force a snapshot, or reset either database. If interrupted, inspect the saved journal and ledger before resuming. Daily quota may prevent finishing all cases in one invocation; changing provider/model is not a workaround inside the frozen experiment.

## Reports without inference

`benchmark-report` takes only a saved snapshot and a new output directory. No provider client is created or called. It generates:

- `scorecard.json`: full configuration, validity gates, raw-count statistics, separate planned/completed answer denominators, zone retention, estimated inputs, detailed known/unknown observed usage and new-cost subtotals.
- `leaderboard.md`: model/budget/variant rows in protocol order, with pending/errors/truncations visible. It does not rank incompatible workloads or hide invalid/low-quality runs.
- `gpt-oss-120b-results.json` and `gpt-oss-20b-results.json`: separate model-specific scorecard projections retaining the parent manifest and snapshot digest, not independent resumable runs.
- `context_cost.png`: estimated input tokens and new calculated charges, explicitly synthetic when appropriate. An oversized raw context is shown as non-fit, not as a billed API call.
- `recall_by_zone.png`: source-backed fitting retention versus answer correctness for early/middle/late facts, with raw denominators. Missing answers show N/A, not measured zero accuracy.
- `report-manifest.json`: source snapshot digest, rendering versions and SHA-256 hashes of generated files; written last. A partial directory without this completion artifact is not a complete report.

Matplotlib 3.11.1 with its noninteractive Agg canvas renders the figures. The reporting dependency is optional and separate from the core/provider. Byte-identical regeneration is tested in the locked local environment with networking disabled; no cross-platform pixel-equivalence guarantee is made. Default tokenizer assets must already be cached for offline validation.

The checked full-run evidence is `output/c06-offline-run.json`; regenerated outputs are in `output/c06-report/`. They are synthetic mechanism evidence only. Earlier wheels/freezes, including 0.7.1 at `archives/c06-free-prep/`, remain archived; historical outputs intentionally fail changed-source resume checks. Use the matching wheel for historical reports. Current 0.7.2 records only the approved protocol state and package version; thresholds/corpus/algorithm are unchanged. See [C06 progress](C06_REPORT.md).

C08 preservation update: the workspace now evolves at 0.8.0. Existing C06 live artifacts must use `output/private/c06-frozen-env/bin/context-engine`, installed from `archives/c06-live/`'s immutable 0.7.2 wheel and hash-locked dependencies. This environment successfully validates snapshot004 and performs a byte-identical zero-call resume. Keep the same working directory, private live configuration and shared ledger; see C06_REPORT.md for the current next-batch command. Do not substitute `uv run` against current source or automatically rewrite an old profile/freeze. Rebuild a missing environment from the archived wheel/requirements, not the current lockfile. Owner D050 deferred further live inference while C08 was delivered; subsequent continuation returned to C06. Its completion gate before C09/C11/C12 remains active.
