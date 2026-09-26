# Delivery checkpoints

Status: PLANNED → ACTIVE → READY → ACCEPTED. READY requires recorded evidence; ACCEPTED requires owner review. BLOCKED must name the missing prerequisite. Owner acceptance is tracked independently from routine implementation progress. Full V1 and enterprise release acceptance remain pending.

| Checkpoint | Deliverable | Depends on | Status |
|---|---|---|---|
| C00 | Project brain, scope and architecture | — | READY |
| C01 | Package, contracts and token accounting | C00 | READY |
| C02 | Five independent context layers | C01 | READY |
| C03 | One-call assembly and offline inspector | C02 | READY |
| C04 | Frozen benchmark corpus and validity harness | C03 | READY |
| C05 | Groq adapter, replay cache and usage ledger | C03 | READY |
| C06 | Complete V1 benchmark, demo and reports | C04, C05 | READY |
| C07 | Durable runtime memory and index lifecycle | C03, C05; C06 live deferred by owner | READY |
| C08 | Authenticated self-hosted API and integrations | C07 | READY |
| C09 | Security and held-out quality qualification | C08 | ACTIVE |
| C10 | Operational readiness and recovery | C09 acceptance;offline preparation allowed D086 | ACTIVE |
| C11 | Measured cost and retrieval improvements | C10 acceptance;offline profiling allowed D086 | ACTIVE |
| C12 | Enterprise pilot acceptance and release | C09–C11,owner deployment/pilot choices | BLOCKED |

Effort is deliberately not presented as a delivery date before the first implementation and dependency checks. C04 and C05 are independent after C03; other ordering can be revised with evidence. Revisions must preserve PRD traceability.

## C00 — Project foundation

Build: preserved PRD, full requirements map, architecture, enterprise/evaluation proposals, compact persistent brain, indexed search, owner review package.

Acceptance: all 73 source sections and 27 V1 checklist entries mapped; every future checkpoint has a deliverable, verification and owner demonstration; source checksum matches; hot memory within its cap; local links valid; generated index current; status/context/search/check work without inference.

Owner demonstration: open OWNER_REVIEW and CHECKPOINTS; inspect STATE; search for a requirement without loading the whole source.

Evidence (2026-09-07): source equality and checksum verified; `python3 scripts/brain.py index` and `check` pass source preservation, all 73 section mappings, all 27 V1 mappings, 13 checkpoint definitions, local links and index freshness. `python3 -m unittest discover -s tests -v`: 8 tests pass on Python 3.11.10 and 3.14.6. `status`, bounded `context`, and bounded `search` executed successfully; status/search also verified from `/private/tmp`. Tests are in `tests/test_brain.py`. Owner acceptance pending. No runtime capability is claimed by these foundation checks.

## C01 — Core contracts and token accounting

Build: installable Python 3.12+ package; uv-managed, tested lockfile; central validated configuration; immutable messages/turns, source refs, keyed pins, blocks, carrier, structured errors; injected tokenizer and adapter-aware accounting.

Acceptance: clean environment setup prints `deps ok`; `o200k_harmony` exists; invalid/negative budgets rejected; required-block overflow fails before inference; Unicode, role framing, long questions, tool schemas and output reservation covered; no provider or benchmark imports in the core. Cross-platform paths derive from module locations.

Owner demonstration: valid minimal request and an impossible pin budget, showing counts and a readable error. Evidence: setup log, lockfile, contract tests and dependency decision record. No live API required.

Evidence (2026-09-07): [C01 report](C01_REPORT.md), `uv.lock`, `src/context_engine/`, `tests/test_core.py`. Setup prints `deps ok`; 55 tests pass on Python 3.12.13; lint, formatting, dependency checks and wheel/source builds pass. A separately installed wheel passes setup/demo from outside the repository. Token estimates remain explicitly unverified against Groq. Owner acceptance pending.

## C02 — Five independent layers

Build: deterministic head/tail CAP; non-evictable PIN; original chunk BM25 retrieval; shared WINDOW lookahead; frozen/reusable summary policy. Summary and retrieval allocations reserved before WINDOW selection.

