# Evidence journal

Earlier evidence: [C00–C08](archive/JOURNAL_2026-09-07_to_C08.md) and
[C06 completion / original handoff](archive/JOURNAL_C06_COMPLETION_2026-09-22.md).

## 2026-09-22 — C09 takeover, repair and offline evaluation

- Owner ends Kimi handoff and requests this assistant review/fix/continue C09 alone. D075 supersedes D074's role split. No subagents, live inference, credential reads or C06 changes.
- Incoming partial0.9.0 work: lock mismatch prevents locked run; direct suite27failed/754passed/54errors (mainly stale sourcefreeze), focused C09 suite8failed/75passed. Reviewed all changed implementation files, new tests and prior C06 documentation without discarding unrelated work. C08 archived wheel/freeze independently verified against0.8.0 hash.
- Corrected invalid cross-scope test payloads/DELETE calls, skipped credential assertions, identical-canary isolation weakness, quota test target/count, broad exception assertions, and CAP-versus-original Unicode expectation. Added warm-index distinct-tenant canaries, no-memory-on-denial and captured-log checks.
- Completed cooperative cancellation checks inside CAP/chunk loops, at assembly stages/return and index precommit. Added malformed-token, mid-batch/precommit rollback and single-large-message regressions. Hard CPU/disconnect cancellation remains OPEN, not silently deferred/accepted.
- Added threat model, heldout-v1 protocol/hash manifest,16 independent synthetic case IDs/eight categories/two splits,64 offline preparation slots and separate evaluator-only truth. No response importer/dispatcher/scorer; TEST_ONLY, answer quality/calibration NOT_EVALUATED.16 harness tests pass; protocol saved before measurements. No algorithm tuning against these cases.
- Version/lock deliberately aligned0.9.0; source freeze9395ab7ce378b0532fae9b016baeb25df7e68b72950db7c18277688fd962b234. C04 fixture hashes unchanged, historical0.8.0/C06 preserved. Full-suite/build verification running; final counts will be recorded below.
- Final verification:857 tests pass twice (99.29s/98.41s),two existing warnings;105 C09 tests included. New report links initially exposed missing artifact copies in isolated brain-test fixtures; added explicit copies without weakening link checks,full suite passes again. Ruff/format/lock/diff checks pass;offline wheel/sdist build and isolated wheel/resources/freeze/core-import checks pass. Historical0.7.2/0.8.0 wheel+freeze hashes reverified unchanged.
-64/64 synthetic preparation slots PREPARED;socket-disabled second run JSON/README byte-identical in separate c09-offline-001-replay. Real loopback HTTP demo PASS for auth/tenant/export/API-SDK/audit,zero external/inference calls,no persistent server. C09_REPORT and engineering review saved with open hard-worker/disconnect and scoring/live-quality gates. No C09 completion/owner acceptance inferred.
- README/AGENTS/SERVICE stale C06-deferral routing corrected to D073/D075;historical handoff prompts explicitly superseded. Brain45-document index/integrity PASS,hotmemory783/900;PRD hash/73sections/27V1items/13checkpoints unchanged. Next implement C09 worker containment,not C10 or C06 rerun.

## 2026-09-23 — C09 local worker containment and scoring verified

- D076 continuation implements0.9.1 process-backed `/context`: authorization before launch,2default/max8 slots,no queue,parent deadline/disconnect/task cancellation/shutdown kill/reap. Middleware forwards disconnect after buffered body. Bounded IPC,stripped credential environment,no shell;worker owns UTC snapshot/index/assembly/currentness checks. SDK remains cooperative.
-19 process tests include true non-cooperative termination,PID reaping,capacity recovery,late startup/shutdown races,ASGI disconnect/audit,credential isolation and SQLite rollback after kill inside transaction. Final review adds drain/discard after kill to prevent full stdout pipe delaying wait();continuous flood regression passes. Metadata quota concurrency and revision-race tests updated to correct new execution boundary without dropping assertions.
- Separate frozen scoring-v1 adds actual rendered-source literal retention,normalized exact synthetic answers,abstention/forbidden checks,full denominators and hash-bound TEST_ONLY import;rejects duplicates,wrong runtime/request hashes and live labels.31 held-out/scorer tests pass. No algorithm tuning;original fixture/manifest bytes preserved.
-003 offline preparation64/64,retention36true/20false/8not-applicable;scorer64missing/0correct,quality/calibration NOT_EVALUATED. Socket-disabled preparation/scoring replay byte-identical. Previous001/002 artifacts and matching wheels/freezes preserved;all four archives independently verified. C06/Gemini/keys/ledgers untouched,zero API calls.
- Final891 tests pass in107.71s,two existing warnings;139 C09 tests. Offline wheel/sdist/lock/lint/format/diff checks PASS. Final installed wheel sourcefreeze e65cb926df31f42d0f06a0c72c67f86860633ba56d00dbb075cf33b9f2ccfadf validates;real loopback HTTP demo PASS with subprocess assembly,no persistent server. Updated current report and preserved001 report separately.
- Offline C09 engineering delivered;full C09 ACTIVE pending exact owner-approved live model/corpus/targets/quota and frozen provider-receipt path. No implicit32-call approval,paid spending,deployment or owner acceptance. SDK/OS/global-limit/SLO limitations explicit. Final brain46-document index/integrity PASS,hotmemory767/900;8 focused brain tests PASS in0.53s after documentation changes.

