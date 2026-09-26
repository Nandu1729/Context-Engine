# D093 — request admission collision repair (0.9.3)

## Cause and change

Windows run36230402597 on4b03d54 recorded INSERT1555 in all three concurrency
tests. Local fixed-clock reproduction confirmed two distinct requests for one
tenant collide on schema1's PRIMARY KEY(tenant,at). Clock timestamps are not unique.

0.9.3 service-control schema2 uses an integer row ID. Real timestamps are retained
unchanged and are nonunique;tenant/time has a lookup index. Every accepted request
is counted in the same transaction as its audit intent. Quota limits,expiry logic,
SQLite locking/timeouts and HTTP correctness assertions remain unchanged. No
INSERT OR IGNORE,no quota resets,no retries and no new platform exclusions.

## Existing service-control databases

Fresh databases use schema2 automatically. Schema1 is rejected until explicitly
migrated. Memory/deletion databases and provider quota ledgers are NOT migrated.

Operator procedure for an existing service deployment (not needed for CI's fresh
temporary databases):

1. Stop every service process using this control database. Back up the control
   database using SQLite's backup API and retain the matching old application.
2. Confirm its existing `rpm` and `max_sessions` values;do not change policy as part
   of this migration.
3. With0.9.3,call `ControlStore(path,rpm=existing_rpm,max_sessions=existing_slots,
   migrate_v1=True)` once. Use the actual control path,not a memory or provider DB.
4. Restart only0.9.3 processes without the migration flag. Verify the service and
   quota behavior. Do not mix old/new processes or use old code against schema2.

Migration copies all admissions (including expired entries) and preserves audit,
session slots and policy. Table replacement/version change occur in one transaction;
errors roll back. Policy mismatch refuses migration. Existing schema2 reopens without
recopying data. Rollback to0.9.2 requires the pre-migration backup and quiescent
service;blindly restoring it after new traffic would discard accounting/audit data
and is not authorized. No real database has been migrated by this development work.

## Frozen research boundary

Preserved the actual0.9.2 wheel and freeze in `archives/c10-admission-093/` before
editing. Historical scripts,experiment manifests,output records and private runtime
environments remain unchanged. New built-in development freeze identifies0.9.3;
it is not a regrading of old experiments or a new live qualification.

Five harness unit-test modules now use temporary TEST_ONLY manifest copies bound
to the actual candidate runtime. All resource/runtime guards still execute;no
identity-function mocking or historical files rewritten. Negative drift tests start
from valid candidate manifests so runtime mismatch cannot mask their intended check.
New transition tests require old manifests to reject0.9.3,then validate them and
exactly reproduce the old preparation using the real archived0.9.2 wheel offline.

Source hash0.9.3: `b0bfb7283087edfb8d1e7c4d63f82687197202ce4682af14c397626dcbccdf7b`.
Package/lock advanced without changing third-party dependency versions.

## Verification / next action

Initial targeted repair run:14PASS0.46s (ten admission/migration cases and four
concurrency/observer checks). Covers fixed timestamps,exact quota boundaries,
multiple store instances,tenant separation,duplicate-request rollback,explicit
migration,history preservation,session slots,policy mismatch and failure rollback.
Final focused verification:134PASS/2dependency warnings4.05s covering service,
bounds,admission/migration,runtime transition,brain and platform scope. Two evaluator
freeze/drift checks PASS1.45s;scoped lint/diff checks PASS. Offline0.9.3 wheel build
PASS. Separate53candidate qualification/harness tests also passed;intermediate
fixture corrections and exact command results are retained in the project journal.

Windows confirmation (owner-supplied run36238746737 on1a444f8):all14 storage/race
checks PASS5.48s. The subsequent portable diagnostic stopped at81PASS/1FAIL14.00s:
the evidence-policy retention test had missed the candidate-manifest transition.
It now uses the same disposable TEST_ONLY fixture,requires the original manifest
to reject new code,and verifies its bytes remain unchanged. Retention/budget
assertions are unchanged. No product code,freeze or Windows exclusion changed.

Follow-up local command:`.venv/bin/python -m pytest -q tests/test_c09_evidence_policy.py
tests/test_runtime_transition.py tests/test_c09_policy_qualification.py --tb=short`:
32PASS2.02s;scoped ruff/diff PASS. Owner:commit/push this test correction and run a
NEW **Windows diagnostic**. Full Windows qualification remains pending. No full
local-suite rerun,API calls,remote dispatch,deployment or checkpoint acceptance.