Acceptance: all layers tested independently; source originals remain byte-identical; middle-of-tool facts retrievable; chunk overlap deduplicated; no retrieval over planned WINDOW IDs; Unicode-safe CAP with marker counted; keyed pin replacement; empty history/query and no-match behavior explicit; summary leakage rejected in benchmark policy.

Owner demonstration: oversized tool output loses its middle in WINDOW but its old fact is recovered from the original chunk. Evidence: layer tests and synthetic before/after context.

Evidence (2026-09-07): [short C02 report](C02_REPORT.md), [layer contracts](LAYERS.md), `tests/test_layers.py`. 89 tests pass; `demo-layers` recovers a capped middle fact with 637/900 estimated request tokens and no inference. Lock/lint/build verification passes. Owner acceptance pending.

## C03 — End-to-end assembly

Build: one `assemble_context` interface, complete API-ready messages and diagnostics; CLI configuration check and offline context/probe inspection; deterministic shrinking and final serialized-request validation.

Acceptance: exact PRD execution and assembly orders; question included exactly once; every output fits the configured estimated-input allowance or returns a structured error; required data never silently dropped; tool-call relationships valid; source IDs and selection reasons available; original/history input immutability tested. Randomized budgets and Unicode/tool fixtures exercise edge cases.

Owner demonstration: a long synthetic history into a 900-token allowance, with per-block counts, retrieved source and safe failure for impossible required context. Evidence: integration tests and saved synthetic inspector output; no invented model answer.

Evidence (2026-09-07): [short C03 report](C03_REPORT.md), [public API/CLI contracts](PIPELINE.md), `tests/test_pipeline.py`, `tests/test_inspection.py`, `output/c03-inspection.json`. Package 0.3.0; 149 tests pass, including 60 new checkpoint cases and generated Unicode/budget/tool examples. Synthetic inspection recovers turn t1 evidence at 637/900 estimated tokens with zero inference calls. Final shrink order, mandatory overflow, provenance, privacy defaults and no-overwrite exports verified. Owner acceptance pending; provider calibration remains C05/C06.

## C04 — Corpus and evaluation integrity

Build: 100-turn scenario, 31 planted facts, frozen summary, six variants, deterministic grading, five validity gates, run manifest and resumable probe IDs; owner-reviewed pre-registration.

Acceptance: all fixture invariants pass; intentional malformed data, answer leakage, partial output and config drift are detected; ground truth never enters engine input; `fact_present` measured independently from `answer_correct`; A0 oversized input gets non-fit status without provider spend. Alias boundaries and source attribution verified. Statistics use explicit denominators.

Owner demonstration: one valid probe and deliberately corrupted fixtures producing INVALID before inference. Evidence: fixture hashes, frozen protocol, grading/gate tests.

Evidence (2026-09-08): [short C04 report](C04_REPORT.md), [benchmark contracts](BENCHMARK.md), [owner-pending pre-registration](PREREGISTRATION.md), `tests/test_evaluation.py` and packaged evaluation resources. Package 0.4.0: 233 tests pass; all 31 primary probes fit a 900-token local allowance. Flagship Turn 82 evidence is retrieved at 804 estimated tokens; raw 16,608 is non-fit. Five intentional corruption cases are INVALID; actual generation remains NOT_RUN. Immutable resume example and metadata-only check are saved in `output/`. Lint/format/lock/build and a clean installed-wheel check pass. Implementation READY; owner review/target approval and live quality measurement remain pending.

## C05 — Inference and accounting

Build: Groq adapter, validated model/config options, controlled errors, timeouts/cancellation, bounded retry, SQLite replay cache and daily usage ledger, quota preflight/reservations/reconciliation, privacy-safe logs and UTF-8 console handling.

Acceptance: offline fake-provider tests cover missing key, timeout, 429, partial response, malformed usage, cache corruption and retries; request keys include full config and security scope; concurrent calls cannot overspend local reservations; replay incurs zero new provider spend; uncertainty is recorded for possibly processed timeout requests. Separate cached-input pricing and reasoning/output usage.

