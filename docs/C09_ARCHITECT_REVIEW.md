# C09 engineering review — single-assistant continuation

D080 result:[live002](C09_QUALIFICATION_LIVE_REPORT.md) completes32requests;PRIMARY
14/16 versusCONTROL11/16 but required16/16 fails. Five empty answers remain failed,
with root cause unresolved. Retention7/7 does not guarantee a nonempty/correct answer.
No inference remains authorized. F05 quality remains OPEN;offline diagnosis next.

Latest offline evidence:[qualification002-r1](C09_QUALIFICATION_REPORT.md) freezes
fresh author-visible cases and budgeted exact-answer integration without changing
0.9.2. Literal retention7/7 primary versus6/7 control at both budgets;F05 model quality
remains OPEN. No API calls or independent review. Owner review/new bounded approval
and separately frozen dispatcher required before live validation.

Current0.9.2 review:[repair001](C09_REPAIR_REPORT.md) adds a default-off retrieval
extension with finalizer source/dedup validation and strict optional answer parsing.
970 tests PASS,including persisted-memory deletion/parity and source forgery checks.
PRD§13 default remains unchanged. Parser validates syntax/identifiers,not factual
correctness;no new model-quality measurement or independent acceptance is claimed.
Actual live001 remains byte-identical under its archived0.9.1 environment.

Latest2026-09-23: [live001 report](C09_LIVE_REPORT.md) adds32 ledger-bound provider
responses under D077,913 passing local tests and byte-identical offline report replay.
Exact-match target FAIL(2/8 per condition);zero forbidden answers/input-cap overruns
in this small sample,not universal guarantees. F05 now has measured but insufficient
quality evidence; F06 remains OPEN. C09 is ACTIVE,not owner-accepted. Frozen external
runner never reruns uncertain claims; original623 attempt records and878 protected
files verified unchanged. The former NOT_RUN description below is historical.

Current0.9.1 supplement: bounded workers now kill/reap on timeout,disconnect,
cancellation and shutdown;19 process tests cover startup races, stdout flood,
recovery and credential isolation. Separate frozen retention/TEST_ONLY response
scoring implemented;31 held-out/scoring tests pass. Sections below describe earlier
0.9.0 findings. F03 local assembly containment addressed; F05 independent live
quality/calibration remains OPEN. Current evidence: C09_REPORT. No independent
review/owner acceptance inferred; C09 remains ACTIVE.

2026-09-22. D075 ended external-developer handoff. This is a documented code/test
review by the implementing assistant, **not independent approval or owner acceptance**.

## 1. Scope and diff

Reviewed incoming changes to context/pipeline/errors/work, CAP/shared WINDOW/
RETRIEVE, memory indexing/assembly, service app/configuration, package version,
lock state and new C09 tests. Repaired these and added heldout package/data/tests,
threat/protocol/report documentation and brain routing. No C10–C12 implementation.
Historical C06 worktree edits predate this takeover and were preserved.

## 2. Architecture

Optional cooperative token is core-only and defaults toNone. Service owns deadline
configuration; memory transactions roll back a cancelled index batch. Core imports
neither service nor providers nor evaluation. A new evaluation package depends on
core, never the reverse. Separate manifest/runtime identity prevents silently
presenting C09 experiments as the frozen C06 run.

## 3. Findings and fixes

F01 test bypass/invalid requests/weak assertions repaired; F02 cancellation
granularity/precommit checks improved; F04 lock/sourcefreeze mismatch repaired.
These fixes and regressions are detailed in C09_REPORT and C09_THREAT_MODEL.
F03 hard worker containment, F05 live quality/calibration, F06 retention remain open.
No owner security-risk waiver inferred and no hidden checkpoint migration.

## 4. Verification

Full857-test suite passes;105 C09 tests included. Offline build/lock/lint/format pass.
Clean wheel has correct resources/freeze and isolated core imports.64/64 offline
slots prepared and socket-disabled repetition is byte-identical. Test counts and
commands in C09_REPORT are actual observations, not inherited claims.

## 5. Evidence integrity

C08 wheel/freeze preserved;0.9.0 sourcefreeze deliberately updated after code
stabilization. C04 data unchanged; C06/Gemini/private state not modified or replayed.
Synthetic evaluation truth is separate and never passed into assembly; selected
source IDs are not mislabeled as retained answers. Outputs TEST_ONLY with quality,
calibration and cost NOT_EVALUATED. Corpus is author-visible, not independently secret.

## 6. Limitations / acceptance recommendation

Recommend review of this repaired offline increment only. **C09 remains ACTIVE**.
No full-checkpoint approval while worker/disconnect containment and independently
approved quality evidence remain missing. No universal injection immunity, exact
provider-token safety, real-world superiority or enterprise-readiness claim.

## 7. Next implementation

Bounded worker isolation/disconnect cleanup, then separate scoring/provenance and
new independent evaluation cases. Owner approval required before any live requests.
Owner remains the sole acceptance authority; no further Kimi handoff required.
