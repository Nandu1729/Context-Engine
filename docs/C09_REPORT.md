# C09 report — qualification preparation and preserved live evidence

Latest D088:[policy003 live diagnostic](C09_POLICY_LIVE_REPORT.md) completes16/16:
BASELINE5/8,CANDIDATE5/8;one improvement and one regression,target FAIL. Do not
adopt candidate.6,956tokens/$0configured,691prior rows preserved,offline replay/
zero-call resume verified. Budget exhausted;C09 ACTIVE,no further inference.

Latest D087:[fresh policy comparison](C09_POLICY_QUALIFICATION_REPORT.md) prepared
offline:8cases,32conditions,all evidence retained,29targeted tests PASS,zero calls.
16unique payloads;proposed16-call diagnostic amendment needs explicit approval.
Author-visible cases,not independent quality evidence;C09 remains ACTIVE.

Latest D085:[conflict analysis](C09_CONFLICT_ANALYSIS_REPORT.md) verifies both facts
and abstention instructions were present. Added opt-in generic evidence-policy
candidate;32offline assemblies fit without retention changes. No API calls or
default changes;semantic effectiveness unproven,C09 ACTIVE.

Latest D084:[structured smoke](C09_STRUCTURED_SMOKE_REPORT.md) completes2/2 calls:
both valid JSON,but only1/2 correct (conflict case fails).1,356tokens/$0configured,
all689 prior rows preserved,35focused tests PASS,offline replay identical.
Approval exhausted;C09 ACTIVE,next offline contradiction analysis,no new calls.

Latest D083:[structured-answer integration](C09_STRUCTURED_ANSWER_REPORT.md) adds
an opt-in strict JSON-schema client/serializer with full schema-budget accounting,
request-key separation and one-attempt policy.117 offline checks PASS,no API calls.
Core0.9.2 unchanged;provider schema acceptance/mitigation NOT_EVALUATED,C09 ACTIVE.

Latest D082:[two-call diagnosis](C09_RESPONSE_DIAGNOSTIC_REPORT.md) confirms raw
provider content is empty in one diagnostic;the other returns valid UNKNOWN JSON.
Local parser preserves both.1,342tokens/$0configured;687 prior rows unchanged,
offline replay identical. No calls remain authorized. Upstream cause unresolved;
evaluate response-format enforcement offline,not a blind full-matrix rerun.

Latest offline continuation:[empty-answer diagnosis](C09_EMPTY_ANSWER_REPORT.md).
Parser preserves response content;client success denotes a stop completion,not a
usable answer. Added an opt-in caller example rejecting empty/malformed answers
without retry or accounting changes.105 targeted tests PASS in0.43s,no API calls,
package0.9.2/frozen scores unchanged. Upstream cause remains unresolved;C09 ACTIVE.

Latest D080:[qualification live002](C09_QUALIFICATION_LIVE_REPORT.md) finishes32/32
requests. PRIMARY14/16 correct versus CONTROL11/16;strict8/8-per-budget target FAIL.
Five empty answers,two CONTROL missing-evidence abstentions;zero API errors,
truncations,forbidden answers,input-cap overruns or unknown usage.24,474new tokens,
$0 configured;all655 earlier account rows preserved. Offline replay identical.
C09 ACTIVE;next offline empty-answer diagnosis,no new calls. D080 budget consumed.

## Previous qualification preparation

Latest continuation2026-09-23:[qualification002-r1](C09_QUALIFICATION_REPORT.md)
prepares32 fresh paired synthetic requests on unchanged0.9.2,with budgeted strict
answer instructions and exact TEST_ONLY scoring. Recovery retention7/7 versus
default6/7 at both900/3000;provider accuracy NOT_EVALUATED. No API calls. Cases
are author-visible,pending owner review and a new bounded live authorization.
Full run:997 passed,two documentation-fixture failures;fixed missing archive-copy
fixture and reran affected tests successfully (details in qualification report).
C09 stays ACTIVE,not accepted. No second full rerun:owner requested fast handoff.

## Previous repair increment

Latest continuation2026-09-23: **package0.9.2**,970 tests PASS,build/installed HTTP
demo PASS. [Repair report](C09_REPAIR_REPORT.md):opt-in recovery of missing original
chunks from CAP-shortened WINDOW messages,and strict optional JSON answer validation.
PRD retrieval default remains unchanged;57 new development regressions,no new API
calls. Old live001 reproduces through its preserved0.9.1 environment,score8/32
unchanged. C09 remains ACTIVE pending fresh qualification;not owner-accepted.

## Previous0.9.1 live/offline increment

Updated2026-09-23. Package **0.9.1**. Local engineering and bounded live001 experiment
complete for review; **C09 remains ACTIVE because strict quality targets failed**.
Owner acceptance is not inferred. [Live report](C09_LIVE_REPORT.md):32/32 responses,
8/32 exact matches,zero provider errors/uncertain usage/forbidden answers/input-cap
overruns.12 misses add wording,3 alter identifier hyphens,9 lack needed evidence.
913 regression tests PASS;28,553 new tokens,$0 configured. Existing623 account
records preserved;32 C09 usage entries appended.878 protected C06/Gemini/archive
files unchanged. No more calls remain in this authorization.

Earlier takeover evidence is preserved in [increment001](C09_OFFLINE_001_REPORT.md).
The sections below document the preceding offline engineering increment; live001
adds a separate external runner and identity without changing the frozen package.

## Delivered

- Service `/context` now runs snapshot/index/assembly/final revision checks in a
  disposable subprocess. Authorization/quota admission precedes worker launch.
  Default2 worker slots per service process, configurable1–8; no waiting queue;
  excess requests receive503 `assembly_busy`.