## 2026-09-23 — C09 bounded live001

- D077 accepts the exact32-call Groq20b/256-output/no-retry/free-tier proposal. Added external runner and separately frozen C09_LIVE_PROTOCOL,leaving0.9.1 core/old artifacts unchanged.22 new offline tests cover single dispatch,resume,crash/uncertainty,errors/truncation,hash drift,receipt tampering,original-ledger preservation,quota pacing and full denominators.913 tests PASS in152.80s,2 existing warnings;lint/format/lock/diff checks PASS.
- Final003 wheel/sourcefreeze archived and independently matched. Before live dispatch,recorded hashes of878 protected archive/C06/Gemini files. Existing original ledger623 attempts/1,050,769tokens,zero active holds;today0 local usage. Current explicit .env only,no key output. Runner hashd7839652e66d6c4c52dc3da398538fd2d2bf6b48c3cde6e1a9adf2a35dca57d9;execution5e6d7cc10f8865d4916b85322a3f7c0bcc82c91e79c2a7c92fba4d1304fa974a. Foreground run in progress;read status before any resume,never reset claims or init a new quota pool.
- Live001 finished32/32 responses,zero provider errors/truncation/unknown usage/retries. Strict8/32 correct(2/8 each condition),quality target FAIL;post-hoc diagnosis12 extra-wording,3 Unicode identifier-hyphen changes,9 absent-evidence UNKNOWNs,without changing scores. Forbidden0,input-cap overruns0;3 inputs exceed estimates,max ratio1.708333.27,402input+1,151output=28,553tokens,configured$0. Original shared ledger now655attempts/1,079,322tokens,no holds;all623 prior attempt hashes match. No more calls authorized in this run.
- Full report/receipts saved separately;socket-disabled report replay byte-identical.878 protected archive/C06/Gemini files hash-identical before/after. Updated C09 report/protocol routing,threat/review/checkpoint disposition,S13 proposal and hot memory. C09 ACTIVE,not accepted;next offline answer-contract/identifier and S11 retention work,then newly frozen independent evaluation with a new call budget. No runner remains. Final48-document brain checks PASS,804/900 hot words;8 brain tests PASS in0.63s after report links,linter/diff PASS. Frozen core/runner/protocol unchanged after dispatch.

## 2026-09-23 — C09 offline repair001,0.9.2

- D078 continuation preserves0.9.1 before editing:installed archived wheel and exact pins into output/private/c09-frozen-env;runner/protocol audit copies saved byte-identically. New0.9.2 adds default-off recover_capped_window SDK policy,source-message chunk dedup and finalizer validation;PRD default old-history exclusion unchanged. Original history,scope,required blocks,reserves and deletion authority preserved.
- Optional AnswerContract generates instructions/schema and validates exact JSON values for text,ASCII identifiers and canonical integers;no normalization/prose extraction,ground truth,provider calls or automatic retries. It validates conformance,not truth;actual model compliance unmeasured.57 new development regressions include source forgery,index drift,duplicate chunks,tight budgets,memory/deletion parity and malformed/Unicode output cases.
- Focused repairs/layers/pipeline118 PASS in0.69s;full970 PASS in153.94s,2 existing warnings,including218 C09 tests. Sourcefreeze298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc;version/lock0.9.2,dependencies unchanged. Ruff/format/lock/diff/offline wheel+sdist PASS. Clean installed wheel /tmp/context-c09-092-wheel.JQzUPT validates version/freeze/core-import isolation/parser;process-backed loopback HTTP demo PASS,zero external/inference calls,no persistent server.
- After edits,frozen0.9.1 live001 report replays byte-identically with sockets disabled;32 responses/8 strict matches unchanged,no new account usage. Saved C09_REPAIR_REPORT and ANSWER_CONTRACT,updated architectural opt-in contracts and current routing. C09 ACTIVE,next fresh reviewed qualification/answer integration plan and separately approved live budget;no C10 or default adoption. Final brain51 indexed documents,837/900 hot words,8 brain tests PASS in0.53s;PRD73sections/27V1items/13checkpoints/hash intact.

