# C09 plan — security and held-out evaluation foundations

Latest2026-09-23(D078):[repair001](C09_REPAIR_REPORT.md) delivers0.9.2 opt-in
missing-WINDOW-chunk recovery and exact JSON answer validation,970 tests PASS.
Live001 previously completed under D077 with failed strict quality targets;its
32-call allowance is consumed and0.9.1 evidence preserved. Earlier NOT_RUN,
missing-worker/scorer and Kimi role-split text below is historical,superseded by
current report. Next is a fresh qualification plan,not more calls or C10 work.

Date: 2026-09-22. Status: ACTIVE implementation plan; targets and any live
evaluation remain owner-pending. Follows [C09 developer prompt](C09_DEVELOPER_PROMPT.md)
and [developer handoff](DEVELOPER_HANDOFF_PROMPT.md). Scope stops at C09; no C10–C12 work.

## Takeover amendment — D075

Continuation0.9.1: local process-backed assembly timeout/disconnect containment and
offline literal-retention/TEST_ONLY response scoring are now implemented. The earlier
gap descriptions immediately below describe increment001. Current evidence and
remaining live-approval/provenance gate are in C09_REPORT. No C10 work or live dispatch.

Owner ended the external-developer handoff; this assistant owns implementation and
review, with owner acceptance unchanged. Original work packages below are a plan,
not a completed-work claim. Incoming partial code/tests failed independent checks.
The repaired code now includes cooperative checks and a separate offline preparation
harness, not the originally proposed response recorder/scorer/leaderboard. Those
remain unfinished. Actual CLI: `python -m context_engine.evaluation.heldout check`
or `prepare --output <fresh-directory>`. Sixteen hand-authored author-visible cases,
no seeded generator or truly sealed/secret corpus. Lifecycle probes stay in tests.
Source selection is recorded; retained-answer scoring is not implemented. Hard CPU
and disconnect containment remains a C09 gate, not automatically moved to C10.
No live execution, scoring thresholds, security waiver or enterprise acceptance is
approved by this amendment. See C09_REPORT for final verified scope and gaps.

## Baseline and preservation

- Verified this session before edits: full suite 752 passed / 2 known service warnings
  (~102 s); `brain.py check` passes; package 0.8.0 code hash matches freeze
  `1712dd4b08cf80cba1408dde2d8afae45920905a5362da067b79d17607763806`; no project
  runner processes.
- Preserve: PRD, `archives/`, `output/private/c06-frozen-env`, all C06/Gemini
  snapshots, journals, ledgers, amendments 001–009, `.env*`. No C06 rerun, no live
  inference, no credential access. Offline tests use synthetic transports/keys only.
- Version strategy: new code ships as package **0.9.0**. Before edits, archive the
  0.8.0 wheel and freeze to `archives/c08/`. After code stabilizes, regenerate
  `freeze.json` through the existing deliberate authoring step (old freeze preserved
  in the archive). C06 reproducibility is unaffected: it runs from the archived 0.7.2
  environment. Held-out fixtures get a separate hash-bound freeze and identity
  (`heldout-*`), never sharing the C04/C06 manifest or snapshots.

## W1 — Threat model and security regression tests

Deliver `docs/C09_THREAT_MODEL.md` and `tests/test_c09_security.py`:

- Cross-tenant/cross-session denial on every route (read, turns, pins, context,
  export, delete, audit) including identical resource IDs across tenants, warm
  replay caches, stale revisions and concurrent access; denied requests provably
  create no scope/rows and make no provider call.
- Credential matrix: missing/malformed/expired tokens, duplicate Authorization
  headers, wrong issuer/audience/algorithm/kid, forged signatures with locally
  generated RSA keys, session allowlists, reader→write and operator→admin
  escalation attempts.
- Hostile history/tool/retrieved/summary content: exactly one system message,
  all evidence inside labelled user-data blocks, forged SourceRef rejected,
  adversarial Unicode/delimiters preserved as data. LLM behaviour is explicitly
  out of scope (untested, labelled).
- Deletion/expiry propagation: chunks/summaries/pins/scoped replay invalidated;
  restore with current deletion authority cannot revive deleted facts.
- Synthetic canaries asserted absent from error responses, audit rows, default
  diagnostics and logs; explicitly authorized content APIs (admin export) are
  distinguished from leakage.
- Acceptance: each abuse case has a regression test or an existing-test citation;
  every confirmed gap gets a focused fix + test; findings carry
  severity/preconditions/residual risk in the report.

## W2 — Resource bounds and cooperative cancellation

- New small core module `work.py`: `WorkCancelled` typed error, a `Cancellation`
  protocol and `DeadlineCancellation` (injectable clock). No new dependencies.
