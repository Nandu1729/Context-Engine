# External verification register

## C06 free-tier preparation — 2026-09-13

- Rechecked [Groq rate limits](https://console.groq.com/docs/rate-limits), [billing FAQs](https://console.groq.com/docs/billing-faqs) and [API reference](https://console.groq.com/docs/api-reference). Published Free-plan rows include both GPT-OSS benchmark models, with request/token limits; actual organization settings are authoritative. No private account settings were inspected.
- Implementation choice: explicit caller-confirmed free-tier policy with zero configured prices and zero paid-spending caps, while retaining local quota/uncertainty enforcement. This is not a claim that an API key reveals account tier or that zero local prices prevent provider-side charges. Owner confirmation and actual limits remain required before live use; free-tier cost records are not paid-plan savings evidence.

## C07 local storage verification — 2026-09-08

- [SQLite ATTACH](https://www.sqlite.org/lang_attach.html) conditions cross-file atomicity on disk-backed main storage and non-WAL journals. C07 uses attached deletion authority, rollback journals and FULL synchronization; local rollback/concurrency tests are not a distributed crash qualification.
- [SQLite backup API](https://www.sqlite.org/backup.html) supports consistent incremental copies. C07 uses bounded backup calls and requires separately retained deletion authority at restore. This recovery design is our engineering choice, not a SQLite deletion policy.
- [SQLite secure-delete](https://www.sqlite.org/pragma.html#pragma_secure_delete) informed current-table cleanup. Backups, exported copies, filesystem snapshots and provider-retained content require separate lifecycle controls; no cryptographic erasure claim is made.

Checked: 2026-09-07. These are point-in-time observations from primary sources. Recheck model availability, prices, dependency versions and account limits before integration or paid runs. No secret account settings were inspected.

| Source | Observed fact | Design implication |
|---|---|---|
| [Groq supported models](https://console.groq.com/docs/models) | Lists both PRD GPT-OSS models; 131,072 context capacity; public input/output prices match PRD examples at this check. | Retain configurable baseline model IDs and pricing; verify the actual account before use. |
| [Groq rate limits](https://console.groq.com/docs/rate-limits) | Limits apply at organization level; exact values are available in account settings; response headers expose quota state. Some accounts also have separate input/output throughput limits. | Model context allowance and shared quota admission need separate components. The PRD values are examples, not universal constants. |
| [Groq prompt caching](https://console.groq.com/docs/prompt-caching) | Requires exact prefix matches; minimum cacheable length varies by model between 128 and 1,024 tokens. Cached-token usage is observable. | Preserve stable prefixes and record observed hits; a 900-token benchmark cannot establish universal cache savings. |
| [OWASP prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) | Retrieved or external content can carry instructions that influence a model. | Treat evidence as untrusted data and enforce access and tool permissions outside model output. |

Architecture choices inferred from these sources are recommendations, not prescriptions from the providers.

## C01 dependency verification — 2026-09-07

- [tiktoken package metadata](https://pypi.org/project/tiktoken/) lists release 0.14.0. Installed and exercised that version locally; `o200k_harmony` loads and Unicode/full-request counting tests pass.
- [tiktoken encoding constructors](https://github.com/openai/tiktoken/blob/main/tiktoken_ext/openai_public.py) were inspected for encoding availability. First-time tokenizer asset loading can need network access; C01 setup deliberately fails with a controlled error when unavailable.
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) documents lock/sync controls. C01 uses a generated `uv.lock`, `--locked` verification, and a separate clean wheel install from a hash-checked runtime export.

Versions actually used and test evidence are recorded in [C01 report](C01_REPORT.md). Provider parameters/pricing and dependencies needed by later checkpoints still require verification when integrated.

## C02 retrieval verification — 2026-09-07

- [rank-bm25 package metadata](https://pypi.org/project/rank-bm25/) and the [maintainer's implementation](https://github.com/dorianbrown/rank_bm25/blob/master/rank_bm25.py) were reviewed. Installed rank-bm25 0.2.2; the package provides BM25 variants and NumPy scoring.
- Engineering choice: use BM25+ with an explicit lexical-match filter for small corpora. Record this variant and its parameters in the future benchmark manifest. This is our implementation choice, not a provider claim of higher quality.
- NumPy 2.5.3 resolved through the package dependency and is captured in `uv.lock`. The singleton, empty/no-match, ranking and deduplication behaviors are verified by local tests. No model-quality claims come from package documentation.

## C05 provider verification — 2026-09-08

- [Groq API reference](https://console.groq.com/docs/api-reference) was checked for chat completions, `max_completion_tokens`, tools, non-streaming responses and usage fields. [Reasoning documentation](https://console.groq.com/docs/reasoning) specifies GPT-OSS reasoning controls: use `include_reasoning=false`, not unsupported `reasoning_format` for these models.
- [Supported models](https://console.groq.com/docs/models) still lists both PRD GPT-OSS models, 131,072 context and 65,536 completion capacity. Public 120b input/output prices were $0.15/$0.60 per million; 20b $0.075/$0.30. These are point-in-time observations, not account quotes or hardcoded spending defaults; the adapter requires a supplied versioned price card.
- [Rate limits](https://console.groq.com/docs/rate-limits) documents organization-level limits and 429/Retry-After behavior. [Prompt caching](https://console.groq.com/docs/prompt-caching) documents cached-input usage details and distinct provider caching. C05 local replay is a separate feature; local quota accounting conservatively includes cached tokens and does not coordinate other account clients.
- [HTTPX async support](https://www.python-httpx.org/async/), [transports](https://www.python-httpx.org/advanced/transports/) and [timeouts](https://www.python-httpx.org/advanced/timeouts/) informed the optional HTTPX transport and offline mock tests. Installed 0.28.1; the adapter adds a total asyncio deadline beyond individual connect/read/write/pool timeouts.
- [SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html) supports the single-file `BEGIN IMMEDIATE` admission boundary. Local concurrency tests verify reservations; this is not distributed-storage or hostile-filesystem qualification.

Engineering choices, not provider promises: retry only known pre-send failures/429; hold ambiguous usage until explicit reconciliation; opt-in replay-body persistence; fixed HTTPS endpoint; no proxy inheritance or redirects. No credentials, account settings or paid inference were used to verify these documents.

## C06 rendering verification — 2026-09-08

- [Matplotlib package metadata](https://pypi.org/project/matplotlib/) and installed resolution confirm 3.11.1. [Backend documentation](https://matplotlib.org/stable/users/explain/figure/backends.html) describes noninteractive Agg rendering; [Figure.savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html) documents image export and metadata controls. The implementation uses Figure/Canvas directly, with no GUI or inference dependency.
- Local verification, not a documentation claim: report images regenerate byte-identically in the locked environment with socket networking disabled. Pillow 12.3.0 and Matplotlib versions are recorded in report manifests. Cross-platform raster equivalence remains unqualified.

## C08 identity/API verification — 2026-09-13

- Reviewed [PyJWT verification API](https://pyjwt.readthedocs.io/en/latest/api.html): fixed configured algorithm list, signature verification, required claims and explicit audience/issuer. Installed PyJWT 2.14.0 with cryptography 50.0.1. Project policy accepts only pinned RSA public keys/RS256 and server-owned subject bindings; no untrusted URL discovery or token-granted tenant roles.
- Reviewed [FastAPI authorization documentation](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/). Installed FastAPI 0.135.4, Starlette 1.6.0, Pydantic 2.13.5 and Uvicorn 0.41.0, locked as optional service dependencies. Actual startup, typed validation, middleware and HTTP behavior are exercised locally; documentation is not a claim of production security.
- Two upstream test-client deprecations remain visible: Starlette's HTTPX compatibility path and AnyIO BlockingPortal alias. Existing HTTPX 0.28.1 provider dependencies are deliberately preserved; no C06 dependency or model changes. Revisit service test-client migration separately before production dependency qualification.

## Gemini read-only setup — 2026-09-14

- [Models API](https://ai.google.dev/api/models) specifies GET /v1beta/models and model metadata/pagination. Local preflight makes one bounded page request and reports further-page presence; model listing is not proof of free inference entitlement.
- [API key guide](https://ai.google.dev/gemini-api/docs/api-key) documents authorization keys and x-goog-api-key authentication. New AI Studio keys default to auth keys. Implementation treats the explicit key as opaque header data, permits periods and never evaluates shell syntax; the real credential authenticated without alteration.
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) identifies project-level limits, model-dependent quotas and the AI Studio account view. Google documents midnight Pacific RPD reset, unlike our Groq local UTC policy. Gemini must receive its own reviewed quota accounting; exact values cannot be inferred from the model list.
- [Gemini compatibility guide](https://ai.google.dev/gemini-api/docs/openai) was inspected for future integration routing only. No generation adapter or inference run implemented yet. Existing core estimates are not a calibrated Gemini tokenizer.

## Groq timeout investigation — 2026-09-22

- [Project documentation](https://console.groq.com/docs/projects) describes project-scoped Dashboard Usage,Metrics and Logs views. These are possible sources for external request-status/usage evidence,not proof that the particular timed-out request has a visible row. No signed-in console access was available;owner asked for matching status and input/output counts,or provider confirmation not processed. Missing dashboard rows alone do not establish non-processing. See C06 report/D071.

## Groq reported upgrade sources — 2026-09-20

- [Rate-limit header semantics](https://console.groq.com/docs/rate-limits): request headers refer to daily requests, token headers to per-minute tokens, not daily token balance. Cached tokens are excluded by Groq; our conservative local accounting totals full usage. Current-key diagnostic D062 verifies HTTP200 plus these headers; it does not verify provider reset algorithm, daily remaining tokens or organization identity.
- [Supported models](https://console.groq.com/docs/models) lists GPT-OSS20b at $0.075 per million input tokens and $0.30 per million output tokens. Planning estimate for125 remaining requests at3,000 input +256 output each: $0.037725 before taxes; not a guaranteed bill or token bound.
- [Billing FAQs](https://console.groq.com/docs/billing-faqs) describes Developer-tier metered billing after upgrading; historical free-tier zero-price configuration is not appropriate for paid dispatch. Actual account tier/limits need Console evidence; successful model listing verifies authentication only.

## Gemini native diagnostic — 2026-09-14

- Owner's expanded AI Studio screenshots resolve actual Default Gemini Project text-model limits. They support 3.5 Flash Lite 15 RPM/250K TPM/500 RPD, not unlimited usage or available remaining quota. [Official model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) identifies stable model code gemini-3.5-flash-lite; also present in saved model-list metadata. Selection for the small diagnostic is our engineering choice, not a quality claim from Google.
- [Native token-count API](https://ai.google.dev/api/tokens) supports generateContentRequest with system instruction and other steering information. [Native generation reference](https://ai.google.dev/api/generate-content) defines thinkingLevel MINIMAL, maxOutputTokens and prompt/candidate/thought/total usage fields. [Thinking guide](https://ai.google.dev/gemini-api/docs/thinking) documents 3.5 Flash Lite's minimal level and warns about output/thinking truncation. Our runner validates actual usage and stops on invalid outcomes rather than treating the old tokenizer estimate as exact.
- Engineering defaults: fixed two-answer known-fixture scope, exact full-request count before dispatch, conservative lifetime caps, private append-only records, strict no-resend semantics. No OpenAI-compatibility implementation, production adapter, billing guarantee or general cross-provider quality inference. Actual results/tests are in [Gemini report](GEMINI_REPORT.md).
