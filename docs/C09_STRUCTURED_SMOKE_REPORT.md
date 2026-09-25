# C09 structured smoke001 — completed, qualification still open

2026-09-24,D084. Exactly2 approved Groq20b calls completed on the original
configured free-tier account/current `.env`,max256 output each,no retries.
Opt-in strict JSON schema and schema-aware assembly/admission were used;core0.9.2,
historical scripts,cases and scores were not changed.

| Synthetic case | Valid answer JSON | Exact correctness | Result |
|---|---|---|---|
| q2-long / PRIMARY /900 | Yes | Correct | `snap-782` |
| q2-conflict / CONTROL /900 | Yes | Incorrect | `OT-417`,expected `UNKNOWN` |

Both requests retained their required source evidence. Schema accounting estimated
844/486 input tokens;provider reported787/469. Output54/46 tokens,including34/26
reasoning tokens. No empty final answers,truncation,API errors or input-cap overruns.
Raw reasoning/body text was not saved;response-shape metadata is hash-bound.

This demonstrates schema acceptance and2/2 formatting compliance in this smoke,
NOT a general empty-answer fix or accuracy improvement. Conflict handling still
fails despite both source facts being retained. Schema overhead may change context
selection;these are not identical prior payloads and do not replace old failures.
The C09 strict qualification gate remains failed;no checkpoint owner acceptance.

## Accounting and verification

-1,356 additional tokens;configured cost$0 (not an independently verified invoice).
-All689 historical ledger rows preserved byte-fingerprint-identically;
 account now691attempts/1,106,494tokens,zero active/uncertain holds.
-35 focused tests PASS9.57s:3 new smoke cases plus32 integration/boundary checks.
 Fake transport verifies actual strict payload,matched request identity/settlement,
 two-call cap,no resend,blank/malformed local rejection and preserved usage.
-Socket-disabled report regeneration identical;ruff checks pass.
-No full-suite rerun;historical full-suite results are not reasserted for this change.

[Frozen protocol](C09_STRUCTURED_SMOKE_PROTOCOL.md) and
[receipt-bound report](../output/c09-structured-smoke-001/report.json).

Execution: `eac0e34b4a87bb7e86cec8d4a5f6ac6aa567c5959713d022f6c36dc058fc20c5`.
Report SHA256: `d3ee387453437fc9904166e0da359e287f8a952c7a5048287a44c227b46580a8`.

## Next

D084 exhausted;no more calls authorized. Diagnose contradiction/abstention behavior
offline against retained context and instructions,without editing frozen fixtures or
post-hoc scores. Any candidate repair needs fresh qualification under a separately
approved budget;do not rerun32 cases blindly or adopt structured mode by default.
