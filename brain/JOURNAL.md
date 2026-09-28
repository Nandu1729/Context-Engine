# Evidence journal

Earlier evidence: [C00–C08](archive/JOURNAL_2026-09-07_to_C08.md) and
[C06 completion / original handoff](archive/JOURNAL_C06_COMPLETION_2026-09-22.md).

[C09 takeover through policy preparation](archive/JOURNAL_C09_2026-09-22_to_24.md)
preserves the archived entries verbatim.

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

## 2026-09-26 — confirmed admission timestamp collision

- ZIP98114467083 on4b03d54:3race failures/1PASS4.39s,INSERT1555 with service_unavailable. Local fixed-clock two-distinct-request reproduction yields identical SQLITE_CONSTRAINT_PRIMARYKEY,one audit instead of two. Root cause:ControlStore PRIMARY KEY(tenant,at) mistakes timestamp for unique identity;not observed lock contention.
- No new tests/production changes or migrations. Recommend versioned service schema repair with explicit history-preserving migration and fixed-clock/quota regressions;frozen0.9.2 benchmarks must remain separately reproducible. Await owner direction for this schema/runtime change;no further diagnostic rerun needed for this defect.

## 2026-09-26 — D093 versioned admission repair

- Owner approves best versioned repair. Preserved actual0.9.2wheel/freeze,then advanced0.9.3 and control schema2 with integer IDs/nonunique timestamps. Explicit v1 migration only;atomic history-preserving copy,unchanged quota policy,rollback on failure. No existing owner DB accessed/migrated.
- 14repair/race regressions PASS0.46s. Five harness modules use disposable candidate manifests with real identity,not weakened guards or rewritten experiments. Transitional fixture mistakes fixed;55qualification/harness tests PASS in85.04s run (one separate baseline subprocess failed then repaired cache/socket setup). Corrected historical-wheel test PASS0.78s,network denied,old preparation exactly reproduced;new runtime rejects old manifests.
- Saved C10_ADMISSION_REPAIR and updated Windows diagnostic to test fixed-clock/migration regressions first. Core sourceb0bfb7283087edfb8d1e7c4d63f82687197202ce4682af14c397626dcbccdf7b;dependencies unchanged. No full suite,live calls,commit/push or CI dispatch. Windows confirmation/other failures pending.
- Final `.venv/bin/python -m pytest -q tests/test_control_admissions.py tests/test_runtime_transition.py tests/test_service.py tests/test_c09_bounds.py tests/test_brain.py tests/test_platform_scope.py --tb=short`:134PASS/2warnings4.05s. Two targeted evaluation freeze/drift checks PASS1.45s;ruff/diff PASS. `uv build --wheel --offline --no-sources --out-dir output/private/c10-admission-build-093` PASS;no sdist/full-suite rebuild.

## 2026-09-26 — Windows admission confirmed; omitted candidate fixture repaired

- Owner-supplied run36238746737 log binds1a444f8:14repair/race tests PASS5.48s;portable diagnostic stops at81PASS/1FAIL14.00s. Evidence-policy retention test still loaded historical0.9.2 manifest on0.9.3;not another admission failure.
- Reused disposable candidate_harness in that test;first assert original rejects new runtime,then execute unchanged retention/budget assertions and verify original manifest bytes unchanged. No production/frozen changes or additional skips.
- `.venv/bin/python -m pytest -q tests/test_c09_evidence_policy.py tests/test_runtime_transition.py tests/test_c09_policy_qualification.py --tb=short`:32PASS2.02s;scoped ruff/diff PASS. Full Windows qualification still pending;owner commit/push and NEW diagnostic. No live calls or remote dispatch.

## 2026-09-26 — Windows multilingual decoding reproduced

- Owner6e36ff6 log:14repair PASS5.19s;portable134PASS/1FAIL48.42s. Only multilingual rows drift569→576tokens;explicit CP1252 decode reproduces exact32c047e9 hash vs UTF-8 baseline4f8a732a. CI jobs set PYTHONUTF8=1;sanitized archived-wheel child uses/asserts -X utf8. No frozen/product changes or weaker assertions/skips. Focused qualification-node/runtime/platform/evidence-policy31PASS2.55s;ruff/diff PASS. Next owner commit/push/NEW Windows diagnostic;full platform qualification pending,no inference/dispatch.

