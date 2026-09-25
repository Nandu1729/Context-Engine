# C09 live001 report — completed experiment, failed strict quality gate

2026-09-23. D077 bounded run completed: **32/32 Groq requests**, original account,
`openai/gpt-oss-20b`, max256 completion tokens, one attempt each. No retries,
provider errors, truncations, unknown usage or extra diagnostic inference.
**C09 remains ACTIVE; this is not owner acceptance or production qualification.**

## Results

| Condition | Exact answers | Source retention | Input-cap overruns | Forbidden answers |
|---|---:|---:|---:|---:|
| WINDOW /900 |2/8 |0/7 |0/8 |0/8 |
| WINDOW /3000 |2/8 |6/7 |0/8 |0/8 |
| CAP_RETRIEVE_WINDOW /900 |2/8 |6/7 |0/8 |0/8 |
| CAP_RETRIEVE_WINDOW /3000 |2/8 |6/7 |0/8 |0/8 |

All four groups fail the predeclared90% exact-match engineering smoke target.
Each contains the same eight author-visible synthetic scenarios, not independent
samples of production traffic. Descriptive Wilson95% interval for2/8 is7.15–59.07%;
this is not population inference for a hand-authored corpus. One no-answer case per
condition is excluded from literal-retention denominators, not answer denominators.
Eight exact matches are correct UNKNOWN abstentions (contradiction/no-answer).

Post-hoc failure diagnosis **does not change the frozen scores**:

-12 outputs contain the expected answer literal but add prose/Markdown. Example:
  expected `Indigo`; actual `The current cedar on‑call team is **Indigo**.`
-3 hostile-tool outputs use `shard‑84` with U+2011 nonbreaking hyphen instead of
  the exact identifier `shard-84` (ASCII). Treating identifiers as merely visually
  equivalent can break downstream lookups; these are not silently normalized away.
-9 outputs abstain UNKNOWN with the needed evidence absent from the assembled
  context: six WINDOW/900 positive-answer cases, WINDOW/3000 long-history, and
  CAP_RETRIEVE_WINDOW's middle-fact case at both budgets. Original source data is
  preserved; missing working-context evidence is a real retention limitation.

Thus8/32 is **strict answer-contract success**, not proof that24 answers asserted
wrong facts. The generic instruction “Give only the supported answer” did not
reliably produce machine-exact values. Extra wording, changed identifier glyphs and
missing evidence are different problems and need separate fixes/measurements.

No injected/forbidden answer was observed in these32 slots. This narrow result does
not establish universal injection resistance or replace deterministic authorization.
Provider input exceeded the local estimate in3 slots, max ratio **1.708333**, but
stayed within the requested900/3000 input cap in all32. S12 remains unresolved as
a universal hard-budget guarantee; zero cap overruns here does not erase C06's12.

## Usage and accounting

27,402 provider input +1,151 output = **28,553 tokens**. Configured cost$0 under the
owner-confirmed free-tier profile; this is not an independently checked billing
statement. The original shared account is now655 attempts/1,079,322 known tokens,
zero active/uncertain holds. All623 pre-C09 attempt records match their frozen
hashes. New usage was appended, never used to reset an account quota.

Median per-call elapsed0.512s, max1.208s, including local admission/settlement but
excluding minute-quota pacing. These are local observations, not service latency SLOs.
No runner remains active. The32-call authorization is fully consumed; no further
inference is authorized by this completed run.

## Reproducibility and safeguards

- [Frozen protocol](C09_LIVE_PROTOCOL.md); external `scripts/c09_live.py` uses
  fsynced exclusive pre-dispatch claims, single-run locking, one-attempt provider
  configuration, receipt-to-ledger checks and full32-slot denominators. An unreceipted
  claim stops instead of resending. No `.env` or key material is exported.
- Execution `5e6d7cc10f8865d4916b85322a3f7c0bcc82c91e79c2a7c92fba4d1304fa974a`.
  RunnerSHA256 `d7839652e66d6c4c52dc3da398538fd2d2bf6b48c3cde6e1a9adf2a35dca57d9`;
  protocolSHA256 `801791e0e87eb5e8f0571846def908b59103eb9f02a4568c19fafec038c4b4d5`.
- Frozen core0.9.1 hash
  `e65cb926df31f42d0f06a0c72c67f86860633ba56d00dbb075cf33b9f2ccfadf`, archived in
  `archives/c09-offline-003/`. Source, wheel and embedded freeze match. This runner
  is external to core; old TEST_ONLY protocols/artifacts were not relabeled LIVE.
- [Full report and synthetic receipts](../output/c09-live-001/report.json) reproduce
  byte-for-byte in [socket-disabled replay](../output/c09-live-001-replay/report.json).
  Report includes runtime/dependency/fixture identity, per-category/condition rows,
  requests' hashes, ledger-bound completions/usage, latency and all denominators.
-913 local regression tests PASS in152.80s,2 existing dependency deprecation
  warnings.22 new live-runner tests (all offline) cover32-call cap/resume, quota waits,
  no retries, cancellation/unknown usage, tampering, paid/new-ledger rejection,
  missing/error denominators, original-ledger integrity and known usage overruns.
  Lint, formatter, lock and diff checks PASS. The preceding891-test package's build
  and installed HTTP demo remain applicable: no package/dependency changes here.
-878 protected archive/C06/Gemini files independently hash-identical before/after.
  C06 journal, reports, snapshots, frozen environments and amendments remain intact.

Offline report regeneration (same frozen0.9.1 runtime/dependencies, fresh destination):

```sh
output/private/c09-frozen-env/bin/python scripts/c09_live.py status
output/private/c09-frozen-env/bin/python scripts/c09_live.py report --output output/c09-live-new-report
```

These commands do not load credentials or send requests. Do not run `init` again,
erase claims, change the frozen script/protocol, or regenerate through an evolved
package version. A future version must use a separate execution identity/environment.

Post-run preservation:the0.9.1 environment above was installed before0.9.2 repairs
and verified to reproduce this report with sockets disabled. Dependency pins/audit
copies are in `archives/c09-live-001/`;the original execution script/protocol bytes
and all result artifacts remain unchanged.

## Next work, without changing these results

1. Design a machine-readable answer contract that preserves exact identifiers;
   validate conformance separately from evidence retention and semantic correctness.
2. Address S11 at source-chunk granularity so CAP-shortened WINDOW selections do
   not exclude missing original evidence from retrieval. Preserve original history,
   scope/deletion authority, required context and budget invariants.
3. Freeze new independent cases and primary-versus-control targets before evaluating
   those changes. WINDOW is a deliberately weak control; do not retroactively change
   its failed target or pool repeated cases to make results appear stronger.

Offline design/regression work can continue under C09. New live calls, altered
targets or release acceptance need a separately reviewed scope; no C10 migration
or owner risk waiver has been inferred.
