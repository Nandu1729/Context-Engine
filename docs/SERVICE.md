# Authenticated service — C08

Package 0.8.0 adds an optional, local self-hosted API around the existing memory/core. It does not deploy hosted SaaS, call an LLM, read `.env`, execute historical tools, generate summaries or change C06's frozen algorithm. API version is `/v1`; package version and API version are separate.

## Run the synthetic demonstration

```bash
uv sync --locked --all-extras --python 3.12.13
uv run --locked python -m context_engine.service.demo
```

This creates temporary private databases and random short-lived synthetic credentials, starts a loopback HTTP server, checks two-tenant isolation and API/SDK equivalence, and shuts down. It prints only evidence counts/booleans, not credentials or conversation content. No external inference occurs. Optional `--output NEW_PATH.json` exports evidence without overwriting.

For an operator-configured local instance:

```bash
uv run --locked python -m context_engine.service --config /absolute/private/service.json --port 8000
```

Use `examples/service-config.example.json` as a structural template, replacing its absolute paths. The configuration must be a private regular file (0600 on POSIX), at most 64 KiB. Separate memory, deletion-authority and service-control database files are required. No credentials appear in arguments. The supplied template has no identities, so it denies every request. Keep private configuration under `output/private/` or another protected application directory; never put real credentials in the example or brain.

The launcher binds only 127.0.0.1, disables access logging and server headers, and limits concurrency to 16. It is a local pilot launcher, not a public TLS deployment. The optional HTTP client requires HTTPS except loopback development and disables redirects/proxy inheritance. Do not expose plaintext bearer traffic remotely. TLS termination, encrypted storage, cross-platform ACLs, external IdP provisioning and production load/recovery approval remain operator/C09–C12 work.

## Identity and authorization

`Authenticator` accepts either an operator-provisioned service credential or a signed external-IdP access JWT. Authentication runs before request-body parsing, then every resource handler checks permissions before calling memory, retrieval, export or deletion.

Service credentials are at least 32 random bytes encoded with prefix `ce_`. Store only SHA-256(token) in `auth.service_credentials`, mapping to `{"principal": {"subject": "svc-1", "tenant": "tenant-a", "role": "operator", "sessions": ["session-a"]}, "expires_at": UNIX_SECONDS}`. Deliver the original through a secret manager. Tokens expire; removing the hash and restarting revokes access. This is configured credentials, not a credential-issuance/login API. Never reuse the Groq key as a service credential.

External identity configuration supplies an exact HTTPS `issuer`, an API-specific `audience`, `keys` mapping key IDs to trusted RSA public-key PEMs, and `subjects` mapping verified subjects to explicit Principals. Only RS256 with RSA >=2048 bits is accepted. Required claims: exp, iat, nbf, iss, aud, sub; numeric dates must be integers, current and within the configured lifetime (default 3,600 seconds). Signature, issuer, audience, key ID and expiry are checked. Unknown subjects/keys, expired/forged tokens and symmetric-algorithm substitutions fail closed. Use a distinct API audience for access tokens, not a login application's ID-token audience.

Tenant/role/session claims inside a JWT never grant permissions: the operator's subject binding is authoritative. Key IDs do not select URLs; no untrusted discovery/JWKS fetch is performed. Import authenticated public keys from your IdP through deployment configuration; overlap old/new keys while rotating, remove revoked subjects/keys and restart. Automatic discovery, refresh and live IdP provisioning have not been qualified. Signed synthetic IdP tokens are tested end-to-end locally.

| Role | Allowed operations within its tenant and session allowlist |
|---|---|
| reader | Read metadata/history/pins; assemble context |
| operator | Reader operations plus create session, ingest/revise turns and pins |
| admin | Operator operations plus export/delete; tenant audit requires wildcard session access |

Even admin cannot cross tenants. `sessions: ["*"]` explicitly allows all sessions in that tenant; no implicit wildcard. IDs are bounded opaque ASCII identifiers (letters, digits, `_`, `-`, 1–80 characters). Prefer random IDs, not emails or customer names. Trusted SDK callers can construct Principals; untrusted HTTP callers cannot.

## API contract

Every route, including `GET /v1/openapi.json`, requires one `Authorization: Bearer ...` header. Duplicate authorization headers are rejected. OpenAPI declares bearer authentication and the input schemas. Responses use `Cache-Control: no-store` and a server-generated `X-Request-ID`; caller-supplied IDs do not enter audit records.

Resource prefix: `/v1/tenants/{tenant}/sessions/{session}`.