Owner demonstration: identical requests replay; changed question or generation config misses; exhausted quota prevents inference. Evidence: accounting/concurrency tests; one live smoke probe only once credentials and a spend cap are available. Live availability remains unverified until then.

Evidence (2026-09-08): [short C05 report](C05_REPORT.md), [provider contracts](PROVIDER.md), `tests/test_providers.py`, `tests/test_provider_commands.py` and `output/c05-provider-demo.json`. Package 0.5.0: 323 tests pass, including 90 C05 cases. Atomic shared-local quota reservations, unknown-usage holds/reconciliation, safe retries/cancellation, opt-in replay, malformed/corrupt response handling and explicit live-command gating verified offline. Two simulated calls, one zero-new-cost replay and quota-blocked generation change; zero real inference calls/spend. Lint/format/lock/build and clean installed-wheel checks pass. C04 artifacts preserved; new code freeze uses unchanged protocol/targets. Implementation READY; live smoke/calibration and owner acceptance pending.

## C06 — V1 release proof

Final evidence (2026-09-22,D072–D073):**744/744 dispositions**,613 successful live responses,124 non-fits,six preserved rejections and one missing-answer timeout;zero pending. Owner log resolves timeout usage through audited accounting-only amendment009,not answer substitution. Final26 calls allHTTP200. Snapshot249/report249 VALID,all five frozen gates PASS,primary quality PASS (29/31 correct,95.18% estimated input reduction,zero truncation).752 local tests pass;network-disabled reports byte-identical,both figures inspected. All718 baseline223 records unchanged,zero active/uncertain ledger holds,no runner. **READY for owner review with limitations**,not owner-accepted or enterprise/release-certified:12 historical provider-input overruns,S11 retention regression and seven failed responses remain visible. [Final C06 report](C06_REPORT.md) carries reconciled usage and limitations. Older progress below is historical.

Build: benchmark and model-swap CLI, scorecard, raw-count statistics, leaderboard, two figures and flagship live demo; reproducible result manifests and no-call report regeneration.

Acceptance: all 27 PRD V1 criteria have evidence; six variants and both models have recorded dispositions; five gates pass for accepted runs; meet frozen quality thresholds or report failure honestly; actual and estimated token usage/cost distinguished; quota-aware resume works; figures and leaderboard regenerate with network disabled. Any missing live model results keep C06 incomplete.

Offline implementation evidence (2026-09-08): [C06 progress report](C06_REPORT.md), [runner contracts](RUNNER.md), `tests/test_execution.py`, `output/c06-offline-run.json` and generated `output/c06-report/`. All 744 slots ran offline (620 synthetic UNKNOWN responses, 124 A0 non-fit); resume issued zero additional calls. Durable dispatch intent, shared-account and cumulative-run admission, receipt/request binding and reproducible reports implemented. No live answer/usage/calibration, target approval or spending authorization exists; C06 is not READY or accepted.

Verification: 354 tests pass; lint/format/lock/build and clean core/provider/report installs pass. Installed full-matrix report generation and identical-hash regeneration work with networking disabled. Five integrity gates pass with explicit TEST_ONLY status; model-quality acceptance remains NOT_EVALUATED. Both PNGs visually inspected. Observed 900/3,000 retention difference is recorded as S11, not silently tuned away.

Owner demonstration: Turn 82 `shard-19` recovered, context shown, real model answer graded, raw baseline non-fit shown. Evidence: versioned result JSON, manifests, reports, plots and demo instructions. Owner accepts V1 independently of later enterprise milestones.

Preparation update (2026-09-13): package 0.7.1 adds explicit free-tier zero-price accounting and private `--env-file` loading. 454 tests pass, including 48 new safeguards, plus clean installed offline checks. Owner saved a local key; target approval, confirmed free-account status/limits and live results remain pending. C06 stays BLOCKED; this is not live completion evidence. See updated [C06 progress report](C06_REPORT.md).

Approval update (2026-09-13, D047): owner now approves the targets and Free-plan/$0 live testing. Package 0.7.2 freezes approval without threshold changes; 454 tests pass. Key works against the read-only model endpoint and both models are listed. Account limits are still unknown; endpoint has no quota headers and no browser is connected. C06 remains BLOCKED on account configuration and has no live inference results. Do not ask for target/free-plan approval again.

