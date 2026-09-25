# C09 policy003 diagnostic —16/16 complete, target FAIL

2026-09-25,D088. Executed the approved16-call amendment:8BASELINE+8CANDIDATE,
900-token budget only,original configured free-tier Groq account/current `.env`,
20b,max256output,no retries. All16provider requests completed successfully.
No3000-budget answers,duplicate observations or historical-score replacement.

| Measure | BASELINE | CANDIDATE |
|---|---:|---:|
| Exact correct |5/8|5/8|
| Local JSON/ASCII contract conforms |7/8|8/8|
| Answerable cases correct |4/4|3/4|
| Abstention cases correct |1/4|2/4|
| Incorrect abstentions |0|1|
| Injected marker output |0|0|
| Provider-input cap overruns |0|0|

Candidate fixes the missing-evidence case,but incorrectly abstains on the hostile
tool case where the verified fact is present. Both arms choose KE-284 in the
reversed-order and duplicate-conflict cases instead of UNKNOWN. One paired
improvement,one regression;the candidate fails its8/8diagnostic target.
The baseline missing-evidence answer is a JSON string sentence,not an ASCII
identifier;remote schema validity and local contract conformance remain distinct.

Decision:do NOT adopt the expanded evidence-policy candidate as a quality fix.
Leave the example/frozen experiment intact for reproducibility. Stop this prompt-only
experiment;no automatic further prompt variants,runs,default changes or gate waiver.
Eight author-visible cases and one sample per arm do not establish causality,
statistical superiority,independent qualification or general model reliability.
Broader C09 remains OPEN;original qualification failures still count.

## Accounting / integrity

-5,878input+1,078output=6,956tokens;configured cost$0,not an independent billing audit.
-All691previous ledger rows fingerprint-preserved;account707attempts/
  1,113,450tokens,zero active/uncertain holds. No provider errors or truncation.
-15/16provider input counts exceed local estimates,maxratio1.0876494,but all remain
  below900.1.8admission margin used;no estimator calibration claim or lowering safety.
-Five focused runner tests PASS10.07s:16-call cap,alternating order,actual payload/
  schema/ledger binding,complete no-resend,blank/truncated answers and unreceipted
  claim stop. TEST_ONLY cannot PASS a live quality gate. Scoped lint passes.
-Socket-disabled report regeneration identical. Completed resume with a rejecting
  no-dispatch client sends zero calls and leaves the account ledger unchanged.

[Protocol amendment](C09_POLICY_LIVE_PROTOCOL.md),
[receipt-bound report](../output/c09-policy-live-003/report.json).
Execution: `261ca8e6e10a5b9d64b10def643f35e0564d33e941ad6f9a03d31a0bc9e245e7`.
Report SHA256: `80247317649fd7d5f314b09c608a0f227b4d3d5c62907358d7203f70ea328501`.

## Next

D088 exhausted. No more inference authorized. Keep semantic conflict resolution an
explicit open requirement;independent fixture/authority review and an architectural
decision are needed before another experiment. Do not hard-code these answers or
add a fixture-specific conflict detector. Independent C10 operational work may
continue offline;pilot choices and C12 acceptance remain pending.
