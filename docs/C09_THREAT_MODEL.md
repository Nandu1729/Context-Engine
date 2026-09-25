# C09 threat model and findings

0.9.2 supplement:F06 has an explicit default-off missing-chunk recovery mode;
source/dedup checks persist through finalization and deletion-aware memory. See
[repair001](C09_REPAIR_REPORT.md). Default CAP/WINDOW loss remains possible,as do
ranking/budget misses. Optional exact JSON parsing rejects malformed/Unicode-spoofed
ASCII identifiers but does not validate truth or grant permissions. F05 qualification
remains OPEN;no new API calls or changed historical scores.

Live001 supplement2026-09-23: [measured evidence](C09_LIVE_REPORT.md) replaces F05's
NOT_MEASURED state,not its open release-evidence disposition.32/32 API responses,
8/32 exact matches,zero forbidden answers/input-cap overruns;source estimate still
under-counted3 inputs(max ratio1.708333). F06 middle-loss reproduced in both CAP/
retrieval budgets. No universal injection/token guarantee or risk waiver. Current
.env was used only for this approved synthetic experiment; no secret was exported.

2026-09-22. Local self-hosted service + SDK. Synthetic offline review; not a
penetration-test certification, public deployment approval or universal LLM defense.

## 0.9.1 current disposition (supersedes F03 below)

F03's local **assembly** worker-containment gap is addressed by disposable subprocesses,
default2/max8 slots, no queue, parent timeout, ASGI disconnect/task-cancel/shutdown
kill-and-reap, bounded pipes and sanitized worker environment.19 actual-process tests
include SQLite recovery after a kill inside a transaction. Authorized scope/revision
checks execute in the child; no caller-selected command or model-derived permissions.
Current API/resource contract is in C09_REPORT and SERVICE. SDK direct calls remain
cooperative, and other HTTP handlers retain the framework's synchronous execution.
This is not a hostile-code sandbox, OS RSS limit, distributed cap or whole-request
SLO; a broken OS can delay process creation/reaping. TLS/IdP/load and cross-platform
qualification remain operational gates. F05 live quality/calibration and F06 retained
middle-text loss remain OPEN. No risk waiver or full C09 acceptance is inferred.

The initial findings below are retained as dated history; F03 no longer describes
the current `/context` implementation. New source/retention scoring is TEST_ONLY
and not evidence of model resistance to injection.

## Assets, actors and data flow

Assets: original histories, scoped pins/summaries/chunks/replay, deletion authority,
trusted system policy, server-owned identity bindings, service credentials, audit
metadata, immutable benchmark provenance. Provider keys and customer data are not
needed for these tests and were not read.

Actors: unauthenticated caller; authenticated malicious tenant; restricted reader or
operator; hostile history/tool author; trusted service administrator; local host/file
administrator. Host compromise and a malicious trusted administrator are outside
the application's isolation guarantee, not assumed impossible.

Flow: HTTP → authentication/body boundary → strict schema → quota/authorization →
scoped memory transaction → original/chunk validation → five-layer assembly →
authorized response. Quota is charged to the authenticated caller, never the requested
victim tenant. The SDK accepts caller-authorized scopes and is not an auth boundary.
No inference endpoint or provider dispatch exists in the service.

