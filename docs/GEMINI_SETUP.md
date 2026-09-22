# Gemini comparison preparation

Updated: 2026-09-14. Status: exact limits resolved; bounded native runner implemented; two-answer diagnostic completed. See [small result report](GEMINI_REPORT.md) for live results, verification and limitations.

The owner requested another free provider and reported ready after the Gemini Free Tier key instructions. This is a separate synthetic-data evaluation, not a replacement for missing Groq C06 results. No paid billing, upgrades, customer-data use or checkpoint acceptance is authorized.

## Key handoff

The owner populated `.env.gemini`; private-file checks pass and Google's official model-list endpoint accepts the key (HTTP 200). Permissions are owner-only (0600). The existing `.env.*` ignore rule covers this file. Do not paste the key into chat or add it to the Groq `.env`: its frozen loader accepts only `GROQ_API_KEY`.

During setup, two read-only model-list GETs were made: initial credential diagnosis, then the tested preflight CLI; no generation or billing operations at that stage. The CLI saved metadata-only `output/gemini-preflight-001.json`: HTTP 200, 41 models advertising generateContent, no further page. Discovery does not establish free inference access. The initial response had no quota headers. Subsequent owner screenshots resolve Free Tier and exact limits below; the earlier JSON remains unchanged. Diagnostic001 later added two native count requests and two generation calls, recorded in the result report. Do not print credentials or place them in command arguments, logs, source, artifacts or the brain.

## Owner limit screenshots — 2026-09-14

- Default Gemini Project is explicitly marked Free tier; Set up billing remains available. Do not request tier confirmation again.
- Earlier partial charts left TPM unknown. The owner's five expanded-table screenshots at 15:38 IST now resolve the exact text-model quotas; no further screenshot/key/tier request is needed.
- The relevant rows below are limits, not a guarantee of remaining quota. Other project traffic may still cause 429 responses.
- Antigravity, embedding, audio, map/search grounding and image quotas are separate. Models with zero generation quota are not usable for this comparison merely because discovery lists them.

| Screenshot model | Requests/minute | Tokens/minute | Requests/day |
|---|---:|---:|---:|
| Gemini 2.5 Flash | 5 | 250,000 | 20 |
| Gemini 2.5 Flash Lite | 10 | 250,000 | 20 |
| Gemini 3.1 Flash Lite | 15 | 250,000 | 500 |
| Gemini 3.5 Flash Lite | 15 | 250,000 | 500 |

Engineering choice before viewing Gemini answers: stable `gemini-3.5-flash-lite`, whose model ID was also present in preflight001 and is documented by [Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite). Higher capacity supports a separate diagnostic; it cannot fill frozen Groq matrix slots. No benchmark acceptance criteria are changed.

## Verified setup tool

`scripts/gemini_preflight.py` requires an explicit private file. Local-only is the default; networking requires an explicit flag and performs exactly one GET to a fixed Google HTTPS endpoint. No proxy inheritance, redirects, retries, generation or billing actions. Responses are bounded to 1 MB and a 30-second total timeout. Output drops descriptions/cursors/error bodies and rejects credential reflection. JSON exports exclusively create new files with owner-only permissions.

```bash
uv run --locked python scripts/gemini_preflight.py --env-file .env.gemini
uv run --locked python scripts/gemini_preflight.py --env-file .env.gemini --allow-network --output output/gemini-preflight-002.json
```

Choose an unused output path; 001 is preserved. The explicit file is authoritative: process GEMINI_API_KEY/GOOGLE_API_KEY variables are not silently substituted. Keys are opaque, printable ASCII header values, including periods; no shell evaluation occurs. An initial ad-hoc Groq-style character check was too restrictive; it was corrected without editing the owner's key.

Verification: 26 new offline preflight cases; combined preflight/free-tier/brain suite has 82 passes. Scoped lint/format pass. Current 0.8.0 and archived C06 0.7.2 source hashes still match their freezes; no core/dependency/version changes. This is setup evidence, not Gemini inference quality or C06 completion.

## Predeclared diagnostic 001 — before live answers