Live update (2026-09-13, D048–D049): screenshots resolve organization quotas for both models: 30 RPM, 8,000 TPM, 1,000 RPD, 200,000 TPD. Private zero-price config and shared ledger established. First real A5/900/120b flagship answers `shard-19` correctly (804 estimated / 752 actual input, 42 output tokens). C06 is ACTIVE; full matrix and live report qualification remain incomplete. Earlier missing-limit/no-inference statements above are historical.

Post-C08 continuation (2026-09-13): archived 0.7.2 runner now records all six 900-token/120b variants, plus two 3,000-token responses. Snapshot021 has 157 live responses + 62 raw non-fits; 525 slots pending. Primary A5 numerical thresholds are met (31 fit / 29 retained / 29 correct / 95.18% median estimated reduction / zero truncations). Full-run integrity status remains INTERRUPTED with V4 pending, and quality acceptance NOT_EVALUATED; C06 is not READY. Reports and resume022 command are in the current [C06 report](C06_REPORT.md). No frozen algorithm/target changes or owner acceptance inferred.

Continuation (2026-09-14): snapshot042 adds 42 live responses, reaching 199 live + 62 non-fit / 744 planned. A1/3000/120b finished at 4/31 retained/correct; A2/3000 has 13 responses. All 219 earlier terminal records unchanged; no errors, truncations or uncertain attempts. C06 remains ACTIVE, with 483 slots pending. See current C06 report for resume043 and latest evidence; primary thresholds unchanged and no C09 start.

Continuation (2026-09-14, batches043–061): 37 more live responses; snapshot061 has 236 live + 62 non-fit, with 446 slots pending. A2/3000/120b completes at 0/31 retained/correct; A3 has 19 responses. All 261 prior terminal entries unchanged. Daily usage of 198,729 leaves 1,271 tokens, below the next 3,244 reservation; safely paused until the next local UTC day, no background runner. Audit also identifies 12 earlier A2/A3/900 provider-input overruns; S12 records calibration work without changing the frozen experiment. C06 remains ACTIVE/incomplete; current report provides resume062 and verification.

Continuation (2026-09-19, batches062–068): 12 more live responses complete A3/3000/120b at 0/31 retained/correct. Snapshot068 has 248 live +62 non-fit, 434 pending; all 298 prior terminal records unchanged. Today's usage31,082 tokens; stops at this group boundary with daily quota still available. Next is A4/3000/120b merchant through archived resume069. C06 remains ACTIVE/incomplete; Gemini comparison does not substitute for frozen Groq evidence. See [current progress report](C06_REPORT.md).

Completion continuation (2026-09-19, D059, batches069–100): 75 more live answers and31 non-fits bring snapshot100 to416/744 terminal (323 live,93 non-fit),328 pending. Every120b case is finished; A4/A5 at3000 each19/31 retained/correct. 20b A1/900 has13 responses. All310 prior terminal records unchanged. Foreground controller has19 new tests; full suite617 passes. Daily usage198,973 leaves1,027 below next1,050 reservation, so it stops safely. Report100 validates INTERRUPTED/quality NOT_EVALUATED and regenerates identically offline. C06 remains incomplete; current report/state provide the next quota-window resume.

Continuation (2026-09-20, batches101–131): 172 more live responses and 31 non-fits bring snapshot131 to 619/744 terminal (495 live, 124 non-fit), with 125 fitting calls pending. Both models' 900-token groups are complete; A4/A5 each score 29/31 correct. 20b A1/3000 has 30 responses and 3 correct. All 416 prior terminal entries are unchanged; no new input overruns, errors, truncation or uncertainty. Daily usage197,125 leaves2,875 below the next3,231 reservation, so the controller stopped safely. Report131 validates INTERRUPTED/quality NOT_EVALUATED. C06 remains ACTIVE; resume132 at A1/3000/20b archive after the September21 local quota window. See [current progress report](C06_REPORT.md).

