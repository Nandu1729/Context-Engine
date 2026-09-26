# C10 platform verification — D089

Latest:D093 owner approved and implemented the [versioned admission repair](C10_ADMISSION_REPAIR.md).
Package0.9.3/schema2 replaces timestamp uniqueness;explicit migration and regression
checks added. Original0.9.2 historical runtime preserved. Next NEW Windows diagnostic
must validate the repair;prior failures/history below remain unchanged.

2026-09-25. Added `scripts/platform_check.py`:real deletion-safe memory recovery,
two isolated assembly jobs compared with SDK output,reaped workers/reusable capacity,
subprocess kill/reap,and authenticated loopback HTTP. Results expose POSIX research
runner capabilities separately and never claim full platform qualification.
Errors are content-free;outputs refuse overwrite;the script hash binds the report.

Seven targeted tests PASS2.89s on macOS,including failure sanitization,missing
fcntl reporting,LF/CRLF child readiness,credential exclusion,and no-overwrite behavior.
[Current macOS report](../output/c10-platform-002/report.json):four probe groups PASS.
Earlier unbound preflight001 is preserved;002 records the finalized runner hash.

## Linux verification

Docker Desktop was installed but stopped. Started the existing local engine and
pulled pinned image `python@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36`.
Container:Linux aarch64/kernel6.12.76-linuxkit,Python3.12.13,2CPU/2GiB limit,
uv0.11.16,locked all-extras dependencies,non-editable package installation.

Used a read-only task copy excluding `.env*`,private directories,SQLite stores and
virtual environments. No host Docker socket,privileged mode,host network,provider
keys or customer data mounted. Only the separate temporary results directory is
writable. Setup downloads public image/packages/tokenizer resources;no inference.
Containers use `--rm`;the source checkout and historical artifacts remain untouched.

First Linux preflight passed all four groups. The first suite invocation failed
during collection because console-entrypoint `pytest` omitted the repository root
needed to import `examples`. Retained [failure evidence](../output/c10-platform-linux-001/collection-failure.xml).
Changed CI/runbook to `python -m pytest`,matching successful local invocation.
No test exclusions or engine changes used to address the collection failure.

Second [Linux preflight](../output/c10-platform-linux-002/preflight.json) passed all
four groups. [Full-suite evidence](../output/c10-platform-linux-002/tests.xml):
1,117 passed,1 failed,2 dependency warnings,316.09s. The failure was the original
C06 accounting-evidence test requiring a private owner screenshot intentionally
excluded from the container;not a demonstrated engine failure.

After staging that read-only Linux snapshot, made the unit test portable with
temporary synthetic evidence and three tamper cases (plan,image,missing image).
Production verifiers and historical evidence remain unchanged. The original private
audit remains separately opt-in via `CONTEXT_ENGINE_PRIVATE_AUDIT=1`.
Original audit before repair:1 PASS1.28s. All recovery009 tests after repair,
including the real private audit:25 PASS11.13s on macOS;scoped lint PASS.
The repaired tests were NOT in the Linux snapshot;Linux revalidation remains pending.
No further container or full-suite run started after the owner's manual-first request.

## Next manual step

From the project root, run these checks yourself and share their final summaries:

```sh
uv sync --locked --all-extras
uv run python -m pytest -q --tb=short
```

For Linux/Windows verification, use the same commands in a clean checkout on that
platform,or manually dispatch the qualification workflow after reviewing/publishing
the changes to your own GitHub repository. Local macOS results do not replace Linux
or Windows evidence. Do not copy `.env` or private evidence to CI. The optional
original-evidence audit is local-only and requires the preserved private files.

Disposable test containers auto-remove. Docker Desktop,the downloaded image and
temporary staging/dependency cache remain available;no unrelated images were removed.

## CI / checkout improvements

Manual CI now executes the platform preflight before the full suite and uses
`uv run python -m pytest`. It remains manual-only,no deployment and no inference.
`.gitattributes` requests LF for hash-checked source/configuration/Markdown on future
checkouts;binary artifacts remain binary. No renormalization or history rewrite.
Verified git attributes and unchanged0.9.2 core source hash locally.

## D090 — owner-approved platform scope (2026-09-26)

Owner screenshots of GitHub run36219698403 show Ubuntu PASS9m28s,macOS PASS8m25s,
Windows FAIL1m12s. Windows setup,brain checks and platform preflight passed;
pytest stopped at collection with17 errors,so operations/build did not execute.
Screenshots,not downloaded full logs or independently verified commit provenance,
are the evidence available here. No remote test-count claim.

Local inspection confirms the displayed traceback reaches the unconditional
`fcntl` import in frozen c06_complete.py. Historical C06/C09/Gemini runners depend
on POSIX locking. Owner explicitly approved this scope amendment after explanation:

- Linux/macOS retain the complete test suite.
- Windows excludes exactly17 named historical-runner modules before import,via
  `tests/conftest.py`. Every excluded filename appears as NOT TESTED in the terminal
  summary,even with quiet output. These are exclusions,not passing or executed tests.
- No wildcard exclusions,no automatic exclusions of future tests,no simulated
  locking. Engine,service,memory,provider and portable evaluation tests remain required.
