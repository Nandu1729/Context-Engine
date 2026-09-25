# C10 platform verification — D089

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

## Remaining gates

Windows is untested and historical live runners still require POSIX `fcntl` and
directory fsync. A local container is not remote CI,production hosting,Windows
support,sustained-load evidence or disaster recovery. C10 remains ACTIVE;C09's
failed quality gate and C12's pilot/owner acceptance blockers are unchanged.