| Method / suffix | Input and result |
|---|---|
| PUT (prefix) | Idempotent session creation; returns `revision` |
| GET (prefix) | Metadata-only snapshot: revision, snapshot_id, turn/pin counts; no raw content |
| POST `/turns` | `id`, `operation_id`, `expected_revision`, timezone-aware `timestamp`, optional `revision`/`expires_at`, and `messages`; returns scope `revision` |
| GET `/turns` | `offset=0`, `limit=20` (1–100), optional `snapshot_id`; returns items, revision, snapshot_id, next_offset |
| GET `/pins` | Active pins (at most 256) and revision |
| PUT `/pins/{key}` | `value`, `expected_revision`, timezone-aware `effective_at`, optional revision/expiry/source; returns revision |
| POST `/context` | `question`, `expected_revision`, `input_cap` (default 900, max 32,000); returns snapshot_id, revision, API-ready request, estimated_tokens, provider_accounting_verified=false |
| GET `/export` | Explicit content-bearing memory snapshot; admin only |
| DELETE (prefix) | `expected_revision` query; tombstones scope; admin only |
| DELETE `/turns/{key}` or `/pins/{key}` | `expected_revision` query; tombstones item and returns current revision; admin only |

`GET /v1/tenants/{tenant}/audit?after=0&limit=20` returns scoped metadata events and `next_after`. Sequence IDs need not be contiguous within a tenant. Initial `after=0`; resume from the returned sequence. Audit reads are themselves audited.

History pagination requires `snapshot_id` for nonzero offsets; a changed revision/content/expiry returns 409 instead of silently mixing snapshots. Pins are a bounded complete collection, not paginated. No store-wide backup/restore/prune endpoint, unscoped session enumeration, summary-generation endpoint or inference endpoint is exposed.

Messages have `id`, role (`user`, `assistant`, `tool`), content and optional tool_call_id/tool_calls. System messages are rejected: system policy comes only from server configuration. Tool calls contain call_id/name/arguments_json; complete call/result pairs must be ingested atomically. They remain history data and are never executed. Pin origin and scope are server-owned. Optional source references contain turn_id/message_id/revision/start/end/message_hash; the core verifies the original source. Source deletion invalidates its pins. Pins without provenance require explicit deletion when their source is removed.

Example ingestion body:

```json
{"id":"t1","operation_id":"ingest-1","expected_revision":0,"timestamp":"2026-09-13T12:00:00Z","messages":[{"id":"m1","role":"user","content":"Database PostgreSQL"}]}
```

Unknown body fields, duplicate JSON keys, NaN, invalid UTF-8, invalid roles and malformed contracts are rejected. Bodies are capped at 262,144 bytes, including streamed bodies, with a 10-second receive deadline. Dates require timezone information. Strings/message counts have additional schema limits. Scope storage bounds remain in MEMORY.md. A too-small input cap can return invalid_configuration or required_context_too_large; mandatory instructions/pins/question are never silently dropped.

Idempotency: identical turn operation_id + payload returns the original scope revision even if the supplied expected_revision is stale. Reusing the key with different content conflicts. A replayed receipt cannot revive a deleted turn. Creation is idempotent while active, but deleted IDs remain tombstoned. Pin updates and deletes use compare-and-swap, not automatic retries; after an ambiguous response, read current state before deciding whether to retry. Read a fresh revision before an independent mutation. API errors do not reset memory receipts or provider accounting.

Errors contain only `{"error":{"code":"...","request_id":"..."}}`; validation inputs, exception text and prompts are never echoed. Statuses: 401 unauthenticated; 403 forbidden; 409 stale revision/snapshot; 422 invalid JSON/schema/core budget/contract; 413 body too large; 408 receive timeout; 429 request/session quota; 503 storage/integrity/tokenizer unavailable; 500 unexpected failure. 401 includes WWW-Authenticate; 429 includes Retry-After: 60 (session-quota exhaustion needs operator review, not merely waiting). Missing/tombstoned scopes currently use memory_revision_conflict/409; no existence detail is disclosed before authorization.

## Quotas, audit and consistency limits

Service control is a separate private SQLite database with shared-worker transactional request admission (default 60 requests per rolling minute per authenticated tenant) and cumulative session slots (default 100 per tenant). Reserve a session slot before memory creation; failed/deleted slots remain reserved, preventing create/delete bypass. Operator migration is needed to change policy or reclaim capacity. Existing core bounds plus finite session slots bound active originals; audit, tombstones, revisions/ingestion receipts and control records still need disk monitoring/retention planning in C10. Per-request ingress/connection limits must also be enforced by the deployment gateway; authenticated route quotas are not global DDoS protection.

