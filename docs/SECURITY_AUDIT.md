# Security audit summary

Updated 2026-10-31 (code review of 0.10.0, dependency scan of 0.11.0; no penetration test). Detailed threat
model: [C09_THREAT_MODEL](C09_THREAT_MODEL.md). Enterprise gates: [ENTERPRISE](ENTERPRISE.md).

| Area | Current implementation | Assessment | Gap / action |
|---|---|---|---|
| API credentials | Service tokens stored as SHA-256 digests with expiry (`service/auth.py`); JWT RS256 with pinned public keys and explicit subject bindings. | Adequate for high-entropy generated tokens. | Hosted signup would need self-service key issuance, rotation UI and revocation propagation. |
| Authentication | No identity from untrusted claims; roles/tenants come from operator config. | Good. | External IdP integration unqualified. |
| Authorization / tenant isolation | `Principal.authorize` checks tenant, session and role before any memory read, retrieval or worker dispatch. Memory rows keyed by encoded scope; 19 process tests cover isolation. | Good by design and test. | Shared SQLite file per deployment; a hosted multi-tenant service needs per-tenant DB or Postgres row-level security and an isolation test suite against it. |
| SQL injection | Parameterized `sqlite3` statements throughout `memory/store.py`. | No string-built SQL found. | — |
| Prompt injection | History, retrieved chunks and summaries are rendered as `[KIND DATA]` user content, never system role; pins/permissions cannot be granted by content. `PromptSummarizer` instructs the model to treat turns as data. | Mitigates, cannot prevent: a model may still follow quoted instructions. | No universal injection-resistance claim. Measure with adversarial cases before marketing. |
| Sensitive data in logs | Prompt bodies hidden by default (`--show-content` opt-in); provider and summarizer exceptions redacted (`raise ... from None`). | Good. | Hosted logging pipeline must keep the same default. |
| Secrets on disk | `.env*` git-ignored; private file permission checks (POSIX and Windows ACLs); workers do not inherit API keys. | Good. | `.env` and `.env.gemini` exist locally with real keys; never commit or copy them. |
| Data retention / deletion | Turn/pin/scope deletion with tombstones; derived chunks, replay cache and covering summaries removed; restore re-applies deletions. 0.10.0 keeps a summary only when the changed turn is not covered by it. | Good. | Retention policy per tenant (time-based) is not configurable yet. |
| Rate limiting | Request-size limit (413), bounded worker pool (default 2, max 8), assembly deadline. | **No per-tenant request rate limit or quota.** | Required before any hosted API (Phase 4). |
| Resource exhaustion | Bounded worker processes killed on timeout/disconnect; bounded page sizes; summary size limit 256 KB in store, 16 K chars in `update_summary`. | Good for self-hosting. | Not a sandbox or RSS limit; global concurrency limits are deployment-owned. |
| Request validation | Pydantic schemas plus dataclass validation; strict JSON (duplicate keys, non-finite numbers rejected). | Good. | — |
| Error handling | Typed `ContextEngineError` hierarchy with stable codes; no stack traces or bodies in responses. | Good. | — |
| Supply chain | Locked `uv.lock`. 2026-10-31 scan (`uv audit`, OSV database, 46 packages incl. extras/dev): 71 advisories in certifi 2026.7.22 and urllib3 2.7.0 (core, via tiktoken→requests), PyJWT 2.14.0 (service extra; service uses RS256 with pinned keys, not PyJWKClient/OKP) and Pillow 12.3.0 (reports/dev only, 59 advisories). Upgraded in the lock to certifi 2026.10.23, urllib3 2.8.0, PyJWT 2.15.1, Pillow 13.0.0; re-scan: **0 known vulnerabilities**. License scan from installed metadata: all permissive (MIT, BSD, Apache-2.0, PSF, MPL-2.0 for certifi and dev-only hypothesis); no GPL/AGPL. | Clean for 0.11.0. Users installing from PyPI resolve transitive versions themselves. | Re-run `uv audit --locked` before every release. |

No critical vulnerability was found in this review. The highest-risk items for a
commercial launch are missing per-tenant rate limits (the supply chain was scanned and
patched for 0.11.0).