| Boundary / attack | Implemented control and evidence | Residual risk |
|---|---|---|
| Credentials/forged tenant or role | Pinned RS256 issuer/audience/subject bindings; expiring hashed service keys; negative claims/algorithm/signature/duplicate-header tests | Live IdP onboarding, key rotation and TLS deployment not qualified |
| Cross-tenant/session read, retrieval, cache, export, delete | Authorize before memory; valid denied payloads fail403 before patched memory methods; distinct canaries with identical IDs and warm indexes; existing C07 cache-scoping tests | Direct SDK users must enforce authorization; local DB admins can read content |
| Model/history authority escalation | Fixed system policy; user/tool roles constrained; evidence remains data; forged source hashes rejected; service never asks a model for permissions | A model can still follow malicious data in its answer; no live injection-resistance evidence |
| Stale/deleted provenance | Revision checks, invalidated derived state, expiry and tombstones; backup restore uses current deletion authority | Exported/provider-held copies cannot be recalled; host must preserve deletion authority |
| Secret/PII disclosure | Synthetic canaries absent from errors/audit/default metadata/captured logs; authorized export/context intentionally contain content | No automated PII redaction promised; proxy/operator-added logging outside review |
| Resource abuse | 262,144-byte streamed body cap;10s body-read timeout; strict schema sizes; per-scope memory/index limits; persistent quota transactions; cooperative assembly cancellation | Native tokenizer/BM25/SQLite calls and threadpool work are not preemptively terminated; see F03 |
| Benchmark leakage/false claims | Separate scenario/truth resources, fixed splits/hash manifest, scenario-only engine builder; TEST_ONLY/no network tests; separate C06 archives | Corpus author has seen fixtures; source presence is not retained-answer proof; no statistical quality claim |

## Findings and disposition

- **F01 — High verification gap, repaired:** new C09 credential test returned early
  for every `Bearer ce_...` token, skipping malformed/unknown checks. Removed bypass,
  split legitimate lowercase scheme into explicit success test. Also corrected
  cross-scope pin schema, DELETE request construction and victim-quota target/count.
  These were test defects, not evidence of an authentication bypass in the service.
- **F02 — Medium cancellation gap, mitigated:** validation/entry/exit checks missing;
  CAP and chunk loops only checked per turn; index transaction lacked final check.
  Added per-message/chunk/CAP-search checks, stage/return checks, and precommit
  cancellation. Deterministic tests prove mid-batch rollback, precommit rollback,
  resumability and original-history preservation. Earlier completed index batches
  may remain committed; assembly is not one atomic index transaction.
- **F03 — High availability risk, OPEN; no waiver:** a valid caller can occupy a
  worker during large/non-cooperative operations. Default30s (configurable >0 to300s)
  is a cooperative deadline, **not** a maximum response/CPU time. Disconnect after
  body receipt does not terminate sync work. Launcher concurrency limits and input
  bounds mitigate but do not prove host-level containment. Before public deployment,
  implement/test bounded worker isolation and disconnect/timeout cleanup, or obtain
  explicit owner scope/risk acceptance. Do not silently move this C09 gate to C10.
- **F04 — Medium reproducibility gap, repaired:** version was0.9.0 while lock/freeze
  remained0.8.0. Preserve verified C08 wheel/freeze; update only new version's lock
  and source freeze. Historical C06 artifacts remain unmodified.
- **F05 — High release-evidence gap, OPEN:** held-out answer quality, actual input
  calibration (S12), and hostile-model behavior have not been measured. Synthetic
  preparation is not qualification. New approved live protocol/identity needed.
- **F06 — Medium retention limitation, OPEN:** CAP can remove relevant middle text
  even in selected recent turns (S11). Unicode test was incorrectly asserting that
  all working text survives CAP; it now verifies preserved originals and uncapped
  wire data separately. No algorithm tuned to C06 or new fixtures.

No confirmed cross-tenant authorization exploit found in this local review.
This is bounded evidence, not proof that no vulnerabilities remain.

## Resource/log review limits

Memory bounds currently10,000 turns,8,000,000 bytes,100,000 chunks per scope; index
batches≤256. API message64,000 characters,32 messages/turn, question/pin16,000,
input cap≤32,000; byte cap applies before JSON decode. Tests lower selected storage
ceilings to exercise rejection paths; they are not full-scale load benchmarks.
Slow-body test uses a deterministic timeout stub, not real slow-client load evidence.
Concurrent tests exercise revision/quota correctness locally, not sustained SLOs.

Cancellation is only trusted caller/server configuration; no cancellation object is
deserialized from HTTP. HTTP work-cancelled responses contain only a typed error
and request ID, status503; audit records outcome without prompt content. Default
SDK diagnostics remain content-free; content APIs require explicit access. Local
SQLite data is not encrypted by this package; deployment must protect files/backups.
Audit retention, tamper resistance, ingress controls and dependency/supply-chain
qualification remain operational work. **No enterprise-ready claim.**
