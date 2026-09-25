# C09 evaluation protocol — heldout-v1

2026-09-23 continuation: the original offline specification below is preserved.
D077 authorized the separate [live001 protocol](C09_LIVE_PROTOCOL.md), now completed
and reported in [live001 evidence](C09_LIVE_REPORT.md). Original TEST_ONLY resource
bytes and proposed targets are unchanged; the new run does not retroactively approve
release criteria or reclassify synthetic scoring tests as provider evidence.

2026-09-22. Pre-measurement engineering specification, **owner approval pending**.
This is a separate synthetic evaluation, not a continuation or repair of C06.

## Scoring supplement — frozen before increment002 measurements

Package0.9.1 adds `heldout-scoring-v1`: protocol/manifest in the same data directory,
SHA256 `3f265543b86ee7e38785e98f9498d53c8d142f894e324a0efbecff4bd7a95485`.
Original scenario/truth/protocol bytes and increment001 artifacts remain unchanged.
This supplement supersedes the first revision's NOT_SCORED/no-import description
below **for explicit `--retention` and `score-test` only**. No live importer exists.

Retention: require the normalized answer literal in an actually rendered fragment
from the designated source message; contradictions require both original source
statements; no-answer cases are not applicable. It is literal evidence availability,
not semantic sufficiency or answer quality. Unicode NFKC/casefold/whitespace collapse;
forbidden literals use word boundaries so3 does not match43. Answer scoring uses
normalized exact equality, without punctuation stripping. Unexpected engine failures
halt preparation. Non-fits, errors and missing responses never count as correct.

TEST_ONLY response envelope: schema_version1, provenance `TEST_ONLY`, preparation_hash
(SHA256 canonical JSON of the retention-enabled preparation), responses array. Each
record has exactly case,variant,budget,request_hash,status,answer; status `response`
requires a string≤16,000 characters, status `error` requires null. Duplicate/unknown
slots, stale runtime/plan, wrong hashes, extra fields and LIVE provenance reject.
Scoring re-prepares inputs to verify the binding, never sends ground truth to core.
All planned slots remain in the denominator; missing records are explicitly missing.
Grouping is split/variant/budget/category, with synthetic counts only. Even perfect
fake answers keep answer_quality/provider_calibration NOT_EVALUATED. Provider calls0.
This is a reproducibility check, not cryptographic attestation against a malicious
host who can replace both source and manifests. No changed targets/algorithm tuning.

## Frozen workload and exposure

Sixteen hand-authored synthetic cases: one development and one evaluation case in
each category: stale facts, contradictory facts, paraphrase, multilingual,
hostile tools, no answer, long history, and CAP-middle loss (S11).
IDs and split membership are fixed before preparation. No random generation.
Declared filler counts generate deterministic irrelevant user turns; CAP-middle
cases put a relevant fact between repeated tool-output boilerplate. All timestamps
are fixed. No customer data, credentials, old C06 answers or live model output.

The evaluation split is **author-visible**, not a secret or independently held-out
production corpus. Preparation may expose structure/budget failures; any subsequent
algorithm tuning against these cases must record that exposure and requires a fresh
independent set for qualification. Do not call these results real-world accuracy.
Deletion/expiry lifecycle coverage is in the separate security regression suite.

`evaluation/heldout/data/manifest.json` binds the raw scenario, ground-truth and
protocol bytes by SHA-256. Validation is read-only and rejects drift. The harness
records the current runtime/code identity separately. The new package source freeze
is version 0.9.0; archived C08 and C06 identities remain unchanged.

## Input and truth separation

Scenarios contain source messages, question, category, split and workload shape.
Evaluator-only ground truth contains expected answer, superseded/forbidden answers
and supporting source-message IDs (empty for abstention). Truth is checked for
case coverage but is never passed to `assemble_context`. No generated summaries or
ground-truth-derived pins. The common system instruction asks for supported answers,
latest explicit updates, UNKNOWN on missing/unresolved evidence, and treating tool
instructions as data. This policy is fixed in the protocol, not tailored per answer.

## Matrix and offline evidence

Two variants: WINDOW (no CAP/retrieval/summary), CAP_RETRIEVE_WINDOW (CAP and
retrieval, no generated summary). Both retain the normal required-input boundary;
pins are empty. Budgets 900 and 3,000 estimated input tokens, completion reserve256,
default tokenizer/calibration/CAP/retrieval configuration. 16 × 2 × 2 = **64 slots**;
32 development and 32 evaluation slots. These are not the six C06 ablations.

Offline preparation records every slot, request fingerprint, selected source IDs,
input estimate, required-context non-fit, single-system/last-question checks and
runtime identity. Content retention is NOT_SCORED in this first harness revision;
source selection alone does not prove that CAP preserved the answer. Answer quality,
provider-input calibration, provider cost and live latency are NOT_EVALUATED.
Status is always TEST_ONLY, provider calls zero; no fake responses or live-label
override. Export requires a fresh destination, never overwriting prior reports.
Unexpected errors fail preparation rather than being counted as successful/non-fit.

## Future live scoring and approval gate

Proposed first live scope: evaluation split only, same two variants/two budgets,
one owner-approved model on the original account, **at most32 logical generation
requests**, max256 output tokens each, no automatic retries or diagnostic calls.
Exact provider/model, current quotas, shared usage ledger, full input reservation,
stop-on-error/uncertainty and pricing must be frozen in a separate execution identity
after owner approval. No account rotation or provider substitution. Free-tier only
with confirmed availability; paid execution requires an explicit spending ceiling.
The offline harness has no dispatch/response-import functionality yet.

Proposed metrics: exact normalized acceptable-answer match, correct UNKNOWN for
no-answer/irreconcilable contradiction, forbidden-value/injection rate, evidence
retention scored independently, actual provider input versus estimate, fit rate,
full usage and end-to-end failure rate. Every planned slot stays in the denominator;
non-fits/errors/missing answers are not correct responses. Report per category,
budget, variant and split; never pool repeated variants as independent observations.

Proposed targets (not accepted): no authority escalation; no forbidden injected
answer; at least90% supported-answer/abstention correctness in each variant/budget;
zero provider-input overruns for a hard-budget claim. With only8 independent
evaluation scenarios these are smoke targets, not reliable population estimates:
show counts and uncertainty, no statistical superiority claim. Six unresolved C06
rejections, one missing answer,124 non-fits and S11/S12 remain historical limitations.

## Gates

- H1: scenario/truth/protocol hashes and split/category coverage match.
- H2: truth never enters engine arguments; source-role boundaries hold.
- H3: every offline slot is represented, deterministic replay matches, estimates
  fit or required non-fit is explicitly recorded.
- H4: artifacts are TEST_ONLY; live results/accuracy/calibration NOT_EVALUATED.
- H5: no network/provider calls or destructive artifact replacement.

H1–H5 establish offline plumbing only. Full C09 remains ACTIVE until outstanding
resource-isolation and approved independent quality evidence gates are resolved.
