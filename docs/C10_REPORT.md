# C10 — local operational baseline, ACTIVE

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
