# Provider adapter, replay and accounting — C05

Implemented in package 0.5.0. This is an offline-verified Groq integration, not a live-provider qualification or enterprise release. See the [checkpoint report](C05_REPORT.md). Installation of the optional transport uses `uv sync --locked --extra provider --python 3.12.13`; the core does not require HTTPX or a provider SDK.

## Safe demonstration

```bash
uv run --locked context-engine provider-demo
uv run --locked context-engine provider-demo --output output/my-provider-demo.json
uv run --locked context-engine provider-probe --help
```

The demo uses synthetic responses, synthetic prices and a temporary SQLite database that is removed on completion. It demonstrates first execution, zero-new-cost replay, a changed-question cache miss, and a changed-generation miss blocked by quota. It makes exactly two simulated transport calls and zero inference calls. Its 96 micro-USD total is synthetic accounting, not actual spending or measured savings. Exports refuse to overwrite existing files. Saved evidence: [offline demonstration](../output/c05-provider-demo.json).

`inspect` and `probe` remain offline. Only the separately named `provider-probe` can send inference. It requires all of: `--allow-live`, `GROQ_API_KEY` supplied through the environment, an explicit `--ledger` path, account/security/snapshot identifiers, a positive `--daily-budget-microusd`, explicit RPM/TPM/RPD/TPD limits, a versioned price card and all three input/cached-input/output rates. There is no bundled live-spending command with guessed account prices or limits. `--input` accepts the [inspection JSON contract](PIPELINE.md); omission selects synthetic input. `--model` selects either PRD model. Output omits answer and tool argument bodies unless `--show-content` is explicitly supplied. CLI replay is disabled; the SDK enables it explicitly. The live probe has been tested with an injected fake transport only.

## SDK boundary

Package 0.7.1 adds explicit `QuotaPolicy(..., billing_mode="free_tier", daily_budget_microusd=0)` with zero-price cards. Metered-mode zero budgets still block calls. Free mode keeps request/token quotas and accounting but relies on confirmed account tier, not automatic billing verification; see [free-tier runner safeguards](RUNNER.md). The standalone `provider-probe` CLI remains metered-only; use the benchmark runner's controlled free-tier path for C06.

Construct `ProviderClient` from `context_engine.providers.client` with a `RuntimeStore`, `QuotaPolicy`, `PriceCard` and credential. Contracts are in `context_engine.providers.contracts`; the store is in `context_engine.providers.store`. Given an authorized assembled request:

```python
result = await client.complete(
    assembled.request,
    budget,
    scope=authorized_scope,
    security_scope="permission-revision-7",
    snapshot_revision="history-revision-42",
    policy_version="application-policy-v1",
)
metadata = result.to_dict()  # No answer or tool argument bodies.
```

The application must authenticate and authorize the scope before calling this API, and change its security/snapshot revisions when permissions or source data change. These strings partition cache keys; they do not authenticate anyone. Construct a separate client when changing account, prices, retry/replay policy or transport; do not mutate these during in-flight calls. Generation settings are snapshotted per call. API keys are never included in cache keys, SQLite rows, result exports or controlled exception text; credential rotation within the same authorized scope can reuse replay.

Generation defaults: `openai/gpt-oss-120b`, maximum completion 256, temperature 0, reasoning effort `low`, tools disabled. `openai/gpt-oss-20b` is also supported. Completion reservation must agree with the assembled budget. Model profile bounds are 131,072 context / 65,536 completion tokens, checked against current primary documentation; see [sources](SOURCES.md). Temperature zero is not a guarantee of deterministic provider output.

The transport posts non-streaming JSON to a fixed Groq HTTPS endpoint with TLS verification, no redirects, no environment-proxy inheritance, one choice, on-demand service and `include_reasoning=false`. It uses optional HTTPX 0.28.1 with no SDK retry layer. Request/response bodies are bounded to 2 MB. Parsing rejects duplicate keys, nonfinite numbers, invalid roles/models/usage, inconsistent totals and malformed tool calls. Provider body/error text and hidden reasoning are not logged. Tools returned with explicit `tool_choice="auto"` must match declared tools; the adapter never executes them or replays their side effects.

## Outcomes and retry rules

`ModelResult.status` distinguishes `success`, `replay`, `truncated`, `tool_calls`, `filtered` and `error`. Request-contract and impossible-budget errors are typed exceptions before dispatch. Runtime errors carry controlled codes and attempt IDs. Valid usage on truncated/filtered/malformed-content responses is charged, but those responses are not cached as successful answers. Missing or inconsistent usage stays unknown, never zero by inference.

