# C09 qualification live002 — completed, target not met

2026-09-23. **32/32 requests completed;no further calls remain under D080.**
Package0.9.2 and qualification002-r1 cases/targets unchanged. Original account,
current.env,Groq20b,max256 output,one attempt per slot,no paid usage configured.
C09 remains ACTIVE,not owner-accepted;C10 remains planned.

## Results

| Input cap | Default CONTROL correct | Recovery PRIMARY correct | PRIMARY conformance |
|---|---|---|---|
|900|5/8|7/8|7/8|
|3000|6/8|7/8|7/8|

PRIMARY14/16(87.5%),CONTROL11/16(68.75%);25/32 total exact answers.
The predeclared PRIMARY target8/8 at **each** budget fails. Four paired improvements
and one regression;one sample/category and repeated conditions are not independent
population observations. Do not directly compare with old live0018/32 as an A/B
result:cases,prompts and engine versions differ. Old score remains unchanged.

-27/32 responses conform to the strict JSON answer contract.
- Five receipts have empty answer content despite provider `stop` success:
  conflict/CONTROL at900 and3000;long-history/CONTROL at900;long-history/PRIMARY
  at900 and3000. Output usage47–63tokens,below256;recorded evidence does not support
  blaming output-limit exhaustion. Root cause is unresolved;no raw-response
  reconstruction,answer substitution or retry performed.
- Two other misses are CONTROL's UNKNOWN for the missing middle fact at both
  budgets. PRIMARY recovers and answers that fact correctly.
- PRIMARY correct abstention2/2 per budget;CONTROL1/2 because conflict answers are
  empty. Wrong abstention:CONTROL1 per budget,PRIMARY0.
- Evidence retention:PRIMARY7/7 versusCONTROL6/7 at both caps. Retention is not
  automatically answer correctness:PRIMARY's long-history evidence survived but
  the answer was empty.
- Zero provider errors,truncations,forbidden outputs,input-cap overruns or unresolved
  usage. Four inputs exceeded the tokenizer estimate;max actual/estimate1.127660.
  This is not a universal hard-budget or injection-safety guarantee.

Usage:22,838input+1,636output=**24,474tokens**;configured cost$0,not independent billing
verification. Shared account687attempts/1,103,796tokens,zero active/uncertain holds.
All655 prior ledger rows retain their exact hashes. Max measured per-call1.231s,
excluding intentional minute-quota waits;no throughput/SLO claim.

## Verification and reproducibility

[Saved receipt-bound report](../output/c09-qualification-live-002/report.json) is
byte-identical when regenerated with sockets disabled. SHA256:
`813e06da87d5b066f05eaa80a219521b04f35d89e399c55a6de9c1c9fe85f746`.
Execution ID:`e90024ddf48e25bed0c21415cbb3d4f5ed529240defb0e8f1d013800d8d3f5be`.
Runner SHA256:`6b1d8df257d8cac21adb758018c5e958821d2d216e119e2023cd1781c48b0a9f`.
Live protocol SHA256:`5ee422aec94fc1fa7ea65ecac52333ce344d802e692e2093ffb3f81589c47d92`.

Focused fake-transport suite24checks covers32-call cap/no resend,immutable claims,
receipt/account binding,uncertainty,error/truncation stops,quota pacing,baseline
preservation,truth isolation and strict scoring. Initial run22passed/two failures:
one stale fixture identifier corrected;one freeze guard correctly stopped because
the wrapper was edited during that offline test. Final failed-test rerun2PASS
in17.46s and ground-truth/drift subset6PASS in0.88s. No live run started before these
checks passed. No engine edits or redundant full-suite rerun. Ruff passes.

Socket-disabled replay must preload the Python SSL/asyncio imports before replacing
socket constructors;the first verification command patched sockets too early and
failed during SSL class import,not evidence validation. Corrected offline replay
passes;no provider call was made by either command.

Original live001 runner/protocol,all old run artifacts and C06/Gemini records were
not edited. New wrapper reuses their byte-verified safety functions in an isolated
module instance with its own run identity. No running process remains after exit0.

## Next step

Diagnose empty-answer handling from saved receipts and local adapter code **offline**;
preserve all five failures. Any further inference needs a new bounded authorization.
Do not tune/regrade these frozen cases or infer default-recovery adoption. The
author-visible synthetic comparison is not independently reviewed real-world
qualification. Owner acceptance remains separate.

Read-only status/replay (unchanged0.9.2 environment):

```sh
.venv/bin/python scripts/c09_qualification_live.py status
```

Never reset claims or run `init` again. Preserve the0.9.2 runtime before future
package changes;source drift must fail closed rather than rebase this evidence.