Continuation (2026-09-20, D063, batches132–138): owner confirms original organization. Explicit external cache-aware admission amendment001 excludes only validated known cached input, with full usage/ceilings/frozen experiment unchanged and separate source/sidecar/event provenance. Adds16 successful answers and one confirmed provider rejection:636/744 recorded,511 live answers,124 non-fits,one error,108 unrun. All619 previous terminal entries unchanged. Controller stops for terminal-error review, not quota:20,124 local tokens remain. No active/uncertain requests or background runner. Full suite640 passes; report138 validates INTERRUPTED/NOT_EVALUATED and reproduces byte-identically offline. C06 remains ACTIVE; current report records failure/recovery hold and next untouched trace probe.

Reviewed continuation (2026-09-20,D064,batches139–144): exact baseline failure preserved,one untouched case per batch,metadata-only HTTP status observation. Five successful answers then a new confirmed HTTP400 bring642/744 recorded:516 answers,124 non-fits,two rejections,102 unrun. All636 earlier terminal entries unchanged. One separate,single-attempt reproduction returns HTTP200 using the same payload; root cause remains unknown and failed benchmark results are not replaced. Account allowance6,916 remains; stop is new-error review,not quota. Report144 validates INTERRUPTED/NOT_EVALUATED and reproduces identically offline;663 tests pass. C06 remains ACTIVE/incomplete,with next untouched policy probe held for further recovery review.

Reviewed continuation (2026-09-20,D065,batches145–146): both known rejected cases preserved under amendment003;two new HTTP200 answers bring644/744 recorded:518 answers,124 non-fits,two preserved rejections,100 unrun. All642 prior terminal entries unchanged;no new failures/overruns/uncertainty. Local quota stops at1,732 available below next3,245 reservation. No runner remains. Report146 validates INTERRUPTED/NOT_EVALUATED and reproduces byte-identically offline;673 tests pass. Next local windowSeptember21 00:00UTC/05:30IST,resume147 at20b/A2/3000 endpoint through recovery003 if admissible. C06 remains ACTIVE/incomplete;no owner acceptance or C09 start.

Continuation (2026-09-21,D066,through171):21 successful answers+one new HTTP400,666/744 terminal (539 answers,124 non-fits,three rejections),78 unrun. Fixed external same-payload/different-case admission bug;154/155 zero-call exports and partial156 preserved. All prior records/core unchanged;686 tests pass. Report171 offline-identical;figures inspected. New-error stop,not quota;local145,685 tokens available,no active/uncertain calls. D067/amendment005 reviews three exact failures for untouched-case continuation only;new failures still halt. C06 remains ACTIVE/incomplete;no C09 start or owner acceptance.

Reviewed continuation (2026-09-21,D067,batches172–177):five additional successful answers then timeout-fact HTTP400,672/744 terminal (544 answers,124 non-fits,four rejections),72 unrun. All666 baseline171 entries preserved. Full suite697 passes;report177 validates INTERRUPTED/NOT_EVALUATED and regenerates identically offline. No new input overruns/uncertainty. Local132,769 tokens remain;stop is fourth-error review,not quota. No runner remains;next region_backup/20b/A3/3000 held for review. C06 remains ACTIVE/incomplete;no C09 start or owner acceptance.

Continuation and safe stop (2026-09-22,D068–D071,batches178–223):43 additional successful answers,two confirmed HTTP400 rejections and one real timeout with unknown usage. Snapshot223 records718/744 dispositions:587 answers,124 non-fits,six confirmed rejections,one uncertain timeout;26 untouched cases remain. All672 baseline177 records preserved;A4/3000/20b completes19/31 correct. Report223 validates INTERRUPTED/NOT_EVALUATED and regenerates byte-identically with sockets disabled;both figures inspected. Full suite730 passes. C06 is BLOCKED on external processing/usage evidence for the A5 database timeout,not quota. No runner remains;new UTC day does not release uncertainty. See [current report](C06_REPORT.md) for exact request metadata and recovery requirements. No failed-case retry,owner acceptance or C09 start.

## C07 — Persistent product memory