Since0.9.3,control schema2 uses distinct admission row IDs,not unique timestamps.
Existing schema1 requires explicit `migrate_v1=True` after stopping service/backing
up;normal startup will not silently migrate it. See [repair and migration](C10_ADMISSION_REPAIR.md).

Resource operations write an audit intent before touching memory, then record outcome and revision afterward. Audit holds request ID, timestamp, action, hashed actor/tenant/session and controlled outcome; no messages, pins, question, answer or bearer credential. Pre-authentication/JSON-validation failures have sanitized responses but are not persisted as per-resource actor events. Audit queries require tenant-wide admin access. Hashing identifiers does not make guessable IDs anonymous.

Memory and audit databases have separate commits: a crash or failed completion write can leave `started` after a successful mutation. Never treat that as proof the mutation failed. Recover through memory revision/idempotency receipts; no distributed exactly-once claim. Audit is locally restricted, not tamper-proof against the host administrator. Access logs are off in the supplied launcher; external gateways must also avoid bodies/authorization headers.

Assembly validates the expected revision and actual snapshot identity before returning. Authorization and snapshot checks are point-in-time: already exported data cannot be recalled, and a concurrent later edit does not retroactively invalidate a response. Since0.9.1 service assembly uses disposable processes with parent timeout/disconnect termination; direct SDK calls remain cooperative. Global quotas, cross-platform and larger workloads still require qualification. Do not claim production noisy-neighbor, SLO or recovery guarantees from this local demo.

## Two integration paths

Caller-managed inference: `service.integrations.prepare_for_caller(memory, verified_principal, tenant, session, question, budget, system=trusted_policy)` returns the same snapshot/context as the core. Pass `context.request.to_wire()` to your chosen inference integration. Once exported, lifecycle checks are the caller's responsibility. Alternatively `ServiceClient.context(...)` obtains the authenticated HTTP representation without importing a model SDK.

Groq adapter: `await service.integrations.complete_with_groq(..., client=explicit_provider_client, system=trusted_policy)` authorizes first, then uses the existing MemoryProvider and shared quota ledger. It neither reads a key nor authorizes spending. MemoryProvider rechecks snapshot identity after inference and discards stale answers while preserving usage receipts. C08 tests inject a synthetic transport; no real Groq requests are made. Never substitute C08 provider/config identity into the frozen C06 run.

## C06 reminder and preserved environment

D073 supersedes the historical D050 deferral: C06 is complete at snapshot249. Review its preserved limitations before C09/C11/C12; do not start another C06 batch. `archives/c06-live/` preserves the0.7.2 wheel/protocol/freeze and hash-locked dependencies; `output/private/c06-frozen-env` is its historical installed environment. Service storage and C09 work must not alter that matrix, journal or ledger. New C09 preparation uses its own versioned identity, not the historical runtime. See C06_REPORT and C09_REPORT for current evidence.

Sources informing implementation: [PyJWT verification API](https://pyjwt.readthedocs.io/en/latest/api.html) for fixed algorithm, issuer/audience and required-claim verification; [FastAPI security documentation](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/) for application-owned authorization. The role policy, pinned-key lifecycle and local quotas described above are project decisions verified by local tests, not vendor security guarantees.
## C09 process-backed assembly deadline (0.9.1)

`create_app(..., limits=ServiceLimits(assembly_deadline_seconds=30, assembly_workers=2))` accepts a
finite deadline greater than0 and at most300 seconds. The private launcher config
may include `"limits": {"assembly_deadline_seconds": 30, "assembly_workers": 2}`;
omitting it uses30 seconds and2 workers. Capacity is1–8 per service process.
The server owns this setting; callers cannot supply a deadline in the request body.
Authorization precedes launch. Snapshot/index/assembly/revision checking execute in
a fresh subprocess against the configured local store, using UTC clock semantics;
parent timeouts and ASGI disconnect/task cancellation kill/reap it. No indefinite
worker queue: saturated capacity returns503 `assembly_busy`; cancellation returns503
`work_cancelled` with an audit outcome and no prompt content. Shutdown also reaps
late-starting workers. Stdout2MB/stdin256KiB caps and stripped environment protect
the IPC boundary. Stored originals survive; interrupted SQLite transactions recover
on reopen, but previously committed index batches may remain. Worker reaping/OS
scheduling is not a strict response-latency SLO. Other sync endpoints and direct SDK
calls do not gain process isolation. Local process counts multiply with service
instances; global admission/load qualification remains future work. See the
[threat model](C09_THREAT_MODEL.md) for remaining live-quality/operational gates.
