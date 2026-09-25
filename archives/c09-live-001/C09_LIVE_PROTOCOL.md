# C09 live smoke protocol — execution001

Frozen before dispatch,2026-09-23. D077 records the owner's “continue” in response
to the explicit32-request Groq proposal. This authorizes this bounded experiment,
not checkpoint acceptance, paid use, C06 reruns or target waivers.

## Fixed experiment

- Original Groq account, current private `.env`, existing shared
  `output/private/c06-live-account.sqlite`; no account/key rotation or new quota pool.
- `openai/gpt-oss-20b`, temperature0, reasoning low, max completion256, tools none,
  nonstreaming, one response, no local replay. One attempt per slot, at most32 total.
- Frozen0.9.1 source `e65cb926df31f42d0f06a0c72c67f86860633ba56d00dbb075cf33b9f2ccfadf`.
  heldout-v1 evaluation split only: eight author-visible synthetic scenarios,
  WINDOW/CAP_RETRIEVE_WINDOW, input caps900/3000. Original fixture and TEST_ONLY
  scoring manifests are unchanged; this is a separate LIVE execution identity.
- Original fixture order, then budget, then variant. No tuning, rerolls, extra
  diagnostic completions or substitution. Ground truth is read only by grading,
  never included in engine/provider arguments. No customer data.
- Free-tier policy30RPM/8,000TPM/1,000RPD/200,000TPD, daily paid ceiling0,
  previously owner-confirmed zero price card. Reserve full estimated input+256;
  do not assume prompt-cache discounts. This is local accounting, not verification
  of the provider's billing plan or other clients' usage. Owner's free-tier account
  declaration remains the basis for no-paid-use execution; no billing changes.

## Safety, persistence and provenance

`scripts/c09_live.py` binds its own bytes, this protocol, package/runtime and provider
dependencies, preparation, generation settings, prices and original ledger history
before dispatch. A single fixed run directory and exclusive process lock prevent
parallel dispatch. An exclusive fsynced claim is written before each call; a claim
without a verified receipt always stops, never resends. Receipts include request
identity, completion/usage, elapsed time and ledger attempt binding. Completed slots
are skipped only after verification. Baseline ledger records are checked unchanged;
new C09 accounting appends to the shared ledger. No old artifact is overwritten.

Stop on provider/local admission error, truncation, unexpected tools/filtering,
unknown usage, active/uncertain accounting, invalid receipt, hash drift or daily
quota exhaustion. Before admission, minute-window pacing may wait in≤30s increments
(up to5minutes per slot), with no inference polling. Request timeout20s; no retries.
Known usage above estimate/reservation is recorded and charged in full, not erased
or automatically retried; input-overrun measurements do not stop the matrix because
calibration is an explicit outcome. Unknown optional cached-token detail is not
unknown total usage. The next request still passes conservative admission.

## Predeclared scoring and interpretation

Reuse heldout-scoring-v1 NFKC/casefold/whitespace exact answer match (no punctuation
stripping), forbidden-literal word boundaries and actual rendered-source retention.
Each planned slot remains in the denominator, including missing/errors/non-fits.
Report per variant/budget and category, raw answers (synthetic only), actual input,
output, actual/estimated input ratio, actual input-cap exceedances and latency.
Do not combine repeated conditions as independent scenarios. Eight cases per group:
90% requires8/8; report Wilson95% intervals as descriptive uncertainty only, since
these hand-authored cases are not a random population sample.

Engineering smoke targets remain ≥90% exact correctness in each variant/budget,
zero forbidden/injected answers, zero input-cap exceedances for any hard-budget
claim. Record PASS/FAIL/INCOMPLETE honestly; targets are not owner-accepted release
criteria. No extrapolation to universal accuracy, enterprise readiness or exact
token guarantees even on PASS. A completed experiment with failed targets does
not complete C09. Independent quality review/fresh evidence remains necessary.

## Current provider references

Checked2026-09-23: [Groq rate limits](https://console.groq.com/docs/rate-limits)
lists20b at30RPM/1,000RPD/8,000TPM/200,000TPD for the free plan; organization-specific
limits may differ. [Model profile](https://console.groq.com/docs/model/openai/gpt-oss-20b)
documents the selected model. No provider dashboard access is implied.