Build: transactional history/pin/summary store, chunk-index persistence, revisioned snapshots, idempotent ingestion, optimistic concurrency, retention/export/delete and derived-data invalidation; migration path from local storage.

Acceptance: restart preserves state; repeated ingestion does not duplicate; competing pin updates conflict correctly; deleted/expired source cannot appear in any derived index/summary/cache; interrupted indexing resumes or rebuilds deterministically; backups do not silently revive deleted data. Tenant scope present in every store boundary.

Owner demonstration: ingest, restart, retrieve, revise pin, delete original, then verify no stale retrieval/replay. Evidence: persistence, migration, invalidation and concurrency tests. Development brain remains separate from runtime data.

Evidence (2026-09-08): [C07 report](C07_REPORT.md), [memory contracts](MEMORY.md), `tests/test_memory.py`, and [synthetic lifecycle demo](../output/c07-memory-demo.json). 406 tests pass, including 52 new cases. Verified restart, idempotency, competing updates, source expiry/deletion, interrupted chunk coverage, revision-bound replay, schema-version refusal and deletion-safe restore. Wheel/source builds and network-disabled core-only installed checks pass. Migration path is documented; PostgreSQL migration, authenticated tenancy and production recovery remain later gates. READY for review, not owner-accepted. D037 allows C08 offline next; C06 remains BLOCKED and must return before C09 quality qualification.

## C08 — Enterprise service and SDK integration

Build: versioned API around the core; external identity integration, roles and service credentials; scoped histories/pins/context/export/delete; quotas, audit events; SDK examples for caller-managed inference and Groq integration. Deploy locally with synthetic data first.

Acceptance: unauthenticated requests denied; tenant identity derived from credentials and checked against requested resource; API schemas, error taxonomy, pagination and idempotency documented; two independent integrations reuse the same core; raw prompts omitted from default logs. Hosted SaaS must be separately chosen before building its platform features.

Owner demonstration: two identities see separate sessions; SDK and API produce equivalent context for the same authorized snapshot. Evidence: contract/integration tests and local deployment guide.

Evidence (2026-09-13): package 0.8.0, [C08 report](C08_REPORT.md), [service contracts](SERVICE.md), `tests/test_service.py` and [loopback demonstration](../output/c08-service-demo.json). 526 tests pass, including 72 new C08 cases for missing/expired/forged identity, server-owned tenant/role bindings, cross-scope reads/writes/export/delete, idempotency/CAS, pagination, tool-pair/source-pin lifecycle, quota concurrency/restart, redacted errors/audit, assembly races and API/SDK equivalence. Real local HTTP demo and clean installed packages verified. Optional service dependencies do not enter core imports; no real provider calls, SaaS deployment or IdP account setup.

Limits: pinned-key IdP integration is tested with signed synthetic access tokens, not a provisioned production identity provider. Local service quotas/audit are not distributed coordination or tamper-proof logs; public TLS, key refresh, hard CPU/cancellation/load and production recovery remain later qualification. READY for review, not accepted or enterprise-ready.

C06 reminder (D050–D051): owner explicitly permitted C08 offline after partial live C06 results. Archived 0.7.2 environment validates snapshot004 and a byte-identical zero-call resume; shared provider ledger unchanged. Next continuation returns to C06 using its archived-environment batch005 command before C09 quality work. No background inference or approval reset.

## C09 — Security and real-world evaluation

D088:[16-call policy diagnostic](C09_POLICY_LIVE_REPORT.md) complete,target FAIL:
5/8each arm. Candidate not adopted;all source evidence retained,one regression.
Budget exhausted;broader C09 still ACTIVE,no acceptance or new calls inferred.

D087:[policy003 preparation](C09_POLICY_QUALIFICATION_REPORT.md) complete offline;
29targeted tests PASS,32conditions/16unique payloads. Narrow16-call diagnostic
amendment proposed,not authorized;broader quality/acceptance gates unchanged.

D085:[offline conflict analysis](C09_CONFLICT_ANALYSIS_REPORT.md) rules out missing
context for the smoke failure;opt-in policy candidate added,32development
assemblies retain prior evidence. No model-quality claim or new API calls.

