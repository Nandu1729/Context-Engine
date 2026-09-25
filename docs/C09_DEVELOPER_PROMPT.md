# Historical C09 assignment — role split superseded by D075

**Not an external-developer assignment.** The owner now assigns implementation and
review to this assistant alone. The original scope prompt below is preserved;
actual progress and open gates are in C09_REPORT.md and brain/STATE.md.

Use after [developer handoff](DEVELOPER_HANDOFF_PROMPT.md).
This is an implementation brief,not approval of new numerical quality targets or API spending.

---

Implement **C09:security and real-world evaluation foundations** in the existing
Context Engine project. Follow AGENTS and the developer handoff. Do not start C10–C12.
The owner will return your report/code to the architect for independent review.

## First actions

Read current STATE,CHECKPOINTS C09,C06_REPORT,ARCHITECTURE,SERVICE,MEMORY,PROVIDER,
ENTERPRISE,EVALUATION and the relevant PRD/requirement sections. Read S11/S12 in
`brain/SUGGESTIONS.md`;inspect `src/context_engine/service/`,memory/provider integration
boundaries and their tests. Resolve stale C06 language against D073;the matrix is finished.
Verify the current test baseline before changes. Write `docs/C09_PLAN.md` with bounded
work items,acceptance checks,risks,freeze/version strategy and open owner choices.

Proceed with offline implementation. Synthetic incident-response scenarios are a
working fixture choice,not owner approval of a production/customer workload. Propose
any workload-dependent targets for review while continuing independent security work.

## A. Threat model and security tests

Create `docs/C09_THREAT_MODEL.md`:assets,trust boundaries,actors,entry points,data flow,
abuse cases,controls,explicit assumptions and residual risks. Cover HTTP versus trusted
SDK access,tenant/session/role authority,originals/pins/summaries/chunks/replay,exports,
deletion/restore,provider accounting,secrets and telemetry. Host-admin compromise and
external exported copies are not magically solved by application controls.

Implement/fix C09-scoped gaps and add regressions covering:

- Cross-tenant and cross-session denial for read/retrieval/assembly,pins,cache/replay,
  export,delete and audit. Include same resource IDs in different tenants,warm caches,
  stale revisions and concurrent access. Show denied requests do not touch protected
  data or make provider calls;authorization must happen before lookup.
- Role/credential boundaries:missing,expired,forged and malformed credentials,duplicate
  headers,wrong issuer/audience/algorithm,session allowlists and privilege escalation.
  Use locally generated test keys and tokens;no real IdP/key/credential exposure.
- Hostile historical/tool/retrieved/summary content cannot become trusted instructions,
  authorize storage actions,rewrite authoritative pins or execute tools. Include forged
  provenance and adversarial Unicode/delimiters. Delimiter assertions alone do not prove
  injection resistance;test deterministic authority boundaries and label LLM behavior untested.
- Deletion/expiry invalidates chunks,summaries,pins and scoped replay where applicable;
  rebuilding/restoring cannot revive deleted facts when using current deletion authority.
- Secrets/PII review across exceptions,validation errors,audit,logs and diagnostics.
  Use synthetic canaries to assert forbidden content is absent. Distinguish explicitly
  authorized content-returning APIs from accidental log/error leakage.

Keep server-controlled identity/tenant policy outside model judgment. No new inference,
public deployment,unscoped administrative endpoints or automatic tool execution.

## B. Resource bounds and cancellation

Test oversize/streamed/slow bodies,deep or malformed JSON,large Unicode/tool payloads,
turn/chunk/retrieval bounds,quota races,concurrent requests and cancellation under
declared local limits. Record environment,load and measured outcomes.

C08 synchronous assembly lacks a hard preemptive CPU deadline. Investigate this gap:
an async timeout around blocking work does not prove the work stopped. Implement and
test an appropriately bounded cancellation/concurrency mechanism within C09,or report
the precise unresolved gate and submit the necessary architectural proposal. Verify
that canceled work cannot continue unbounded,leak permits/transactions or partially
commit data without an auditable recovery path. Preserve provider uncertainty semantics.

Do not claim production SLOs,distributed fairness or generic DDoS prevention from local
tests. Large process/storage changes need an explicit design/tradeoff record;do not
silently introduce infrastructure outside this checkpoint.

## C. New,versioned evaluation protocol and fixtures