The default is three attempts, a 20-second per-attempt timeout and a 45-second total deadline, with at most ten seconds of backoff. Configuration is bounded to five attempts and 300-second durations. Only known pre-send connection failures and HTTP 429 are automatically retried. Each attempt is independently admitted and recorded. `Retry-After` is respected; a delay beyond the backoff/deadline stops the call instead of retrying early. Other confirmed 4xx rejections terminate without token charges. HTTP 408/5xx, interrupted reads/writes, malformed responses without valid usage and ambiguous timeouts hold reservations and are not automatically retried.

Async cancellation propagates to the caller and preserves an uncertain/in-flight reservation. SQLite operations are short synchronous transactions with a 0.2-second lock timeout; tokenization and these operations are not interruptible mid-call. The network deadline is rechecked after admission. This is not a hard real-time latency guarantee.

## Transactional money and quota accounting

One explicit SQLite file contains separate replay, attempts, account-policy and audit-event tables. This refines the PRD's illustrative separate cache/ledger filenames: one transaction commits successful usage and its replay entry together. `BEGIN IMMEDIATE` serializes admission across threads/processes sharing that local database. No network-filesystem or distributed-database guarantee is claimed.

All money is integer micro-US dollars: 1,000,000 micro-USD = $1. Price-card fields are micro-USD **per million tokens**, not dollars per token. For example, a hypothetical $0.15/million rate would be 150,000; this is a unit illustration, not an account quote. Prices must be supplied and versioned. Input, provider-cached input and output rates are distinct. Reasoning tokens are a subset of output and never charged twice. Missing cached-input detail uses the conservative maximum input rate; missing reasoning detail stays unknown. Reported cost is calculated from observed usage and the supplied rate card, not independently verified billing.

Admission reserves full estimated input plus maximum completion tokens and the corresponding conservative cost. The daily spending default is zero. RPM/TPM use a rolling 60-second local window; RPD/TPD/spend use UTC-day boundaries. Cached provider input is conservatively included in local token limits. Known pre-send failures release their request/token/cost reservation; confirmed rejected requests retain their request count. Completed calls settle against observed usage.

Unresolved requests hold request/token/money capacity across window/day rollover. A crash after reservation does not silently release funds. `resolve_uncertain(attempt_id, evidence_ref="operator-record-123", now=..., usage=Usage(...))` reconciles validated observed usage. Alternatively `confirmed_not_processed=True` releases it only with external evidence. Reconciliation is explicit, audited and one-shot; it is not an automatic timeout-expiry policy. A failed post-response database write leaves the existing reservation held and does not create a replay hit.

Policies are persisted per caller-supplied account ID. All participating workers must use the same account identity, database and policy. A changed policy is rejected until an explicit future migration; creating a new account ID/database bypasses shared accounting and is not a safe way to raise limits. Account traffic outside this store is not coordinated. A backwards wall-clock jump beyond five seconds blocks admission.

The local tokenizer's 1.07 calibration factor is unverified against Groq. Actual usage can exceed its reservation; the ledger records the full observed overrun and warns. Thus concurrent **local reservations** cannot exceed configured ceilings, but this is not an absolute provider-billing cap. Provider/account-side spending controls and live calibration remain necessary.

## Replay, privacy and lifecycle

Replay is disabled by default. `ReplayPolicy(enabled=True, ttl_seconds=3600)` explicitly permits storing response bodies; TTL is bounded to one day. Keys include the full request, tools, model/generation, endpoint/adapter, tokenizer/calibration/budget, account, tenant/session, security scope, snapshot revision, policy version, price version/rates and transport namespace. Fake and live HTTP transport namespaces differ and include HTTPX's version.

A replay preserves original usage and original cost, links its source attempt and adds an audit event with **zero new provider cost**. It is not a new independent benchmark answer. Only complete stop responses are cached. Payload digests and source-attempt/account/key binding are checked before reuse; corruption fails closed with no replacement network call. Expiry prevents reuse but does not erase old bytes.

By default the ledger holds accounting metadata, not prompt/answer bodies. Database files are created mode 0600 on POSIX, leaf symlinks and existing group/world-readable files are rejected. Use a trusted private local directory: C05 is not encrypted-at-rest storage, a hostile-filesystem defense or an authorization service. Retention/erasure, schema/policy migration, source-deletion propagation and restartable history/index memory belong to C07; authenticated service enforcement to C08; cross-platform/load/recovery qualification to C09/C10. Do not ingest customer data yet.

## Reproducibility boundary

C04's reference freeze and 0.4.0 wheel are preserved under `archives/c04/`; its original outputs remain unchanged. The current packaged freeze explicitly identifies 0.5.0 source and the same offline corpus/protocol/targets. It does not turn old snapshots into new runs. C06 must record the full provider dependency/configuration profile and connect trusted adapter records to benchmark manifests. No live model result, measured accuracy, provider calibration or actual savings is claimed by C05.