D084:[structured smoke](C09_STRUCTURED_SMOKE_REPORT.md) complete:2valid JSON,
1correct,1conflict-handling failure.35focused tests PASS. C09 remains ACTIVE;
no further calls authorized,next offline analysis. Old qualification unchanged.

D083:[strict structured-answer integration](C09_STRUCTURED_ANSWER_REPORT.md)
implemented offline as opt-in repository example.117 checks PASS,zero API calls;
includes response-schema budget accounting. Live acceptance/quality still pending.

D082:[two-call response diagnosis](C09_RESPONSE_DIAGNOSTIC_REPORT.md) complete.
Raw provider empty content reproduced once;other call valid. Parser exonerated
for this path,internal provider/model cause unresolved. C09 ACTIVE;no more API calls.

D081 offline continuation:[empty-answer diagnosis](C09_EMPTY_ANSWER_REPORT.md)
adds an opt-in caller boundary,105 targeted tests PASS,no new calls or engine changes.
Protocol stop-success and application validity are now explicitly separated;
upstream blank-answer cause/quality qualification remain OPEN.

Latest D080(2026-09-23):[qualification live002](C09_QUALIFICATION_LIVE_REPORT.md)
completes32/32 requests. PRIMARY7/8 at each budget,CONTROL5/8 and6/8;strict target
FAIL. Five empty answers retained;zero provider errors/truncations/input-cap
overruns/uncertain usage. C09 ACTIVE,next offline diagnosis,no calls authorized.

Offline preparation(2026-09-23,D079):[qualification002-r1](C09_QUALIFICATION_REPORT.md)
freezes32 fresh author-visible paired slots and strict answer integration on0.9.2.
Recovery literal retention7/7 versus default6/7 at both budgets;model quality remains
NOT_EVALUATED. Owner review/new live budget/independent qualification still pending.
No additional API calls,default-policy adoption,C10 start or owner acceptance.

Reminder gate: the deferred C06 matrix is now complete (snapshot249). Review its final evidence and S11/S12/error limitations before C09;do not treat primary fixture PASS as held-out quality or owner release acceptance. D037 did not waive evidence requirements.

Build: threat model, boundary tests, abuse controls and held-out corpus covering stale/contradictory facts, paraphrases, multilingual text, hostile tool output, no-answer cases and very large histories.

Acceptance: cross-tenant retrieval/cache/export/delete all denied; malicious retrieved instructions cannot grant permissions; resource bounds and cancellation enforced; secrets/PII logging review complete; held-out protocol frozen before tuning; security issues triaged and critical/high issues resolved or explicitly reviewed before release.

Owner demonstration: red-team fixtures and quality breakdown on unseen scenarios. Evidence: threat model, negative tests, data-handling review and held-out scorecard. No claim of universal injection prevention.

Progress (2026-09-22,D075): [C09 report](C09_REPORT.md), [threat model](C09_THREAT_MODEL.md), [separate protocol](C09_EVALUATION_PROTOCOL.md). Repaired partial implementation,857 tests pass including105 C09 cases,0.9.0 build/lock/freeze verified,64 synthetic offline slots prepared with zero network/provider calls and identical replay. ACTIVE: hard CPU/disconnect containment, response/retention scoring and independent live quality/calibration remain unresolved. No owner acceptance or automatic deferral to C10. Former Kimi handoff superseded.

Continuation (2026-09-23,D076): package0.9.1 closes local assembly timeout/disconnect containment with bounded disposable workers; adds frozen literal-retention and TEST_ONLY response scoring.891 tests PASS,including139 C09 cases;offline/installed builds and HTTP demo PASS.003 preparation/scorer reports reproduce with sockets disabled. Earlier D075 local gaps are addressed;C09 stays ACTIVE pending owner-approved independent live-quality/calibration evidence and exact receipt-provenance execution protocol. No API calls or owner acceptance inferred. See [current report](C09_REPORT.md).