- Parent-enforced default30s assembly deadline (configurable >0 to300s) covers spawn
  and computation. Timeout, ASGI disconnect, request-task cancellation and shutdown
  kill/reap the child before its slot is reused, including late startup races.
  Cooperative SDK cancellation remains available but is no longer the service's
  only protection. Non-assembly handlers remain ordinary bounded service operations.
- Worker input/output capped at262,144/2,000,000 bytes; fresh isolated Python
  process, no shell or user-selected executable; API/service credentials not
  inherited; stderr discarded. The worker executes trusted package code, not tool
  instructions. This is process containment, not an OS security sandbox/RSS limit.
- Real-process tests verify non-cooperative termination, no orphan PID, capacity
  recovery, startup/shutdown races, sanitized failures, environment isolation and
  SQLite rollback/reopen after kill inside an open transaction. The ASGI test proves
  disconnect forwarding through middleware and `work_cancelled` audit recording.
- Added a separately frozen scoring protocol. Actual rendered fragments are checked
  against designated source facts; selection of an original message alone is not
  retention. Response import binds to a reproducible preparation hash/runtime and
  per-request hash; duplicate/unknown/stale/live-labeled records are rejected.
- TEST_ONLY scoring handles normalized exact match, correct abstention, forbidden
  answers, errors/missing slots and category/split/variant/budget groups. All planned
  slots remain in denominators. It cannot turn supplied synthetic answers into
  live model evidence. The subsequent live001 external dispatcher/receipt validator
  uses its separately approved execution protocol; TEST_ONLY artifacts stay unchanged.

## Offline package verification preceding live001

`uv run --locked pytest -q --tb=short`: **891 passed**,2 existing service dependency
warnings,in107.71s. This includes139 C09 tests. Final brain integrity passes with
46 indexed Markdown documents,767/900 hot-memory words;
PRD source hash,73 section mappings,27 V1 items and13 checkpoints unchanged.
`ruff check src tests`,scoped formatter check,`uv lock --check --offline` and
`git diff --check` all pass. All four archived wheels/freezes independently match.
Focused worker tests:19 PASS; held-out/scorer tests:31 PASS. Source/installed-wheel
loopback demos PASS (auth, tenant separation, export denial, API/SDK equivalence,
content-free audit); zero external/inference calls and no persistent demo server.
Offline wheel/sdist build, lock check, lint and diff checks PASS. Clean installed
wheel at `/tmp/context-c09-091-wheel.u42fsw` validates version/resources/sourcefreeze,
does not import optional service/provider modules through core import, and runs
the process-backed HTTP demo successfully.

Code hash: `e65cb926df31f42d0f06a0c72c67f86860633ba56d00dbb075cf33b9f2ccfadf`.
Previous0.9.0 wheel/freeze preserved in `archives/c09-offline-001/`;0.7.2/0.8.0
archives and all old evaluation artifacts remain unchanged. Dependency versions
unchanged; lock update is own package0.9.0→0.9.1.

## Offline evidence (not model quality)

[Preparation003](../output/c09-offline-003/report.json) and
[scorer003](../output/c09-scoring-003/report.json) each reproduce byte-for-byte in
separate `*-replay` directories with sockets disabled.64/64 requests PREPARED;
36 literal-retention slots true,20 false,8 no-answer/not-applicable. Repeated
variant/budget slots are not64 independent scenarios.

Evaluation split only (7 eligible source-retention cases plus1 no-answer case each):

| Variant |900-token budget |3,000-token budget |
|---|---|---|
| WINDOW |0/7 literal facts retained |6/7 |
| CAP_RETRIEVE_WINDOW |6/7 |6/7 |

No algorithm was tuned from these measurements. CAP-middle loss remains visible
(S11), and estimated fit is not actual provider calibration (S12).
The saved scorer report deliberately has **64 missing answers,0 correct** and
answer quality **NOT_EVALUATED**. Unit tests with perfect fake answers exercise
the scorer but are never exported as real model-quality success.

## Commands

```sh
uv run --locked python -m context_engine.evaluation.heldout check
uv run --locked python -m context_engine.evaluation.heldout prepare --retention --output output/c09-new-preparation
uv run --locked python -m context_engine.evaluation.heldout score-test --responses /path/to/test-only-responses.json --output output/c09-new-scoring
uv run --locked pytest -q --tb=short
uv build --offline
```

Fresh destinations only. TEST_ONLY envelope and exact bindings documented in
[protocol](C09_EVALUATION_PROTOCOL.md). Synthetic cases remain author-visible,
not independently curated production evidence.

## Remaining acceptance gate

Local worker containment, scoring and receipt-provenance gaps are addressed. D077's
32-call experiment is complete, but exact-answer quality failed in all four groups
(2/8 each). Independent qualification and F06/S11 retention are not resolved.
Next: exact identifier/output contract and source-chunk retention work, then a fresh
predeclared independent evaluation. Preserve failed scores; no relaxed grading,
extra calls,paid spending,account rotation,C06 rerun or deployment is authorized.

OS-level stuck process creation/reaping, host memory limits, TLS/IdP provisioning,
distributed/global quotas, cross-platform/load/SLO testing remain explicit operational
limits; tested termination is not a strict whole-HTTP latency or production SLO.
Earlier committed index batches can remain after cancellation; originals/deletion
authority are preserved, and the current SQLite transaction recovers on reopen.

Intermediate002 artifacts/runtime are preserved in `archives/c09-offline-002/`.
Final review added a killed-worker stdout-drain fix and continuous-output regression
to prevent pipe backpressure delaying reaping.003 is the final evidence identity.