- Thread an optional `cancellation=` through `assemble_context` (new
  `ContextCarrier.cancellation` field, default `None` = unchanged behaviour),
  with checks inside the bounded loops: CAP per message, shared WINDOW planner per
  candidate, RETRIEVE chunking/selection, final shrink. `MemoryStore.assemble` and
  `index_batch` accept and forward/check it. Core stays independent of
  provider/service/evaluation.
- Service: `create_app(..., limits=...)` with a validated assembly wall-clock
  budget (finite default, configurable via optional `limits` config key);
  cancellation maps to a content-free 503; audit outcome recorded.
- `tests/test_c09_bounds.py`: oversize/streamed bodies, deep/malformed JSON, large
  Unicode/tool payloads, per-scope turn/chunk/byte bounds, quota races, concurrent
  assembly, deterministic cancellation (counting token) proving loops stop without
  partial commits, and wall-clock deadline evidence with generous margins.
- Honest gate: cooperative cancellation inside bounded engine loops, not
  preemptive thread kill; client-disconnect mid-sync-handler and host-level CPU
  isolation remain C10 proposals (process/worker isolation). No SLO or DDoS claim.

## W3 — Held-out evaluation protocol, fixtures and offline harness

- `docs/C09_EVALUATION_PROTOCOL.md`: categories, independent scenario IDs,
  development vs sealed split, deterministic seeded generation with recorded
  provenance, leakage risks, scoring/denominators, abstention/hallucination
  handling, confidence limits and **proposed** thresholds (owner-pending; C06's
  29/31 is not imported).
- New `src/context_engine/evaluation/heldout/` package + `data/` fixtures:
  categories stale/contradictory (temporal authority), paraphrase, multilingual,
  hostile tool output, no-answer (abstention), large history, plus deterministic
  deletion/expiry lifecycle probes. Ground truth (acceptable answers, superseded
  values, source/effective-time lineage, injection markers) lives in a separate
  evaluator-only resource; leakage gates mirror V2.
- Harness: loader, fixture/leakage validators, hash-bound manifest, deterministic
  offline preparation (fit/retention/security-structure metrics), response
  recording with `test`/`live` provenance, offline scoring/report export
  (scorecard JSON + leaderboard MD), validity gates H1–H5. CLI `heldout-check` /
  `heldout-plan` mirror the offline C04 commands. TEST_ONLY synthetic answers are
  never presented as model quality.
- Artifacts in new `output/c09-*` paths only; reports regenerate with networking
  disabled.
- Live evaluation: **not performed**. The protocol carries a bounded live
  proposal (models, probe count, 900/3000 budgets, 256 completion, shared existing
  account ledger, $0 free-tier or explicit paid ceiling, stop conditions, privacy)
  for owner approval. Full C09 quality qualification stays pending until approval
  and execution.

## W4 — C06 carry-forward (documentation only)

- S11/S12 restated as open experiment proposals; held-out categories give
  prospective coverage; no tuning of the frozen C06 algorithm, thresholds or
  results; 124 A0 non-fits and seven errors preserved and referenced, not hidden.

## W5 — Verification, memory and handoff

- Focused tests, then full `uv run --locked pytest -q`; Ruff check/format; lock
  check; wheel/sdist build; clean installed-wheel import/demo checks (offline).
- Update REQUIREMENTS/CHECKPOINTS with actual status (C09 expected to remain
  ACTIVE: offline stages ready for review, live held-out quality pending owner
  approval). Archive JOURNAL (at 148/150 lines) before appending; keep
  INDEX+STATE ≤ 900 words; run brain index/check.
- Deliver `docs/C09_REPORT.md` and `docs/C09_ARCHITECT_REVIEW.md` with the
  handoff's seven review-package sections and PASS/FAIL/BLOCKED/NOT_RUN per
  criterion.

## Risks and mitigations

- Freeze churn: any `.py` change alters the package code hash → controlled
  refreeze at the end with the old freeze archived; both freezes recorded in the
  report. Held-out freeze is separate so future C06-family artifacts never depend
  on C09 files.
- Behaviour drift from the cancellation field: default `None` keeps byte-identical
  assembly; the existing flagship checks (637/900 demo, 804/900 benchmark) must
  still pass.
- Timing tests: deterministic counting-token proofs primary; wall-clock assertions
  use wide margins to avoid flakes.
- Fixture exposure: fixtures are newly generated for C09, sealed split unused for
  any tuning; if results ever influence implementation, that exposure is recorded
  and a fresh split is required before held-out qualification claims.

## Open owner choices (non-blocking)

1. Live held-out evaluation approval: protocol/targets/budget/stop conditions in
   C09_EVALUATION_PROTOCOL's live proposal section.
2. Endorse cooperative cancellation now + process isolation later (C10 proposal).
3. Held-out scenario categories/threshold review (synthetic workload choice is an
   engineering default, not a product commitment).
