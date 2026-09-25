# C09 qualification live002 — D080 bounded execution

Owner answers "continue" to the explicit maximum32 new Groq requests proposal on
2026-09-23. Authorizes this run on the original account/current .env,not a new
account,paid usage,retries,default-policy change or checkpoint acceptance. The
author-visible cases and predeclared targets in C09_QUALIFICATION_PROTOCOL remain
unchanged;execution approval is not independent review or release acceptance.

Run frozen qualification002-r1 exactly:32 planned slots,eight cases,two budgets,
CONTROL then PRIMARY. Source0.9.2 unchanged;manifest/preparation reproduced before
init. Model openai/gpt-oss-20b,temperature0,reasoning low,max256 output,one request
per slot,no retries. Strict JSON prompt instructions,not provider schema mode.
Truth never enters generation. Actual usage/response hashes bind immutable receipts
to the original shared ledger;all655 prior attempt rows remain hash-identical.

New external wrapper `scripts/c09_qualification_live.py` imports the byte-verified
old runner into a separate module instance. Reuses exclusive claims,process locking,
resume guard,request-key/receipt/ledger validation,one-attempt client,full-usage
quota accounting and sanitized CLI. Overrides only run identity,qualification
request reconstruction,admission margin and exact-answer reporting. No old script,
protocol,claim,receipt,archive or key file edits. Run-private directory:
`output/private/c09-qualification-live-002`. Frozen execution manifest binds wrapper,
parent,protocol,preparation,runtime,generation,provider dependencies,ledger baseline.

Admission checks use1.8×estimated input+256,then ledger/client retain their original
estimate and actual full usage. This margin covers historical observed ratios,
not a guarantee of future calibration. Minute waits≤30seconds each,≤300seconds per
slot;daily quota,uncertain usage,provider error,truncation,unreceipted claim or
freeze drift stop dispatch. No unsuccessful slot is retried. Quality misses are
scored without early-stopping the planned matrix;actual cap overruns are disclosed.
No extra quota-probe inference. Key loaded only at live execution from current.env;
inherited GROQ_API_KEY removed. Prices remain owner-confirmed free-tier configuration,
not independently verified billing. Stop if account configuration disagrees.

Score parsed exact strings without repair,using the frozen AnswerContract and
targets. Both conditions keep8-case denominators at each budget. PRIMARY gate
requires8/8 correctness/conformance,2/2 correct abstentions,zero forbidden answers,
errors,truncation or input-cap overruns. CONTROL stays diagnostic;publish all paired
deltas. Partial runs remain INCOMPLETE. TEST_ONLY manifests never claim measured
quality. Missing and uncertain slots are not successes. Old live0018/32 unchanged.

Before dispatch:targeted fake-transport tests,freeze manifest,read-only quota check.
After dispatch:socket-disabled report reproduction,baseline-hash inspection,short
owner report and updated brain. No redundant full-suite rerun;owner requests speed.

```sh
.venv/bin/python scripts/c09_qualification_live.py init
.venv/bin/python scripts/c09_qualification_live.py status
.venv/bin/python scripts/c09_qualification_live.py run --allow-live
.venv/bin/python scripts/c09_qualification_live.py report --output output/c09-qualification-live-002
```