## 2026-09-26 — D094 Windows credential ACL enforcement

- Owner42148a6 log:14admission PASS4.83s,UTF-8 regression PASS,portable501PASS/1FAIL270.02s. Permission test assumes chmod enforces privacy;Windows loader had no ACL check. Owner selects best real-world enforcement rather than exclusions. Preserved actual0.9.3 wheel/freeze before version0.9.4.
- Added lazy pinned Windows-only pywin32 binding,local fixed-disk/no-reparse handle open,owner/DACL allowlist and bounded same-handle read;fail-closed redacted failures,cleanup,no operator ACL rewrites. Test fixtures now set real Windows ACLs. Credential/config callers covered;SQLite ACLs remain separate known gap,not silently waived.
- Focused186PASS/10native-Windows untested/2warnings6.03s;additional30qualification checks PASS1.73s. Old0.9.2 full plan and0.9.3 wheel/freeze preserved and tested. Offline wheel build/metadata check PASS. CI now probes ACL tests first;owner push/NEW Windows diagnostic pending,no inference/remote dispatch. Archived pre-D088 journal entries verbatim under linked C09 archive at149-line threshold.

## 2026-09-27 — Windows verbose diagnostic log-volume repair

- Owner screenshot run36289927733:ACL/storage probes PASS,10minute job timeout. Pasted916-item output ends58% after Gemini response`{}`;no assertion failure/final summary. Next case's collected node ID is1,000,081characters. Four mocked cases pass quietly0.09s;verbose output is leading suspect,not proven Windows hang diagnosis.
- Added short descriptive IDs only;1,000,001-byte input/assertions remain.26module tests PASS0.11s with exact verbose flags;ruff/format PASS. No production/frozen changes,timeout increases,skips,inference or remote dispatch. Owner commit/push/NEW diagnostic;SQLite ACL/full qualification remain open. See C10_PLATFORM_REPORT.

## 2026-09-27 — Windows backup filename fixture

- ZIP98310168056,checkout77faaaa5d11370533508faf96e7ec99aa223fa70:credential71PASS2.66s,storage14PASS4.05s,main628PASS/1FAIL296.05s. Gemini oversized case PASS;no timeout. First failure at os.open on Windows-invalid`backup ?#.sqlite`,before copy/restore.
- Added portable`backup %#.sqlite` test case on all platforms;original question-mark case retained on POSIX,all assertions unchanged.11focused backup/restore PASS0.20s,ruff/format PASS. No production/frozen changes,new exclusions,inference or CI dispatch. Owner commit/push/NEW Windows diagnostic;SQLite ACL/full qualification remain open.

## 2026-09-27 — D095 Windows SQLite ACL enforcement

- ZIP98315475586/98353896744 repeat77f2de7 public-SQLite failure:636PASS,341.10s/291.71s,no timeout. Owner explicitly approves best real enforcement. Preserved actual0.9.4 wheel/freeze before0.9.5;older archives and frozen experiments untouched.
- Shared native owner/DACL checks,private new-object security,inheritable immediate directory validation,existing journal/WAL/SHM/super-journal checks,per-transaction revalidation and Windows temp_store=MEMORY. Memory/deletion/backup/runtime/control paths covered;existing ACLs never rewritten. Trusted ancestors/user/admins remain a limit,not a sandbox or race-proof VFS. Synthetic Windows fixtures use real ACLs;existing rejection assertions retained,no extra historical exclusions.
- Final scoped523PASS/44native-Windows untested/2warnings13.37s;ruff/diff/build PASS. Prior wheels validate;0.9.2 still reproduces original plan. Dedicated SQLite ACL probe added before full Windows diagnostic. Owner commit/push/NEW diagnostic remains required;no native-Windows/full qualification claim,operator DB changes,inference or dispatch. See C10_STORAGE_ACL_REPORT.

## 2026-09-28 — Windows temporary-directory compatibility

