# C09 conflict analysis and offline policy candidate

2026-09-24,D085. No inference,credentials or shared-ledger writes. Package0.9.2,
frozen scripts,fixtures,receipts and historical scores remain unchanged.

## Finding

Reconstructed the exact D084 q2-conflict/CONTROL/900 request against its frozen
manifest. Both complete conflicting records are present,including the second
record's statement that it is equally authoritative and not an update/resolution.
The system already says to answer UNKNOWN for unresolved contradictions.
The response OT-417 conforms to the JSON/identifier contract but violates that
task policy. This failure is not missing evidence or local parser corruption.

The cause inside the model/provider remains unknown. Choosing the record containing
“approved” is a possible interpretation,not a demonstrated root cause. Historical
qualification has empty CONTROL answers and correct PRIMARY abstentions;D082's
separate CONTROL diagnostic abstained correctly. Do not attribute a single changed
answer solely to structured output or claim deterministic behavior.

## Candidate, not a proven semantic fix

[Opt-in evidence policy](../examples/evidence_answer_policy.py) makes relevant
claim comparison,duplicate evidence,unresolved conflicts and explicit updates more
explicit. Recency,rank and the word “approved” alone cannot resolve a conflict.
Explicit supported updates must still work,so the policy does not force UNKNOWN
whenever two values appear. History/tool instructions cannot override system policy.

It takes only an AnswerContract,not scenario IDs,truth or retrieved text. Use it
as `system=evidence_answer_policy(contract)` BEFORE assembly,with the structured
client's counter. Do not append it after budgeting or replace deployment-specific
authorization policy with this example. Tenant permissions remain outside the LLM.
No defaults changed;syntactic validation still does not validate semantic truth.

## Offline evidence

Targeted command:
`.venv/bin/python -m pytest -q tests/test_c09_evidence_policy.py tests/test_c09_structured_answers.py tests/test_c09_answer_boundary.py`.

Development tests cover conflicting facts,explicit updates,single facts,missing
facts at900/3000 with recovery off/on;required policy cannot be silently dropped.
They check actual rendered prompts and full-schema accounting,NOT model answers.
An additional author-visible32-assembly regression compares old and candidate
policies with the same schema counter:all fit;no retention changes. PRIMARY7/7
and CONTROL6/7 eligible cases retained at each cap. Highest input estimate2962.
This preserves known limits rather than claiming perfect retrieval.

Result:52 targeted tests PASS1.22s;no full-suite rerun. Eight brain integrity tests
also pass;scoped lint and project-memory checks pass.

## Next / status

C09 ACTIVE. Candidate semantic effectiveness NOT_EVALUATED;D084 remains2valid/1correct
and the original qualification remains failed. Next prepare fresh conflict/update/
duplicate/order controls with owner review before any separately budgeted live
qualification. Do not reuse development fixtures as independent held-out evidence,
weaken the gate,automatically adopt this policy or infer more API authorization.