## 2026-09-23 — D079 qualification candidate preparation

Latest continuation is recorded below under D080;D079 authorization-pending text is historical.

Final targeted qualification/brain rerun:37 PASS in10.21s;29 new qualification checks.
Brain53 indexed docs,880/900 hot words;PRD hash/mappings/checkpoints unchanged.

- Added fresh synthetic qualification002-r1 protocol/fixtures/manifest and external offline preparation/strict TEST_ONLY scorer. Answer instructions included before budget accounting;no truth injection,normalization or live-label acceptance. Engine0.9.2 unchanged;no API calls or credential/ledger access.
- Initial002 preflight:7 passed/19 setup errors from empty optional block decoding;preserved original script/manifest and corrected evaluator under r1,with explicit empty-block regression. Cases/targets/engine unchanged.32 requests prepare;primary retention7/7 vs control6/7 at each budget. Sockets-disabled reproduction identical;provider answer quality NOT_EVALUATED.
- Saved C09_QUALIFICATION_REPORT/protocol/preparation and updated current routing. Owner review/new bounded32-call approval needed before a separately frozen live dispatcher;C09 ACTIVE,C10 planned.
- Full run997 passed,two documentation-fixture failures,2 existing warnings,in162.90s;both failures caused by archive README absent from isolated test copy,not engine behavior. Fixed fixture,brain8/8 passes;final combined qualification/brain recheck follows. Installed0.9.2 wheel offline preparation identical;old live001 script/protocol hashes unchanged. Owner explicitly requests faster,lower-usage completion:avoid redundant full reruns,unnecessary features or expansive context reads;retain risk-proportionate targeted checks.

## 2026-09-23 — D080 bounded qualification completed

- Owner approves32 new original-account free-tier Groq20b calls. Separate byte-bound wrapper reuses old safety functions without editing them;frozen002-r1 cases/targets/0.9.2 unchanged.24 fake-transport checks:22passed initially;stale fixture identifier fixed and source-drift guard triggered during offline editing;failed-test rerun2PASS17.46s,drift subset6PASS0.88s before inference. Local quota171,447tokens,zero holds;no quota-probe call.
- Run exit0,32successful receipts. PRIMARY7/8 at900 and3000,CONTROL5/8 and6/8;strict target FAIL.27JSON-conforming,25correct total. Five empty success answers (47–63 output tokens,not256 exhaustion);two CONTROL missing-middle abstentions. Four paired improvements/one regression;no direct comparison to old corpus.0errors/truncations/forbidden/input-overruns/uncertainty;4estimate-under-counts,max1.127660.
-22,838input+1,636output=24,474tokens/$0configured. Account687attempts/1,103,796tokens;all655baseline row hashes unchanged,zero holds. Socket-disabled report replay byte-identical SHA813e06da87d5b066f05eaa80a219521b04f35d89e399c55a6de9c1c9fe85f746. Initial replay command patched sockets before SSL import and failed locally;corrected verification succeeds without network. Old live001/C06/Gemini artifacts not edited.
- Saved C09_QUALIFICATION_LIVE_REPORT and updated routing. D080 exhausted;next offline empty-answer diagnosis,no new calls or regrading. C09 ACTIVE,not owner-accepted;C10 planned. No background runner remains.

## 2026-09-23 — D081 fast offline empty-answer diagnosis

- Verified parser copies content verbatim;null stop would fail,reasoning is not extracted. Client maps stop to protocol success and settles usage;five saved empty answers remain invalid application answers. Upstream cause unresolved,not proven budget exhaustion.
- Added examples/validated_answer.py opt-in caller guard and20new tests,including all five saved failures and one-attempt accounting preservation.105targeted tests PASS0.43s;ruff PASS. No package or frozen script/fixture changes,no APIs,credentials,real-ledger writes,retries or full-suite rerun. Saved C09_EMPTY_ANSWER_REPORT and integration guide;C09 ACTIVE,quality unchanged. Future provider diagnostic needs a bounded approval.

## 2026-09-24 — D082 two diagnostic calls completed