This is a two-answer connectivity/accounting diagnostic, not a new checkpoint, held-out experiment, enterprise qualification or full provider benchmark. The flagship question and Groq outcomes are already known. Do not generalize a single question to accuracy across the 31 facts or select another model after seeing these answers without a separately declared experiment.

- Same synthetic `shard` question; order A1 (WINDOW only), then A5 (all five layers), assembled with current frozen 0.8.0 at the existing 900-token estimated input allowance. Original history, summary, grading and retrieval settings stay unchanged; no ground-truth answers are added to engine/provider inputs.
- Model `gemini-3.5-flash-lite`, temperature 0, one candidate, MINIMAL thinking, no returned thoughts, 512 maximum generated tokens. This output setting differs from Groq's 256/low and is explicitly not a cross-model controlled comparison.
- Native text-only conversion: preserve the single system instruction; keep ordered, explicitly labelled history/retrieval DATA and final question as separate user text parts. Unsupported roles, live tools and additional wire fields fail closed rather than silently changing meaning.
- Native countTokens receives the entire generateContentRequest, including system instruction and generation configuration. Reject counts above 900 before generation. Record actual input/output/thought/total usage independently; countTokens and the old tokenizer estimate are not exact usage guarantees. Unknown/missing/inconsistent usage, unrecognized finish reasons or transport uncertainty stop work. Only STOP with nonempty answer and in-budget usage is scored using the existing exact-alias/one-field-JSON grader; retention is reported separately.
- Single fixed `output/private/gemini-comparison-001/`: immutable plan with core/script/fixture/request hashes, exclusive 0600 intent/receipt records, 0700 run directory, filesystem sync before HTTP, one nonblocking process lock. No alternative directory/model/reset options. Completed results are reused, never resent; any rejected or unfinished request halts the rest of the experiment, including on resume.
- **Lifetime ceiling: two countTokens attempts and two generateContent attempts**, not four per invocation/day. At most two 900-input/512-output generations. The fixed four-attempt cap is stricter than the supplied 15 RPM/500 RPD; bounded 16KB text payloads remain well below 250K TPM. Provider quota errors still halt; this does not account for independent external project traffic or assert provider billing guarantees. Pacific dates are recorded using America/Los_Angeles; there is no daily reset or quota multiplication in this diagnostic.
- Fixed Google HTTPS endpoint, explicit private credential file only, no inherited proxies/redirects/retries, 45-second total deadline per operation, 64KB response limit. No API bodies/errors/headers or reasoning text logged. Only validated synthetic answer and usage are persisted; credential reflection is rejected. No account or billing mutation.

Implementation: `scripts/gemini_comparison.py`, outside the frozen reusable core. It uses the existing optional HTTPX dependency and preparation/grading helpers; no Gemini SDK, dependency, core or Groq runtime changes. This narrow experiment runner is not a general production Gemini adapter or shared multi-run quota service.

```bash
# Freeze/inspect the plan offline first; never reads a key or contacts Google.
uv run --locked python scripts/gemini_comparison.py
# Run only the declared two-pair experiment; repeat invocation never resets its ledger.
uv run --locked python scripts/gemini_comparison.py --allow-live --env-file .env.gemini
```

Do not delete or edit the plan/intent/receipt files to retry failures. A new experiment or broader adapter needs an explicit separately recorded scope with existing account usage carried forward. Preserve `.env`, Groq ledger, archived environment and matrix unchanged. See [Google's native counting reference](https://ai.google.dev/api/tokens), [generation reference](https://ai.google.dev/api/generate-content), and [quota guide](https://ai.google.dev/gemini-api/docs/rate-limits).

## Preserved C06 resume point

Groq continues independently under the unchanged frozen protocol. Use [C06 report](C06_REPORT.md) and [current state](../brain/STATE.md) for the latest validated snapshot, ledger status and exact resume action; do not reuse old batch names or quota dates from Gemini setup history. The foreground completion controller respects the same archived runtime and shared ledger. Gemini diagnostic001 remains complete and separate; no additional Gemini calls, result substitution, background next-day task or C09/C11/C12 gate change.