Build a held-out evaluation path separate from the frozen C06 data/identity/runtime.
Create `docs/C09_EVALUATION_PROTOCOL.md` and a hash-bound manifest before evaluation
or retrieval tuning. Specify:

- Scenario categories,independent scenario IDs,train/development versus sealed
  evaluation split,random seeds/provenance,distribution and known leakage risks.
- Stale/contradictory facts with deterministic temporal authority,paraphrases,multilingual
  text,hostile tool output,no-answer questions,large histories and deletion/expiry cases.
- Ground-truth source/effective-time lineage and acceptable answers/abstentions separated
  from engine inputs. No answer leakage through questions,summaries,pins or metadata.
- Exact variants,budgets,scoring rules,denominators,invalid/error handling,confidence
  limitations and proposed pass/fail thresholds. Owner-pending targets stay pending;
  do not import C06's29/31 outcome as a universal threshold or adjust criteria after results.
- Independent retention,answer correctness,abstention,hallucination where measurable,
  security denial,estimated token fit,actual provider usage when available,and local
  latency/resources. Do not present correlated probes as independent general-world evidence.

Use evaluator-only ground truth. Freeze test fixtures and protocol before running/tuning;
if test results influence implementation,record that exposure and obtain a fresh
evaluation split before claiming held-out qualification. Synthetic fixtures are not
real customer data and do not establish unseen production quality.

Implement deterministic preparation,validation,offline scoring/reporting and reproducible
artifacts. Separate TEST_ONLY/mock correctness from real LLM answer quality. Reproduce
offline reports with networking blocked;unknown measurements remain unknown. Use a new
C09 output directory without overwriting previous artifacts.

**Do not make new live calls yet.** First produce a bounded live-evaluation proposal:
model/provider,request count,max input/output budget,shared-account accounting,free-tier
or explicit paid ceiling,approved targets,stop conditions and privacy handling. Get owner
approval before sending even free-tier requests. Do not create an isolated fresh ledger
that forgets prior use of the same provider account. Credentials come from authorized
private configuration only,never prompts/reports. Approval may remain pending while
offline/security work completes;full C09 quality qualification must then remain pending.

## D. Carry C06 findings forward without rewriting them

- The124 A0 non-fits are expected baseline budget rejections,not defects to suppress.
- Preserve all seven errors. Improve bounded,sanitized diagnostics and safe failure
  tests where justified;do not guess why a400 occurred or retry an ambiguous timeout
  as if it definitely consumed nothing. Live reproduction needs separate declared scope.
- S11 retention regression and S12 provider-token calibration need separate reproducible
  experiments. Add diagnostic/offline evidence where feasible;propose architecture or
  calibration changes with tradeoffs. Do not tune C06 or hide a regression behind a
  larger limit. A new multiplier is not proof of a universal token bound.
- Preserve the old0.7.2 archives and0.8.0 baseline. Version actual new code/fixtures
  through the existing workflow;do not overwrite historical source identities or use
  new runtime results as if they were old-run evidence.

## Required deliverables and exit criteria

Deliver C09_PLAN,C09_THREAT_MODEL,C09_EVALUATION_PROTOCOL,implementation/regression tests,
versioned fixtures/manifests,offline evaluation artifacts and `docs/C09_REPORT.md`.
Also save `docs/C09_ARCHITECT_REVIEW.md` using the developer handoff's review-package
sections. Include exact changed files,commands,actual results,findings/severity,
criterion-to-evidence table,residual risks,live approval status and next actions.

Run relevant focused tests,full regression suite,applicable Ruff checks,build/installed
import checks when package changes,and brain index/check. Preserve existing tests;
explain any baseline failures. Test isolation must prevent real provider calls and
mutation of original C06/account data. Never claim green without observed commands.

Every critical/high security finding needs a demonstrated fix and regression or an
explicit unresolved gate for owner/architect review. You cannot self-accept those risks.
Classify each criterion PASS/FAIL/BLOCKED/NOT_RUN with evidence. An offline-only stage
may be ready for review while C09 as a whole remains incomplete—do not mark full C09
READY if required cancellation/security/live-quality evidence is missing.

Update checkpoint/requirements/brain with actual status. Keep memory bounded;the
current JOURNAL is near its150-line archival threshold. Preserve old entries on rollover.
Stop after the C09 handoff. End with a concise report and the exact artifacts the owner
should give the architect. Do not start C10 or make broad enterprise-ready claims.