- ZIP98359821827,75b78ec:credential70PASS/1FAIL2.74s at ControlStore initialization;later probes/main suite not run. CPython3.12.13 mode0700 supplies protected OWNER RIGHTS ACL,so pytest children do not inherit the configured base ACL. Native failure substage redacted;new CI confirmation required.
- Provision every newly created pytest directory,not only base;restore wrapper at teardown and propagate setup failures. Demos/operational probes now let storage create private child directories below tempfile roots. Production ACL policy unchanged,no operator ACL rewrites. Preserve actual0.9.5 wheel/freeze and version demo changes0.9.6;historical evidence untouched.
- 532focused local PASS/47native-Windows untested/2warnings13.53s. Includes portable fixture regressions,prior-wheel hashes/freezes,original0.9.2 replay and demos/security/recovery/workers. Eight brain tests PASS0.71s;ruff/diff/build/isolated-wheel checks PASS;brain index/check895/900words. No additional exclusions,inference or remote dispatch. Next:owner commit/push/NEW Windows diagnostic;full qualification remains open.

## 2026-09-28 — Native Windows ACL probes pass; diagnostic timeout

- ZIP98501161699,c6b82fc02bc183983e424fa43975398648fce661:credential71PASS2.74s,concurrency14PASS5.39s,SQLite ACL62PASS4.49s. Main976collected/849PASSED lines,no FAILED;explicit7minute step timeout at86%,with a pass less than1second before interruption. Later pytest stash KeyError is interrupted teardown,not an application assertion. Remaining tests are not passes.
- Diagnostic suite limit15minutes/job25 with25slowest-test reporting,1second threshold. Probes unchanged2minutes each;manual dispatch,fail-fast,security assertions and exact17POSIX exclusions retained. No runtime/freeze/dependency changes,remote dispatch or inference. Owner commit/push/NEW diagnostic;then full manual qualification if passing.
- Workflow YAML/budget assertions PASS;18brain/platform-scope tests PASS1.04s with duration flags;brain index/check895/900words and diff checks PASS. No full local rerun or native-Windows qualification claim.

## 2026-09-28 — Owner-requested consolidated review and full offline verification

- Reviewed0.9.2→0.9.6 admission/migration,credential/storage ACLs,temp directories,connection policy,fixtures,freeze preservation and CI. Full macOS suite1195PASS/48SKIP/2warnings269.81s,no fail-fast. Skips:47Windows-native and one explicit private-screenshot audit;native checks separately pass in owner c6b82fc probes. No new product defect identified;runtime/freeze unchanged.
- Changed-code ruff,lock,YAML/budget checks PASS. Offline sdist/wheel build PASS;isolated wheel memory/provider/service demos PASS. Four platform probes and11operational checks PASS,zero inference. Historical experiments/scripts/output unchanged. Evidence in C10_PLATFORM_REPORT;private synthetic review artifacts retained.
- Windows workflow renamed complete portable verification,removes -x,retains15minute suite/25minute job and slow-test report. No extra exclusions,weaker assertions,retries or security-policy changes. Owner commit/push/NEW Windows run,then manual full matrix remains required;no remote dispatch,release acceptance or deployment.

## 2026-09-28 — Complete Windows portable verification PASS

Next-step handoff: inspected the existing manual qualification workflow for all
three platforms. Recorded exact UI steps/evidence requirements in C10_PLATFORM_REPORT
and cleared stale current Windows-pending wording. No runtime/workflow changes,
remote dispatch or repeated long local tests;quality/pilot/acceptance gates remain.

- Owner screenshot run36382286882/#12 Success7m57s;ZIP98509138631 checkout7a8ecb50141164c1863c6379a03de24fe08bd171. Main976PASS/2warnings394.22s;credential71PASS2.91s,concurrency14PASS5.52s,SQLite62PASS4.84s. Probe counts overlap main suite,not extra unique passes.
- Windows portability repair verified complete on this run;exact17POSIX modules remain visibly NOT TESTED. No further product changes/repeated diagnostic needed. Updated evidence/current state;broader manual qualification and owner operational/quality/release gates remain separate. No remote dispatch,inference or deployment.
