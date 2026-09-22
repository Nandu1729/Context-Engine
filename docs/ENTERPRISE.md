# Enterprise scope and release evidence

Status: proposed delivery scope beyond PRD V1. Controls below are engineering acceptance work, not claims of certification or legal compliance.

## Release tiers

1. V1 SDK / evaluated research release (C01–C06): all 27 PRD acceptance criteria demonstrated on synthetic data.
2. Enterprise pilot (C07–C10): durable memory, authenticated service, isolation, lifecycle controls, held-out testing, restore and rollback evidence.
3. Production enterprise release (C12): owner-approved workload, operating targets, runbooks and pilot results. Hosted SaaS requires a separate explicit product decision.

## Controls required before enterprise pilot

| Area | Implementation requirement | Acceptance evidence |
|---|---|---|
| Identity | Integrate an external OIDC identity provider; scoped service credentials; admin/operator/reader roles. | Expired, missing, forged and unauthorized identities denied. |
| Tenant boundaries | Tenant/session scope enforced before history, index, pins, summary, cache, exports and deletion access. | Negative tests across each access path, concurrent requests and warm caches. |
| Data lifecycle | Configurable retention, access-controlled export/delete, lineage-aware invalidation, backup expiry/deletion replay. | Deleted fact cannot reappear after index rebuild, replay or restore. |
| Encryption/secrets | TLS for service/storage connections; protected at-rest storage and key/credential rotation using deployment facilities. | Deployment configuration review and exercised rotation; no secret content in logs. |
| Audit | Actor, action, scope, request ID, policy/revision and outcome; restricted audit access and tamper detection appropriate to deployment. | Reconstruct an administrative change without exposing conversation bodies. |
| Prompt injection | Data/instruction separation, source trust labels, external tool authorization, malicious-history cases. | Hostile evidence cannot grant access, invoke privileged tools or modify authoritative pins. |
| Resource isolation | Byte/turn/chunk limits, timeouts, cancellation, per-tenant quotas and organization-wide provider accounting. | Flood/oversize/cancellation tests and no noisy-neighbor starvation at declared load. |
| Reliability | Idempotent writes, optimistic concurrency, atomic quota reservations, bounded retries, request deadlines. | Duplicate requests and crash/retry tests preserve state and spend accounting. |
| Recovery | Versioned migrations, backups, restore verification, derived-index rebuild and rollback. | Timed restore from backup and rollback rehearsal using synthetic data. |
| Observability | Per-layer latency, fit, token-estimate error, retrieval hit/empty rate, index lag, summary age, replay and provider usage. | Dashboards/alerts from synthetic load; no raw prompt bodies by default. |
| Supply chain | Locked dependencies, vulnerability/license review, SBOM and release provenance. | Reproducible clean build and reviewed release artifacts. |
| Interfaces | Versioned API/SDK contracts and migration policy; stable error taxonomy. | Compatibility fixtures and integration examples. |

## Proposed performance and operational targets

For owner review after workload selection: warm local assembly p95 ≤100 ms for the 100-turn fixture and ≤300 ms for 10,000 indexed chunks on a declared 4-vCPU/8-GB host, excluding provider latency. These are test targets, not measured capability. Report cold build time and memory separately; test Unicode and large tool outputs.

Proposed service baseline: 99.9% monthly successful assembly availability, with explicit exclusions and separate provider availability reporting; RPO ≤24 hours and RTO ≤4 hours for the initial self-hosted pilot. Owner/customer requirements may require stronger targets. C10 must record deployment size, concurrent request rate, storage size and dataset characteristics before load tests. Production acceptance requires observed pilot evidence and an operating plan, not a short test extrapolated to an SLA.

## Expansion constraints

Do not add Kubernetes, a vector database, multi-region failover, automatic memory extraction or cross-agent sharing simply to appear enterprise-ready. Add each when a recorded workload, recovery requirement or measured retrieval failure justifies it. Prefer fewer operational dependencies until evidence requires more.

Multi-agent memory, if later added, needs explicit sharing scopes and source ownership; a shared index is not shared authorization. Deployment region, provider data handling and retention are owner/customer decisions before using sensitive workloads.
