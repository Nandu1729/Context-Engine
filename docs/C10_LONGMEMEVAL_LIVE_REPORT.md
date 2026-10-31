# LongMemEval bounded live development comparison

Later D102: [saved-answer recheck](C10_LONGMEMEVAL_RECHECK_REPORT.md) records a
separate assistant assessment and confirmed overlap-suppression diagnosis.
Original results below and private report fields remain unchanged; owner review pending.

2026-09-29, D100. Execution complete:14/14authorized attempts;approval exhausted.
The owner approved14 Groq `openai/gpt-oss-20b` requests, seven development examples
with date-aware recovery OFF/ON,3000estimated input/max256completion tokens.
No retry, account/model substitution, paid allowance or held-out execution.

## Frozen identity and verification

- Execution ID: `16e3ffce752afc2e757563fba56a0cf2a578e94a5596eb49712194a75759b3da`.
- Runner SHA256: `9831dc1b4761ea4c51f5c408c2794ee33c7080e4283fd93b33b6794aa7995ec0`.
- Protocol SHA256: `cde4db016da83ae52214b94275fcc89a2d2e28589648b150e5dc57e252f9873a`.
- Unchanged package0.9.6/source freeze
  `304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.
- Shared-account baseline707attempts/1,113,450charged tokens/no active holds.
- Before initialization:146targeted tests PASS2.78s,including23new portable runner
  checks;Ruff PASS. Real authenticated read-only model-list preflight lists the
  approved exact model active. This is not a billing attestation.

Frozen [protocol](C10_LONGMEMEVAL_LIVE_PROTOCOL.md) specifies selection, alternating
order, fixed payloads, accounting, stop rules and limitations. Runner/protocol must
not change under this execution identity. Historical experiments remain separate.

## Selection, not cherry-picking

One eligible development example/category is selected by fixed question-ID hash,
excluding only future-session cases, with no answer/coverage-based ranking. The
70held-out examples remain unassembled/unscored. Source row indices are zero-based.

| Category | Source row | OFF estimated input | ON estimated input | Identical wire |
| --- | ---: | ---: | ---: | --- |
| Abstention |232|2940|2940|Yes|
| Knowledge update |390|2888|2888|Yes|
| Multi-session |106|2915|2885|No|
| Single-session assistant |454|2973|2973|Yes|
| Single-session preference |156|2941|2941|Yes|
| Single-session user |49|2939|2939|Yes|
| Temporal reasoning |262|2987|2974|No|

Five identical pairs measure repeated responses, not recovery effects. Only two
examples have different payloads. Seven examples cannot establish population
accuracy. The selected abstention row232 has a positive source message annotation;
this previously recorded dataset caveat is not silently repaired or excluded.

## Data handling

The original `/Users/nandyyy/Downloads/longmemeval_s_cleaned.json` is read-only.
Only14bounded assembled requests are authorized for Groq;no whole corpus upload,
training or real customer data. Original messages and question wording,prior
320assembly exports,split,labels,core and default recovery behavior stay unchanged.
Private run claims/receipts live under `output/private/longmemeval-live-001/`.
No raw provider bodies,reasoning text,credentials or headers are stored.

## Results and next gate

| Measure | Recovery OFF | Recovery ON | Total |
| --- | ---: | ---: | ---: |
| Planned / attempted |7|7|14|
| Normal completion with nonempty answer |6|6|12|
| Truncated at completion limit |1|1|2|
| Provider errors / missing receipts |0|0|0|
| Native input-cap overruns |0|0|0|
| Literal reference equality |0|0|0|

Literal equality is not semantic accuracy: the successful abstention and location
responses paraphrase their references. No official judge or additional model calls
were used. The report deliberately leaves semantic review PENDING.

Actual usage:36,686input+1,459output=38,145tokens;zero configured cost,not an upstream
billing attestation. Shared account now721attempts/1,151,595charged tokens,zero active
holds/unknown usage. All707historical row fingerprints remain unchanged. Both
preference responses reached256completion tokens and are preserved as truncated;
no limit increase or retry occurred.

Preliminary assistant inspection found the multi-session jewelry count and
assistant-history study sample-size answers abstained despite answerable dataset
references. The multi-session request selected none of its five marked messages;
the study request retained only partial chunks. These are diagnostic observations,
not independent grading or proof that whole-message coverage equals answer recall.
The preference response was generic and truncated;more output alone is not an
established fix for missing personalization. Do not adopt recovery from this run.

## Final integrity and owner handoff

- Reconstructed all14selected inputs/labels from the unchanged500row source:
  exact matches,network disabled,no new assemblies. All32prior demo files match
  their saved hashes. Selected review exports and core/protocol identity verified.
- Completed-run resume with network disabled made zero additional calls and left
  all721ledger rows unchanged.14claims/14receipts bind to actual settled usage.
-146targeted tests PASS2.78s plus8brain checks PASS0.85s before final documentation;
  no full suite,remote CI,commit/push,deployment or default/core changes.
- Results: `output/private/longmemeval-live-report-001/report.json`.
- Editable owner worksheet: `output/private/longmemeval-live-report-001/manual-review.md`.
  Contains seven questions/references and both responses,with rating/reason fields.
  Keep private;edit only the worksheet,not frozen evidence or reference answers.

Owner requested less assistant usage while continuing. Next:owner reviews the
worksheet (about15–25minutes),marks Correct/Partly correct/Incorrect/Unclear and a
short reason,then returns it. Assistant work should focus on disputed examples
and scoped offline diagnosis,not redundant suites or further prompt experiments.
No remaining D100calls;70held-out still unassembled/unscored. Independent semantic
review and broader C09/C10/C12 acceptance remain open.
