# C08 report — authenticated local service

Date: 2026-09-13. Package: 0.8.0. Status: READY for owner review; not owner-accepted or enterprise-qualified.

## What was done

- Added optional versioned API for scoped history, pins, context assembly, export and deletion.
- Added signed external-IdP JWT verification with server-owned permissions, expiring hashed service credentials, reader/operator/admin roles and tenant/session isolation.
- Added shared local quotas, content-free audit intents, revision checks, idempotent turn ingestion, snapshot-bound pagination, bounded input and sanitized errors.
- Added caller-managed and Groq-adapter integration paths, a safe HTTP client, private local launcher, OpenAPI schema and deployment/contract guide.
- Preserved C06's live 0.7.2 environment and zero-call resume evidence before changing source. Its results, targets and ledger are unchanged.

## Verification

526 tests pass (79.06 seconds), including 72 new C08 cases. Lint/format, dependency compatibility, offline lock check and wheel/source builds pass. [Loopback demonstration](../output/c08-service-demo.json) passes all five checks: authentication required, tenants isolated, cross-tenant export denied, SDK/API context equivalent and audit content-free. It starts/stops a real loopback server with synthetic data; zero external inference.

Clean installed core-only environment passes memory and frozen flagship checks with socket networking disabled and no HTTPX/FastAPI/PyJWT installed. Clean service installation passes the real loopback demo from outside the repository. Core installation was hash-checked offline; service installation needed registry metadata, then completed with dependency hash verification. Packages exclude private credentials/databases. The frozen flagship remains 804/900 estimated tokens; no quality tuning.

C06's archived 0.7.2 environment validates its original live snapshot and produces a byte-identical zero-call resume. Its ledger remains 28 completed requests / 22,772 tokens / configured $0; C08 made no real inference requests. Brain integrity and source PRD preservation pass. Detailed build/freeze evidence is saved in the project journal.

## Limitations and next step

Local implementation only: external IdP provisioning, public TLS deployment, automatic key discovery/refresh, production load/cancellation and recovery/audit-retention qualification remain ahead. Two upstream test-client deprecation warnings are recorded; no provider dependencies were changed to suppress them. See [service contracts](SERVICE.md).

Reminder: C06 remains incomplete. The owner authorized this offline C08 step, not waiving C06. After C08, return to [C06's preserved live run](C06_REPORT.md) before C09 quality work, C11 measured cost work or C12 release. No background inference is running; next immutable live snapshot is batch005.