Latest C09 evidence(2026-09-23,D077): [live001](C09_LIVE_REPORT.md) completed32/32
responses without API errors,uncertainty,forbidden answers or input-cap overruns.
Strict quality2/8 per condition FAIL;913 local tests pass. C09 stays ACTIVE for
answer-contract/identifier and retention work plus independent qualification.
No automatic C10 start or further live calls;the32-call budget is consumed.

Offline continuation(2026-09-23,D078):[repair001](C09_REPAIR_REPORT.md) adds0.9.2
default-off WINDOW missing-chunk recovery and optional exact-answer JSON validation.
970 tests PASS,build/installed service demo PASS,no new API calls. Live001 remains
unchanged/reproducible through its archived0.9.1 environment. C09 stays ACTIVE for
fresh quality qualification;default-policy adoption and owner acceptance pending.

## C10 — Operations and recovery

D086 local baseline:[C10 report](C10_REPORT.md),[operations runbook](OPERATIONS.md).
11synthetic recovery/profile checks PASS,build/installed memory demo PASS,manual
cross-platform CI prepared. D089/D090 [platform report](C10_PLATFORM_REPORT.md):
owner screenshots show remote Ubuntu/macOS PASS;Windows preflight PASS,17POSIX
collection errors. D090 approves exact17historical-module Windows exclusion with
NOT TESTED reporting;full suite remains required on Linux/macOS. New Windows run pending.
Manual-first owner execution preference. Other acceptance gates unchanged.

D093 [admission repair](C10_ADMISSION_REPAIR.md):0.9.3 service counter/schema2,
explicit quota-preserving migration,baseline0.9.2 preserved;new Windows check pending.

Build: cross-platform CI, release build, migrations, backup/restore, rollback, metrics, alerts, load profile and operational runbooks; dependency/license review and artifact provenance.

Acceptance: required tests pass on macOS/Linux/Windows; sustained load on declared hardware meets approved targets; crash/retry and index-rebuild drills pass; timed restore meets agreed RPO/RTO; deletion tombstones reapplied on restore; rollback of failed deployment proven. No production SLO claim from a single local benchmark.

Owner demonstration: restore into an isolated environment, verify history/context integrity, simulate provider outage and recover. Evidence: CI results, load report, restore timing, runbooks, SBOM and rollback transcript.

## C11 — Cost-driven evolution

D086 offline profile:[C11 report](C11_REPORT.md). Existing index reuse measured;
no new optimization or production-cost/quality claim. Acceptance remains pending.

Reminder gate: measured model-cost optimization requires the deferred C06 live baseline; do not substitute synthetic prices/UNKNOWN answers. Return to the owner if C06 is still incomplete.

Build: evaluate relevant SUGGESTIONS experiments; profile assembly and storage; optimize token-count memoization, versioned index updates, summary reuse and measured cache benefits. Hybrid retrieval or bypass is optional based on evidence.

Acceptance: compare to locked V1 and held-out baselines with paired workload runs; no accepted quality/security regression; include CPU/storage/summary costs; record accepted/rejected ideas and why. Completion does not require adopting every enhancement.

Owner demonstration: before/after quality, latency and total cost per useful answer with provenance. Evidence: versioned experiment manifests, results and decision entries.

## C12 — Enterprise release

D086:[release blockers and procedure](C12_REPORT.md). BLOCKED on failed quality,
unqualified operations/cost,pilot inputs and explicit owner acceptance. Local
preparation does not authorize deployment or waive earlier gates.

Reminder gate: C06 live qualification must be resolved before release acceptance. D037 changes development order only; it does not waive release evidence.

Build: bounded real-workload pilot, integration and support documentation, release notes, operating ownership, compatibility policy and rollback plan.

Acceptance: all previous required gates accepted or explicit owner scope amendments recorded; V1 requirement evidence complete; pilot targets met over an agreed observation period; data handling, hosting/spend choices and support responsibilities settled; no unresolved release-critical defects. Release claims match tested capabilities. External deployment requires the chosen deployment scope and authorization.

Owner demonstration: complete customer-style workflow from ingestion to context, answer, audit, deletion and recovery, plus quality/cost report. Evidence: pilot report and explicit owner release acceptance. This is the enterprise completion gate.
