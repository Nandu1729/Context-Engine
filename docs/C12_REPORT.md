# C12 — release preparation, BLOCKED on qualification and owner decisions

2026-10-02,D103:[whole-project completion audit](PROJECT_COMPLETION_STATUS.md).
Current deliverable is a local development SDK/service candidate,not a completed
enterprise production release. Current package0.9.6;historical0.9.2 evidence preserved.
No deployment or publication. Built artifacts are local and their hashes inventoried.

## Release blockers

| Gate | Actual state | Required before acceptance |
|---|---|---|
| C09 quality | Qualification PRIMARY14/16;policy003 diagnostic5/8each arm,target FAIL | Fresh reviewed evidence passing the unchanged target,or an explicit scope amendment |
| C10 operations |0.9.6 three-platform CI PASS on3e3e0e4:Ubuntu/macOS each1195PASS/48SKIP;Windows976PASS. Platform/operations/brain/build steps PASS. See[evidence](C10_PLATFORM_REPORT.md) | Declared load,operating targets,monitoring,real restore/rollback qualification;CI-platform gate complete |
| C11 cost | Index reuse profiled;70condition overlap-union prototype tested,not adopted | Paired representative workload with accepted quality and total cost accounting |
| Supply chain | Local metadata/artifact inventory only | Vulnerability/license review,release license choice,SBOM/provenance policy |
| Pilot | Synthetic incident-response selected by delegated choice;32assembly/10lifecycle preflight checks PASS. See[report](C10_INCIDENT_PILOT_REPORT.md). No real pilot observed | Independent domain reviewer,source/update rules,authorized data,environment,targets,operating owner,measured pilot |
| Owner acceptance | C00–C08 READY,not accepted;later gates open | Explicit checkpoint/release acceptance |

## Prepared release procedure

Current next action:[pilot intake](OWNER_REVIEW.md#pilot-intake-after-cross-platform-ci)
and [quality/authority review](C09_QUALITY_REVIEW_REPORT.md). Platform CI is complete;
synthetic incident-response is selected;real source-authority rules and an
independent reviewer are still needed.

1. Keep the current source and frozen research artifacts intact. Record candidate
   artifact digests and dependencies;do not relabel failed evidence as passing.
2. Follow [operations](OPERATIONS.md) and [service](SERVICE.md) in an isolated
   synthetic local environment. Identity tests do not provision a real IdP.
3. Obtain deployment location/data-handling policy,representative workload,quality
   target,load/SLO/RPO/RTO,operating and incident owner,and pilot observation period.
   Configure TLS/at-rest encryption/secrets/audit/backup facilities for that environment.
4. Review results and unresolved defects;prepare upgrade/rollback instructions
   against actual deployed versions. Pilot success must be observed,not predicted.
5. Owner explicitly authorizes release and external deployment scope. Until then,
   no public service,publishing,customer data or additional model spending.

API remains `/v1`;package0.9.6 does not imply an enterprise SLA or a stable1.0 promise.
Breaking contract/storage changes need a new version,migration tests and compatibility
review. Source output history is preserved;authorized deletion takes precedence over
retaining data in restored indexes,cache or summaries.

Fastest responsible path:finish independent local preparation now,then resolve
the concrete external gates above. More repeated smoke calls cannot substitute
for deployment evidence or owner decisions.
