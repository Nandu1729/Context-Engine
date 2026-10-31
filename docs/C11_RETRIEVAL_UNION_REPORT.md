# C11 — isolated retrieval-union experiment

2026-10-02. Completed one fixed offline experiment;candidate NOT adopted.
Core0.9.6, all provider results and70held-out cases remain unchanged.

## Implementation and verification

The research-only `scripts/retrieval_union_candidate.py` merges overlapping source
slices instead of discarding all novel overlapping text. Exact original offsets,
source validation, existing ranking, WINDOW eligibility, top-k and full-block
budget checks remain. Rejected merges leave prior selection intact. No new
dependency, vector index, model, stopword list or answer-aware retrieval.

This script uses process-local substitution in a single-threaded offline process;
it is NOT a service integration or production-safe concurrent extension. Candidate
configuration fingerprints include separate script/protocol identity. Frozen
runner/protocol and core source files were not edited.

137 focused tests PASS0.75s:19new synthetic candidate tests plus existing retrieval,
layer and pipeline tests. Tests cover exact novel spans, overlap bridges, no gap
filling, containment, distinct messages, Unicode, invalid/revised/deleted sources,
index parity, zero/tight budgets, original/required-content preservation,
cancellation checkpoints, exception restoration and exclusive output writes.
Scoped Ruff lint/format PASS. Initial3 tests failed because the public tokenizer
cache was missing; vocabulary initialization before socket denial fixed the setup.
No inference or credentials were involved in that asset download.

## Fixed development comparison

The [protocol](C11_RETRIEVAL_UNION_PROTOCOL.md) was written before execution.
Exactly35 existing development rows ×2 budgets =70candidate assemblies;all succeed.
Date-aware recovery-OFF baseline exports are read-only. Labels enter only after
assembly for measurement. No baseline reruns, prompt tuning or provider calls.

| Measure |900 estimated-token budget|3000 estimated-token budget|
| --- | ---: | ---: |
| Candidate assemblies |35/35|35/35|
| Baseline complete marked messages |19/56|18/56|
| Candidate complete marked messages |22/56|22/56|
| Cases improving complete-message count |3|4|
| Cases regressing complete-message count |0|0|
| Changed request payloads |7|8|
| Aggregate input-token change across35cases |+50|+100|
| Largest candidate request |876|2992|
| Finalizer drops |0|0|
| Median candidate assembly seconds |0.6235|0.6557|

Whole-message retention is NOT answer accuracy. Latency includes local assembly
and candidate identity bookkeeping;baseline timing was not repeated,so no speedup
or CPU-cost reduction is claimed. Summary/provider/billing costs are not measured.

Improved source rows:385,390,452 at900;105,385,390,452 at3000.
For the known row454 failure, both budgets now retain[0,920),including the requested
count at[793,804). The original span selection omitted it. This fixes that specific
context omission only;no new model answer was generated or graded.

## Tradeoffs found during recheck

Post-hoc interval comparison confirms WINDOW payloads identical in all70conditions.
However, some previously retrieved text is displaced in10conditions (five rows at
both budgets):385 loses223characters,390 loses360,454 loses280,456 loses28 and495
loses360. Only454/495 lose portions of annotated source messages. In454 the missing
count is now included while a later tail is omitted. In495 the reference name is
still present;an earlier portion of the source is displaced. These two source checks
are post-hoc development diagnostics,not proof that all displaced text is harmless.

Therefore “no complete-message regression” must not be reported as “no evidence
loss” or “no quality regression.” Reject default adoption pending independent
quality and source-span evaluation. No parameter sweep was performed to hide losses.

## Provenance and decision

- Private plan/results: `output/private/retrieval-union-001/plan.json` and `report.json`.
- Plan SHA256: `1da539ed7d75ddcff4be0f1b1dc5c1a932a3291a7fa77a5ed14560bf5f058df8`.
- Candidate script SHA256: `4154108879470479092c93c48bf1c02ac26b1ea36ca809f4b92530b2220f3da4`.
- Protocol SHA256: `af33e83280b21a819fb82e6b69d0bf68b828c61a44c21d0cfcc2b17ef822f2e6`.
- Report SHA256: `cbca92fb5eab5e36335719e2e268ee2e4e2a2ee88d8d5cce47e99993a6c97d7a`.
- Input hashes checked before/after;network-disabled D100 report reconstruction
  still matches. Original dataset/selected exports/runner/runtime and blank owner
  worksheet unchanged. Ledger721attempts/1,151,595tokens,zero new calls/writes.

Decision: keep the isolated prototype as evidence,not a production repair. C11's
experiment task is complete;C11 checkpoint remains ACTIVE because paired accepted
quality and total cost per useful answer are unqualified. C09 quality remains open.
Next requires deciding local-demo versus production scope and,for live validation,
a separate fixed model/call/spend budget. Old failures and targets stay unchanged.