- Workflow job/step labels expose the differing scopes. Frozen scripts,core source,
  safety guards and historical evidence are unchanged.

Verification:7new scope tests PASS0.28s,scoped lint PASS;local full collection
1128tests in0.46s without import errors. Scope tests exercise actual tiny subprocess
pytest collections,proving the Windows selection prints all exclusions and the
non-Windows selection still attempts the historical import. This does not emulate
Windows runtime or establish Windows product correctness. No full local rerun.

Next manual action:commit/push these reviewed changes,then start a NEW workflow
run on that commit. Re-running the old failed job uses old code and cannot verify
this repair. Share the new Windows test summary/errors;do not add further exclusions
merely to turn CI green. No commit,push or remote dispatch performed by the assistant.

## Remaining gates

Latest finding (2026-09-26):logs_98114467083.zip/run36230402597 on4b03d54 shows
3concurrency failures/1observer PASS in4.39s. Every captured storage error is INSERT
code1555 (SQLITE_CONSTRAINT_PRIMARYKEY),with service_unavailable/503 responses.
ControlStore admissions use PRIMARY KEY(tenant,at);timestamps are not unique request
identifiers. A local isolated fixed-clock reproduction sends two distinct request
IDs at123456.0:the first succeeds,the second produces the same1555,and only one
audit is retained. This confirms the collision defect without Windows or inference;
the prior lock-timeout hypothesis is not the cause of these observed failures.

Recommended repair:separate admission row identity from its timestamp,retain atomic
quota counting/audit behavior,and test same-timestamp admissions and exact quota
boundaries. A schema transition must preserve existing admission/audit/session/policy
records and require explicit operator migration. Do not use INSERT OR IGNORE (would
undercount),drop quota history,increase timeout or relax the200/409/429 assertions.

Implementation pending owner direction because this changes the frozen0.9.2 runtime
and service-control schema. Preserve the old runtime/evidence and give the repair a
new version;do not refreeze past experiments against changed code. No source/schema
changes or real database migrations made during this diagnosis. No further Windows
diagnostic rerun needed for this known defect;other Windows failures remain unresolved.

D092 update (2026-09-26):logs_98100003759.zip includes the actual Windows diagnostic
from run36224788664/commit417c611. It collected862tests and stopped after58PASS/1FAIL
in16.07s. `test_concurrent_writes_are_serialised_by_revision` observed200,409,503;
one successful write assertion passed,but503 violates the test's required200/409
outcomes. This identifies the failing test,not its underlying exception. The log
records statuses only;storage contention is a hypothesis,not a confirmed root cause.
It also does not establish why the earlier full run failed to exit.

Local targeted baseline:all3concurrency tests PASS0.40s. Added test-only connection
observation recording static SQL stage and numeric SQLite code,plus allowlisted API
error codes in assertion diagnostics. No exception text,SQL arguments,credentials,
paths or response bodies logged. Exceptions still propagate;timeouts,locking,
expected status sets,thread counts and frozen core remain unchanged. A deterministic
two-connection lock test verifies SQLITE_BUSY remains a failure and metadata capture.
All4focused checks PASS0.41s;lint PASS. This is diagnostic instrumentation,not a fix
claim or weakened assertion. No new exclusions or product changes.

Updated Windows diagnostic runs these4checks first (2-minute step cap). Only if they
pass does the existing first-failure suite run. Owner should commit/push and launch
a NEW Windows diagnostic,then share the log. No full local suite,API calls,automatic
remote run or assumption that other Windows failures are resolved.

D091 update (2026-09-26):owner run36222231008 uses934aa52. Windows portable suite
now executes,shows failures/errors,reaches100% progress,and exceeds30-minute job
limit. Cause of failures/delayed exit is unknown;100% is not success. Raw-log link
returns BlobNotFound. Supplied logs_98093417183.zip contains Ubuntu/macOS logs only;
they bind934aa52 and confirm successful jobs,not Windows correctness.

Owner approved a separate manual `windows-diagnostic.yml` workflow named
**Windows diagnostic (first failure, no deployment)**. It runs only Windows with
`pytest -vv -x --tb=short --capture=tee-sys`,unbuffered output,7-minute test step and
10-minute job cap. Prints test names/stops at first failure;does not increase the
old timeout,change product code,add exclusions or run inference. If cleanup itself
hangs,the last printed test narrows diagnosis;this does not guarantee a full trace.
The existing qualification workflow remains unchanged. Diagnostic success alone
would not establish full-suite qualification.

Next:owner commits/pushes the new workflow and memory/report changes,then selects
**Actions → Windows diagnostic (first failure, no deployment) → Run workflow**.
Share the first failing test/traceback or last named test if it times out. No need
to rerun Linux/macOS. Assistant has not committed,pushed or dispatched anything.

Windows portable-suite verification remains pending;historical live runners are
explicitly unsupported there (POSIX locking/directory fsync). Cross-platform CI is
not production hosting,sustained-load evidence or disaster recovery. C10 remains
ACTIVE;C09's failed quality gate and C12's pilot/owner acceptance blockers remain.