- Nine tests PASS5.11s,then2original-account20b/256calls,no retries. Initial001 zero-call preflight report assumed paired cases;preserved manifest/script,corrected report under002 identity with old-claim guard. No call budget reset. Observed only allowlisted response shape/hash metadata,no raw body/reasoning/headers/key logs.
- long/PRIMARY900 raw content is present empty string,stop;conflict/CONTROL900 gives20character UNKNOWN JSON,stop. Native parser preserves both. Provider final-content emptiness confirmed once;internal cause unresolved,not output-limit exhaustion (47/65output tokens). Old25/32 andPRIMARY14/16 scores unchanged.
-1,342tokens/$0configured;account689attempts/1,105,138tokens,all687prior rows unchanged,no holds. Socket-disabled replay identical SHAae4ef86a391d2c3107d121533c0e8740f0330ee12e9b9c931629851e532d5468. Report saved;D082 exhausted. Next offline response-format mitigation review,no new calls or matrix rerun;C09 ACTIVE.

## 2026-09-24 — D083 structured-answer mitigation offline

- Checked official Groq structured-output documentation;strict schema supported for current20b model,tools/streaming unsupported. Implemented repository example with closed required answer-string shape,full-schema serializer,matched client counter and one-attempt policy;keep local exact-answer guard. No SDK/core/frozen artifact changes.
-117 targeted tests PASS0.41s (12new),ruff PASS;tests cover actual fake payload/accounting,overflow-before-dispatch,tool/config rejection,immutable schemas and distinct cache/request keys. No provider calls or real-ledger/key access. Live mitigation remains NOT_EVALUATED;proposal2new smoke calls needs owner approval. C09 ACTIVE.

## 2026-09-24 — D084 approved structured smoke completed

-35focused tests PASS9.57s before freezing;new wrapper reuses verified frozen safety machinery with matched schema counting/client keys.2/2 original-account calls complete,no retries;2valid JSON but1correct. Long case snap-782 correct;conflict OT-417 wrong (expected UNKNOWN),despite retained evidence. No old-score replacement or full-suite claim.
-1,356tokens/$0configured;691account attempts/1,106,494tokens,all689prior rows preserved,zero holds. Socket-disabled report replay identical. Saved C09_STRUCTURED_SMOKE_REPORT;D084 exhausted,C09 ACTIVE,next offline contradiction analysis,no further calls.

## 2026-09-24 — D085 offline contradiction analysis

- Reconstructed frozen smoke request:both complete conflicting records and abstention instruction present. Wrong but syntactically valid answer;model-internal cause unknown. Added generic opt-in evidence policy clarifying unresolved conflicts vs explicit updates,without fixture hints or defaults/core changes.
-52focused tests PASS1.22s,including32development assemblies with no retention regression (PRIMARY7/7,CONTROL6/7 per budget). No live semantic claim,API calls or ledger writes. Saved C09_CONFLICT_ANALYSIS_REPORT;next fresh qualification controls/owner review,C09 ACTIVE.

## 2026-09-24 — D086 whole-project offline acceleration

-Full existing suite1087PASS/2dependency deprecation warnings248.68s;10new operations/inventory testsPASS0.30s. Local100turn/20sample drill11checksPASS:backup0.94ms,restore/reindex49.20ms,warm assemblyp95=27.86ms,all deletions preserved. Existing index reuse100→0processed,not a new optimization or production cost claim.
-Offline wheel/sdist built and hashed,core-only installed memory demo from/tmp9checksPASS,source0.9.2unchanged. Artifact path inspection found no private/.env/venv paths.45dependency metadata inventory is not license/CVE approval. Manual macOS/Linux/Windows CI prepared,not remotely executed;frozen POSIX-runner Windows risk visible.
-Saved C10/C11/C12 reports and operations runbook;updated owner review. C09quality remains failed,C10/C11acceptance pending,C12blocked on qualification/pilot decisions. No API calls,deployment,customer data,spending or acceptance inferred.

## 2026-09-24 — D087 policy003 offline preparation

-8fresh author-visible cases with separate truth;matched strict schema/recovery across baseline/candidate.29targeted testsPASS1.28s. All32conditions retain all records,max463estimated tokens;socket-disabled replay identical. Script/resources/runtime frozen after checks;earlier experiments unchanged.
-Only16unique payloads because budgets do not change these short contexts. Proposed16-call900-budget diagnostic amendment needs owner approval;do not duplicate receipts or claim32independent samples/two-budget quality. No calls/credentials/ledger access. C09 ACTIVE;report saved,broader quality/pilot/release gates unchanged.

