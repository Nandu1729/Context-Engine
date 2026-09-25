# Self-hosted operations and recovery runbook

Status: local preparation,not an approved production operating plan. No deployment
has been performed. Keep the service loopback-only until TLS,IdP,key management,
storage encryption,workload and operating ownership are chosen and reviewed.
See [service configuration and roles](SERVICE.md).

## Reproducible local checks

```bash
uv sync --locked --all-extras --python 3.12.13
uv run python -m pytest -q --tb=short
uv run python scripts/brain.py index
uv run python scripts/brain.py check
uv run python scripts/operations_check.py --output output/NEW_RUN/operations.json
uv build --no-sources --out-dir output/private/NEW_BUILD
uv run python scripts/release_inventory.py --artifacts output/private/NEW_BUILD --output output/NEW_RUN/inventory.json
```

Use fresh output paths. The drill creates only temporary synthetic databases,
deletes that temporary directory on completion,and never opens `.env`,production
stores or a provider. Reports contain timings/booleans,not conversation bodies.
Cold initialization and warm assembly are separate. Repeat under a declared load
before using these measurements to choose an SLO;single-process p95 is not HTTP p95.

## Backup / recovery

1. An authorized operator records memory schema/version,lineage,deletion watermark,
   artifact digest,and the deployment/configuration version. Stop writes for a
   deployment-wide consistent snapshot;do not independently copy active SQLite files.
2. Use `MemoryStore.backup(new_path)` for memory. Protect and independently retain
   the latest deletion authority,service-control/audit state and provider accounting
   state. The memory backup alone is NOT a complete service backup.
3. Restore into a new isolated path with `MemoryStore.restore(...,deletion_path=...,
   minimum_deletion_seq=...)`. The minimum watermark must come from a trusted,
   independently retained latest checkpoint,not an old backup. Missing/stale/wrong
   deletion authority must fail closed. Never reset the watermark to make restore pass.
4. Confirm surviving history and pins,reapplied tombstones,new epoch,invalidated
   summaries/replay,and successful derived-index rebuild. Run authorized tenant and
   deletion tests before enabling traffic. Do not restore old secrets or revoked
   identities blindly;reauthorize from current policy.
5. Measure from outage detection to verified service recovery,including offsite
   retrieval and operator action. The local drill measures only restore/reindex/
   assembly;it does not establish RPO/RTO or disaster recovery.

## Rollback and migration

Retain immutable previous artifacts and compatible configuration. Test a new
version on an isolated restored copy first. Schema1 currently rejects unsupported
versions;there is no forward/down migration to another schema. Never edit SQLite
`user_version` to bypass that guard. A same-version restore rehearsal is not proof
of cross-version deployment rollback. Prior to any schema-changing release,write
and test migration/reversal or a documented forward-recovery path,including all
tombstones and provider uncertainty records. Switch traffic only after checks pass.

## Outage / alerts / privacy

-Provider429:respect reset/backoff;do not rotate accounts or reset claims.
-Timeout/uncertain processing:hold the reservation;retain receipts and seek usage
  evidence before reconciliation. A fresh day does not clear an unknown charge.
-Integrity/schema/deletion mismatch:stop traffic;preserve evidence;restore in
  isolation. Do not overwrite a damaged source or silently rebuild authoritative data.
-Worker saturation:reject/backpressure;do not add unbounded queues. Deployment-wide
  capacity remains distinct from per-process concurrency.
-Before production,connect external monitoring for request failures/latency,
  worker saturation,index lag,disk growth,backup age/restore failures,auth failures,
  provider quota/uncertainty and actual-input/estimate ratios. Assign alert owners
  and escalation targets. No exporter,dashboard or alert delivery is claimed here.
-Never log prompts,answers,bearer tokens or provider keys. Keep audit access scoped;
  local restricted audit is not tamper-proof against a host administrator.

## Manual cross-platform CI

`.github/workflows/qualification.yml` is manual-only,read-only repository permission,
no deployment,secrets or model calls;it uses a locked environment and full tests on
macOS/Linux/Windows. It has NOT run remotely. Frozen research runners import POSIX
`fcntl`;Windows collection is a known qualification risk,not hidden by skips.
Do not claim three-platform support from this configuration alone.

Run `uv run python scripts/platform_check.py --output output/NEW_RUN/platform.json`
first for actual memory/worker/termination/authenticated-loopback probes. It reports
fcntl/directory-fsync capabilities separately;passing these local probes is not full
OS qualification. Use `python -m pytest` so repository examples are importable in
non-editable installs. See [platform evidence](C10_PLATFORM_REPORT.md).

Action commits were resolved from official repositories;configuration follows
[checkout](https://github.com/actions/checkout) and
[setup-uv](https://github.com/astral-sh/setup-uv). Runner/action updates still require
review;hash pinning is not a vulnerability or license audit.
