# C09 historical increment 001 — takeover and offline foundations

2026-09-22. Package **0.9.0**. Status **ACTIVE**, not complete or owner-accepted.
The owner ended the external-developer handoff; this assistant reviewed and
continued the partial implementation. No live inference, credential reads,
deployment, C06 reruns or historical-result changes.

## Outcome

- Reviewed all incoming changed core/memory/service code, new security/resource
  tests, version/lock state and C09 plan. Preserved unrelated C06 documentation and
  artifacts already in the worktree. Verified the archived C08 baseline.
- Repaired skipped credential assertions, invalid cross-scope pin/DELETE requests,
  victim-quota test target/count, weak identical-canary checks, broad exception
  assertions and incorrect assumptions about CAP preserving every working character.
  Added warm-index tenant separation, protected-memory denial and captured-log checks.
- Completed cooperative cancellation checks at entry/stage/return boundaries,
  inside CAP/chunk loops and before index commit. Added deterministic rollback and
  single-large-message tests; normal uncancelled output remains unchanged.
- Aligned package/lock/source freeze for0.9.0, preserving0.8.0 archive and every
  C04 fixture hash. Documented security risks and incomplete gates in the
  [threat model](C09_THREAT_MODEL.md).
- Added a separate [pre-measurement protocol](C09_EVALUATION_PROTOCOL.md), hash-bound
  synthetic scenarios/truth and offline preparation CLI. Sixteen cases, eight
  categories, two splits, two budgets and two variants: **64/64 prepared**, zero
  provider calls. Network-disabled replay is byte-identical. This is not64 model
  answers, nor proof of retained-answer accuracy.
- Updated checkpoint/requirements routing and project memory; archived the149-line
  C06 journal rather than deleting history. D075 supersedes the Kimi role split.

## Verification evidence

Incoming state independently observed: `uv run --locked pytest -q` could not run
because the lock was stale. Direct suite:27failed,754passed,54errors; most inherited
evaluation failures were the unrefreshed new-version source freeze. Focused incoming
C09 tests:8failed,75passed. These failures were investigated, not hidden by disabling
tests. Deliberate source refreeze applies only to the new0.9.0 workspace.

| Command/check | Result |
|---|---|
| `uv run --locked pytest -q --tb=short` | **857 passed**,2 existing service dependency warnings;99.29s initial,98.41s final repeat |
| New C09 coverage within full suite | **105 tests**:89 security/resource +16 harness |
| `ruff check src tests` | PASS |
| `ruff format --check src tests/test_c09_bounds.py tests/test_c09_security.py tests/test_c09_heldout.py` | PASS,57 files |
| `uv lock --check --offline` | PASS,46 packages; own package version only, no dependency upgrades |
| `uv build --offline` | PASS,wheel and source distribution |
| Clean isolated wheel install, offline | PASS,0.9.0/resources/freeze; core import does not load FastAPI/httpx |
| `uv run --locked python -m context_engine.service.demo` | PASS,real loopback HTTP; auth/tenancy/export/API–SDK/audit checks;0 external/inference calls;server stopped |
|64-slot preparation twice with sockets disabled | PASS,64 PREPARED; report JSON/README byte-identical |
| `git diff --check` | PASS |
| Brain index/integrity | PASS,45 indexed Markdown documents,783/900 hot-memory words; source/mappings/links/current index verified |

Two warnings are the existing Starlette HTTPX/AnyIO deprecations, not test failures.
No synthetic model responses are scored as real answers.

## Artifacts and reproduction

- [Offline report](../output/c09-offline-001/report.json),
  [summary](../output/c09-offline-001/README.md),
  [independent replay output](../output/c09-offline-001-replay/report.json).
- Fixtures/manifest: `src/context_engine/evaluation/heldout/data/`.
- Build: `dist/context_engineering_core-0.9.0-py3-none-any.whl` and matching tar.gz.
- Clean-wheel environment used: `/tmp/context-c09-wheel.cXfMVf` (temporary verification
  artifact; not a required runtime or historical archive).

```sh
uv run --locked python -m context_engine.evaluation.heldout check
uv run --locked python -m context_engine.evaluation.heldout prepare --output output/c09-your-new-run
```

The output directory must not exist. This CLI has no provider/key/live mode and
never overwrites previous reports. New-version code hash:
`9395ab7ce378b0532fae9b016baeb25df7e68b72950db7c18277688fd962b234`.
C08 archived code hash:
`1712dd4b08cf80cba1408dde2d8afae45920905a5362da067b79d17607763806`.
C06 archived code hash remains:
`efeaa9f2459e067ac21f93a960ec0cc537c0d266e42c25a98aa67e1ae81da6a6`.

## Acceptance matrix and remaining work

| C09 criterion | Status / boundary |
|---|---|
| Cross-scope retrieval/cache/export/delete denial | PASS for tested local service and existing SDK contracts |
| Data cannot grant service permissions | PASS structural/authorization tests; model obedience NOT_EVALUATED |
| Input/storage bounds and cooperative cancellation | PASS local regressions; not sustained load evidence |
| Hard CPU timeout / disconnect cancellation | **OPEN** — sync/native work cannot be forcibly stopped |
| Secrets/PII logging review | PASS within application paths using synthetic canaries; external logging not qualified |
| New protocol frozen before preparation/tuning | PASS separate manifest; no algorithm tuning; owner targets pending |
| Independent unseen quality / calibration | **NOT_RUN**; author-visible synthetic set is not production qualification |
| Retention/answer scoring, provenance-aware response recording | **NOT_IMPLEMENTED** in new harness |
| High-severity issues closed or release waiver accepted | **OPEN**; F03/F05 remain; no waiver inferred |

The original plan included more than this delivered increment. In particular,
response import/scoring, a real independent held-out evaluation and enforceable
worker isolation are not claimed done. Cooperative checks cannot preempt one large
tokenizer/BM25/SQLite call; a disconnected client may leave threadpool work running.
Some earlier completed index batches can persist safely when later assembly cancels.

C06 remains complete with124 non-fits/seven errors and S11/S12. The primary29/31
fixture PASS and historical provider overruns are not changed or generalized.

## Next action

Continue C09: implement bounded isolated assembly workers with timeout/disconnect
cleanup and regression evidence; then complete separate retention/answer scoring
and provenance gates. Before any live held-out calls, finalize exact model/quota/
ledger/targets and obtain owner approval for the bounded execution protocol.
Do not move to C10 or rerun C06 as a substitute for these gates.