## 2026-09-25 — D088 sixteen-call policy diagnostic complete

-Owner approved bounded16-call amendment by continuation. New isolated runner tests5PASS10.07s before freeze.16/16requests succeed,BASELINE5/8,CANDIDATE5/8;one improvement (missing evidence),one regression (hostile-tool wrong abstention). Both fail reversed/duplicate conflicts. Candidate not adopted;broader C09 OPEN,old scores unchanged.
-5,878input+1,078output=6,956tokens/$0configured. All691baseline rows preserved,account707attempts/1,113,450tokens,zero holds.15input underestimates,maxratio1.0876494,no input-cap overruns,truncation or provider errors. Socket-disabled report replay identical;completed resume with rejecting client sends no calls,ledger unchanged. D088 exhausted;stop prompt-only experiments,next independent review/offline C10 work.

## 2026-09-25 — D089 platform checks and manual-first handoff

- New platform preflight7testsPASS2.89s;Mac/Linux4real probe groups PASS. CI uses python-m pytest and LF checkout attributes. Core0.9.2 unchanged. Local Docker2CPU/2GiB read-only sanitized copy,no keys/private evidence/inference;public setup downloads only.
- First Linux collection failure retained;module invocation fixes examples import. Second run1117PASS/1FAIL/2warnings316.09s,private screenshot absent by design. Synthetic unit evidence now checks plan/image/missing tampering;original audit remains opt-in. Original audit1PASS1.28s;repaired recovery009 suite with private audit25PASS11.13s locally. Linux snapshot predates repair;no green Linux claim.
- Saved C10_PLATFORM_REPORT and raw reports/XML. Owner requests manual setup/CI/long tests to conserve Codex usage;persisted in AGENTS/STATE/DECISIONS. No third container/full run. C10 ACTIVE,C09 quality/C12 gates unchanged;next manual rerun and report review.

## 2026-09-25 — owner-run suite memory-cap repair

- Owner supplied macOS full-suite result:1119passed,1failed,1private-audit skip,2warnings267.26s. Brain stale-index test appends3words to898-word memory,exceeding900. Shortened INDEX prose without removing routes or changing the cap/test;kept headroom. No full-suite rerun or inference.
- Verification:brain check PASS851/900words;all8brain tests PASS0.73s. Full suite not rerun;owner evidence plus targeted repair verification only.

## 2026-09-26 — D090 explicit Windows test boundary

- Owner screenshots of run36219698403 show Ubuntu/macOS PASS,Windows17import errors after preflight PASS. Inspected frozen fcntl dependency;owner approved transparent platform split. Exact17-module collect_ignore only on Windows,all names printed NOT TESTED;Linux/macOS unchanged. No frozen scripts/core/credentials touched.
- 7new scope regressions PASS0.28s,lint PASS;1128tests collect locally0.46s. Tiny nested pytest runs verify import exclusion/reporting vs complete non-Windows collection;not Windows runtime validation. CI labels/docs updated. Next owner commit/push and NEW manual run;no full rerun or external mutation.

## 2026-09-26 — D091 bounded Windows diagnostic preparation

- Owner's934aa52 CI run passes Ubuntu/macOS;Windows now executes tests but displays failures/errors and times out. ZIP contains no Windows log;raw link BlobNotFound. Failure/hang cause unknown. Do not infer success from100% progress or merely extend timeout.
- Owner approves dedicated manual Windows-only first-failure workflow:verbose names,tee output,unbuffered,7minute test/10minute job caps. Same17exclusions;no code/frozen changes,new dependencies,inference or automatic CI dispatch. Next owner push/new diagnostic run.
- Validation:YAML parses,manual trigger/Windows-only runner confirmed;8brain tests PASS0.79s,brain check862/900words. No Windows execution claim.

## 2026-09-26 — D092 first Windows failure identified

- Read actual Windows ZIP98100003759:862collected,58PASS/1FAIL16.07s on417c611;concurrent write test sees503 alongside200/409. Original full-run delayed exit not explained. Local3race tests PASS0.40s;no evidence to justify a guessed core fix.
- Added safe test-only SQL stage/numeric error observation and allowlisted HTTP error codes,unchanged correctness assertions. Real two-connection lock regression proves SQLITE_BUSY still raises.4checksPASS0.41s,lintPASS. Refined manual Windows workflow probes these first;no new exclusions,core/frozen changes or inference. Await owner push/new run for actual Windows exception evidence.
