# LongMemEval retention and date-mapping review — TEST_ONLY

2026-09-29, D099. Owner approved completing the proposed follow-up work. Steps1–4
(five-case review, retention diagnosis, timestamp mapping experiment and expanded
offline evaluation) are complete. Step5, generated-answer testing, awaits explicit
model/call-budget approval. No model inference, credential access, paid use,
training, upload, core change or default-policy adoption occurred.

## Completed work

- Added `scripts/longmemeval_review.py` and19 synthetic regression tests.
- Diagnosed saved five-case demo using actual emitted WINDOW/RETRIEVED text.
- Implemented an experimental date-aware adapter without changing source messages.
- Saved split and experiment plan before running new assemblies.
- Evaluated35 new development examples, five from each of seven categories.
- Compared four arms at900 and3000tokens on the35 new plus five prior examples:
  **320/320 assemblies completed within estimated budgets**. These are40 source
  examples, not320 independent observations.
- Reserved70 held-out rows, ten per category; **zero assembled or scored**.

Outputs: `output/private/longmemeval-review-001/`, Git-ignored, owner-only parent
directory on this Mac.645files/141,985,852bytes: plan/split/prior diagnosis/report/
HTML index plus per-case input, separate labels and assembly exports. No complete
corpus copy or memory database. Keep derived corpus exports private.

