# D105 — one-request application answer test

2026-10-03. Owner explicitly approved one request after the proposed row49test:
existing Groq account,previous model `openai/gpt-oss-20b`,max256output tokens,
no retries or paid usage. Only the prepared public dataset context may be sent.
This supersedes exhausted budgets only for this single test,not another benchmark.

## Fixed input and limits

Use existing `longmemeval-review-001/row-049/input-baseline.json`,SHA256
`4798dc0fdb5174fb68efee364142c853fdb7ebcb207911e7bb74a9548f567fb5`.
Reassemble unchanged0.9.6 offline and require exact saved baseline900wire equality.
Budget900,CAP35,recovery OFF,summary reserve0,estimated892input tokens.
Keep original question/system/history,without answer schema or prompt edits.
Labels are not loaded by preparation or dispatch. Original source SHA256 remains
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.
No held-out cases or additional inputs are authorized.

Use a separately frozen runner `scripts/sample_answer.py` and private evidence
`output/private/sample-answer-001`. Freeze runner/protocol/helper/runtime/dependency,
input/assembly/split/label hashes and all existing account attempt hashes before
dispatch. Reuse only unchanged safety utilities from longmemeval_live;do not invoke
its historical init/run/dispatch/report or modify its identity/files.

Original `.env`,confirmed free-tier configuration and shared c06account ledger only.
Temperature0,reasoning low,include_reasoning=false,max_completion_tokens256,
replay OFF,max_attempts1,attempt20s,total25s. Exact active model must appear in a
read-only model-list GET before initialization. Local configured zero-cost policy
is required;the model endpoint does not attest upstream billing or quota balance.
No account/model fallback or quota adjustment.

Conservative local admission:ceil(892×1.8)+256=1862tokens. Require room under
existing30RPM/8000TPM/1000RPD/200000TPD policy;no automatic waiting or retries.
Refuse active/unknown-cost attempts or unexplained account traffic. Unchanged
ProviderClient reserves/settles actual usage in the original shared ledger.

Exclusive run lock and durable exclusive claim before dispatch. At most one claim
and one provider attempt. A claim without receipt is uncertain and never resent.
Completed or failed reruns make zero calls. Preserve errors,empty/truncated results
and native-token overruns;do not repair answers,raise limits or clear claims/locks.
No new requests after this authorization is consumed.

## Reporting

Store the raw returned answer privately with usage/status and ledger-bound receipt.
Public terminal status contains no content unless --show-answer is explicitly used.
Compare with the separate local reference only after dispatch,as an assistant
review—not an official score,independent review or checkpoint acceptance.
Actual token usage/configured cost are not a provider billing attestation.
One known development case does not establish general accuracy or enterprise readiness.
