# C10 — local operational baseline, ACTIVE

2026-09-28:[temp-directory compatibility repair](C10_STORAGE_ACL_REPORT.md),0.9.6.
Windows75b78ec stops at credential70PASS/1FAIL on storage startup;later steps did
not run. Pytest child-directory ACL setup corrected;offline demos/probes create
new private storage children,without rewriting existing permissions.532local
PASS,47native Windows tests pending;actual0.9.5 preserved. Owner NEW diagnostic.

2026-09-27,D095:[Windows SQLite ACL repair](C10_STORAGE_ACL_REPORT.md),version0.9.5.
Memory/deletion/runtime/control databases and sidecars now require private native
ACLs and safe directory inheritance. Existing permissions are never rewritten;
actual0.9.4 preserved.523focused local PASS,44native tests unverified on macOS;
offline build PASS. Owner NEW Windows diagnostic required;C10 remains ACTIVE.

2026-09-27,Windows77faaaa:[platform report](C10_PLATFORM_REPORT.md):credential
probe71PASS,storage14PASS,main628PASS/1FAIL296.05s,no timeout. New failure is a
Windows-invalid`?` in a backup test filename. Portable URI-sensitive fixture now
runs everywhere;original POSIX case retained.11local backup/restore checks PASS;
owner NEW Windows run pending. SQLite ACL gap/full qualification remain open.

2026-09-27:[diagnostic update](C10_PLATFORM_REPORT.md):owner Windows ACL/storage
probes PASS;main suite times out after58% without an assertion failure in the
supplied excerpt. Next test's million-character name replaced with a short ID,
unchanged oversized input/assertions.26local tests PASS0.11s;Windows confirmation
pending. No broader qualification or SQLite ACL resolution claimed.

2026-09-26,D094:[credential ACL repair](C10_CREDENTIALS_REPORT.md) advances to0.9.4.
Native Windows credential/config checks implemented;0.9.3 wheel/freeze preserved.
186focused local tests PASS;10native Windows checks await owner-run CI.
Separate SQLite ACL enforcement and full platform qualification remain open.

2026-09-26,D093:[admission repair](C10_ADMISSION_REPAIR.md) advances to0.9.3.
Confirmed same-timestamp primary-key collisions repaired with schema2 row IDs;
existing control DBs require explicit transactional migration. Historical0.9.2
wheel/freeze preserved;old preparation reproduces offline. Windows confirmation
pending;older measurements below apply to their recorded runtime only.

2026-09-24,D086. Owner requested completing the whole project quickly;independent
offline operations work advances without waiving C09 quality or release gates.

Delivered:bounded synthetic operations drill,manual macOS/Linux/Windows workflow,
artifact/dependency metadata inventory,and [operations runbook](OPERATIONS.md).
No production data,credentials,API calls,remote CI execution or deployment.

Evidence:

-Full pre-increment suite:1,087 PASS,2dependency deprecation warnings,248.68s.
-10new operations/inventory tests PASS0.30s;scoped lint passes.
-[Local drill](../output/c10-local-001/operations.json):11checks PASS,100turns,
  20warm samples,concurrency1,Darwin25.6 arm64/10logical CPUs,input cap900.
  Warm assembly p50=27.31ms,p95=27.86ms;warmup125.64ms. Backup0.94ms;
  restore/reindex/assembly49.20ms. Timed after the full test suite finished.
-Deleted turn and marker do not return;surviving history retained,epoch rotated,
  replay invalidated,99surviving turns reindexed. Second isolated restore matches.
-Offline wheel/sdist built to private c10-build-001. Installed wheel in a fresh
  core-only environment and ran the nine-check memory demo from `/tmp`:PASS.
  Installed source hash remains298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc.
-[Inventory](../output/c10-local-001/inventory.json) records2artifact hashes and
  45installed dependency metadata entries. Wheel75entries/sdist1118entries inspected:
  no private directories,venv or secret `.env` paths. This is not a content-secret
  scanner,standards-compliant SBOM,signed provenance or approved license/CVE audit.

D089 update:[platform report](C10_PLATFORM_REPORT.md). Mac/Linux preflight4groups
PASS;Linux full suite1,117PASS/1private-evidence-fixtureFAIL. Portable test repair
passes25local checks including original private audit;Linux rerun still pending.
Owner now prefers manual setup/CI/long-test execution;no new inference.

D090 owner screenshots show remote Ubuntu/macOS jobs PASS,Windows preflight PASS
but17historical-runner collection errors. Approved explicit Windows-only boundary
excludes those17modules with NOT TESTED reporting;Linux/macOS retain the full suite.
7scope tests PASS;1128local tests collect. New Windows run pending;see platform report.

Not complete:remote three-platform results,Windows POSIX-runner portability,
sustained service load,approved hardware/targets,offsite recovery/current deletion
authority,real deployment rollback,migration to future schemas,monitoring/alerts,
dependency/license/vulnerability review and owner acceptance. No SLO or RPO/RTO claim.