Original download and all32 prior demo files remain unchanged. All ten baseline
wire requests from the prior demo reproduce exactly under the same0.9.6 runtime.
Source SHA-256 remains
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.
Core source freeze remains
`304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.

## 1. Why the larger budget lost complete evidence

The prior five-case demo gives a concrete reproduction:

- Single-session-user: WINDOW expands from8 to41messages. Marked original
  `s0051-m0004`, fully retrieved at900, enters capped WINDOW at3000 and is excluded
  from retrieval by the default policy. Complete marked-message count falls1→0.
- Knowledge-update: WINDOW expands8→43. Marked original `s0039-m0000` likewise
  enters capped WINDOW and leaves retrieval; complete coverage falls2→1.
- Multi-session: one of three marked messages remains complete at both budgets;
  the other two are not selected.
- Temporal: neither of two marked messages is complete; one has a retrieved
  partial chunk and the other is not selected. A partial chunk can still carry
  useful answer evidence; whole-message coverage cannot decide answerability.
- Abstention: no positive annotations in this prior example. No coverage score
  or correct-abstention result can be inferred from that absence.

There are no finalizer drops in these prior baseline runs. Source inspection
confirms `plan_window` takes a contiguous suffix of the capped working history;
`RetrieveLayer` normally excludes every planned WINDOW turn. More input budget
therefore does not imply a superset of retained original evidence.

The existing opt-in recovery is a mitigation, not a universal fix. In the prior
demo it improves one condition and regresses another (six unchanged, two without
annotations). At900 on knowledge-update, recovery admits `s0039-m0010`; retrieved
`s0019-m0004` disappears. Its larger candidate pool competes under the same280token
reserve and BM25 ranking. No monotonic-recall guarantee follows from enabling it.

## 2. Date-aware mapping experiment

Two mapping variants, each with recovery OFF/ON, form a2×2 comparison:

- `baseline`: original demo mapping, recovery OFF.
- `recovery`: same mapping, existing recovery ON.
- `dated`: date-aware mapping, recovery OFF.
- `dated_recovery`: date-aware mapping, recovery ON.

The date mapping appends `|session_date=YYYY-MM-DDTHH:MM` to generated positional
turn IDs. WINDOW serialization and every retrieved chunk carry that ID, so dates
remain visible even when CAP shortens the message. Fixed system guidance explains
that these are source session dates, not event dates, and includes the validated
question date. The original question, message bodies, roles and order are unchanged.
Answers, evidence IDs and `has_answer` labels never enter assembly inputs.

This avoids consuming the message's CAP35 head/tail with a date prefix, but date
metadata still consumes serialized request tokens. Changed IDs can also change
tie-breaking; the comparison measures the entire mapping, not date semantics alone.
Dates have unspecified real-world timezone; UTC remains an internal schema
convention. Source order is not silently sorted into chronological order.

All arms keep CAP35, retrieval reserve280, summary reserve0 and all other core
defaults. No parameter search or outcome-based tuning was performed. Date-aware
mapping is experimental, not automatically adopted for product users.

## 3. Fixed development and held-out split

Seed: `longmemeval-local-review-v1`. Group question IDs with their `_abs` family
and rows sharing answer-source session IDs, then order groups by deterministic
SHA-256. Prior-demo groups are removed first; reserve held-out groups before
selecting development groups. Answer-source IDs serve only split grouping and
never retrieval. Correctness or observed performance does not select examples.

| Partition | Rows | Use |
| --- | --- | --- |
| Previously exposed group | 6 | Five prior demo rows replayed; related sixth reserved, not run |
| Development | 35 | Five per category; all eight conditions executed |
| Held out | 70 | Ten per category; metadata only, no assembly/scoring |
| Unused | 389 | No assembly/scoring in this review |

All500 rows were already structurally validated in the original import. “Held
out” therefore means not used in assembly/score-driven development, not an
independently blind or unpublished corpus.127 source session IDs appear in both
review and held-out histories as background/distractor reuse; no held-out
answer-source session ID appears in review histories in this split. The split
is grouped but not fully session-disjoint. Do not claim independent benchmark
qualification without reviewing these limitations.

Split digest:
`aab5693329fa716acd05621b4d791e508779c6e80471e22e94021d6537229279`.
Plan digest:
`2fac0e0f7b2b32f7aa6b7d9c76384c432a41d146e09ad1d3cabf0f456759123e`.
Plan records source/runtime/helper-script identities, prior-file hashes and arm
settings. Reproduction rejects source mismatch, existing output and prior baseline
drift. Do not overwrite this experiment or tune against its reserved held-out rows.

## 4. Development findings

All35 development cases assembled in each condition, with zero rejects.

| Arm | Complete marked messages,900 | Complete marked messages,3000 |
| --- | --- | --- |
| Baseline | 19/56 | 18/56 |
| Recovery | 19/56 | 19/56 |
| Dated | 19/56 | 18/56 |
| Dated + recovery | 19/56 | 19/56 |

These are **exact complete annotated-message coverage**, not answer accuracy,
answer-span recall or official LongMemEval scores. Thirty-one development examples
have positive annotations and four have none. One abstention example (source
row232) has a positive annotation; it contributes1/1 to these mechanical counts
but must not be interpreted as a correct answer or successful abstention. Removing
the five abstention-category examples for an answerable-only descriptive view
gives18/55 at900 and17/55 at3000 for baseline; recovery gives18/55 at both budgets.
The primary recorded counts above are not retrospectively redefined.

Recovery versus baseline across70 paired development conditions:61 unchanged,
one improved, eight without positive annotations, zero regressions. Dates alone
change no complete-message counts in those70 conditions. This does not establish
semantic equivalence or better temporal answers. Prior-demo regression remains
visible and prevents a blanket “recovery fixes everything” conclusion.

At3000, baseline's56 annotated messages comprise18complete, eight partially
retrieved and30not selected. Further improvement requires diagnosing retrieval
relevance, chunk coverage and task-specific evidence needs, not merely raising
the input limit. Whole-message completeness is deliberately conservative.

Development metadata:11rows have unsorted session dates, three have sessions
after the question, none have duplicate session IDs. These overlap and remain
in the offline denominator. Future-session rows must not count as valid temporal
answer evaluation without a reviewed cutoff policy. No facts were removed to
make results look better.

## Verification

-151scoped adapter/demo/inspection/preflight/recovery regressions pass2.25s.
  Eight brain regressions also pass0.76s:159 focused checks in total.
-19new tests cover grouped splits, holdout isolation, label separation, exact
  coverage/forged slices, source identity, original/prior preservation and date
  visibility under CAP. Synthetic fixtures only; CI needs no downloaded corpus.
-Independent checks of all320 exports: original messages/order/roles/question,
  request hashes, budgets, date metadata on every emitted source and held-out
  exclusion PASS. Plan/split/helper-script hashes and source identity PASS.
-Core and existing frozen evidence unchanged. No repeated full suite or remote CI.
-Dashboard visually inspected at1440×1050 using an isolated local browser, then
  that browser was stopped. Scoped Ruff, brain integrity and whitespace checks PASS.

## Open the review

```sh
open "/Users/nandyyy/Project/Context Engineering/output/private/longmemeval-review-001/index.html"
```

Intentional offline repeat, from the repository root, requires a new directory:

```sh
uv run --locked --offline python -m scripts.longmemeval_review \
  --input /Users/nandyyy/Downloads/longmemeval_s_cleaned.json \
  --prior-demo output/private/longmemeval-demo-001 \
  --output output/private/longmemeval-review-002
```

## 5. Generated-answer step — awaiting approval

Proposed, not executed or authorized: seven development cases (one per category),
date-aware recovery OFF versus ON at3000,14calls maximum to the existing Groq
`openai/gpt-oss-20b` setup,256output tokens/call, no retries or paid use. Source
text would leave this computer for the provider; held-out rows remain unused.
Select cases deterministically without using retention outcomes and reject
future-session cases from temporal evaluation explicitly, not silently. Record
the exact selection and requests before dispatch.

Before any request: obtain owner approval, verify current model availability,
account/free-tier eligibility and shared-ledger quota, freeze a separate live
protocol/request set, and test the new runner with fake transport. Preserve all
historical receipts and exhausted approvals; do not reuse old claims or create a
new quota account. An offline estimated input cap is not a native-provider cap.

Every response must retain its disposition, usage and independent human semantic
review against separate labels. Empty/failed/truncated answers are not retried,
repaired or dropped from denominators. No extra LLM judging calls. This small
author-visible diagnostic would not be official benchmark qualification, final
held-out evaluation, production acceptance or permission to adopt defaults.
