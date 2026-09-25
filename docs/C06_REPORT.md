# C06 checkpoint report

Updated: 2026-09-22. **Frozen benchmark complete — READY for owner review, with limitations.**
Archived runtime:0.7.2. Workspace:0.8.0. Not owner-accepted or production-qualified.

## Outcome

All **744/744** planned cases have recorded outcomes;zero pending:

- **613 successful live responses**
- **124 raw-context non-fits**, deliberately not sent
- **7 preserved errors**:six provider rejections and one missing-answer timeout

The final26 untouched cases all returned HTTP200. No failed case was retried or
replaced. Snapshot249 preserves every718 terminal entry from223 exactly.
The original organization,current private.env,free-tier/$0 policy and frozen
experiment stayed unchanged. The foreground runner exited0;no runner remains.

Final [leaderboard](../output/c06-live-report-249/leaderboard.md) and
`output/c06-live-report-249/scorecard.json`:**VALID**,all five frozen integrity
gates PASS,primary numerical quality acceptance **PASS**. These statuses describe
the declared fixture and gates,not universal provider-token safety or enterprise readiness.

## Primary result: A5 /900 tokens /120b

| Metric | Approved target | Observed |
|---|---:|---:|
| Fits estimated input budget | 31/31 | 31/31 |
| Source-backed facts retained | ≥28/31 | 29/31 |
| Correct answers | ≥27/31 | 29/31 |
| Median estimated input reduction | ≥90% | 95.18% |
| Truncated answers | 0 | 0 |

Both models at900 score A1:1/31,A2/A3:0/31,A4/A5:29/31 correct.
At3000,120b scores A1:4/31,A2/A3:0/31,A4/A5:19/31.
At3000,20b scores A1:4/31,A2/A3:0/31,A4:19/31,A5:18/31.
20b A2 has29 responses/two errors,A3 has27/four,A5 has30/one.
The missing A5 answer stays in the planned31 denominator;it is not inferred from retention.
A0 is non-fit throughout,not an executed incorrect answer. See leaderboard for
completed-call denominators,zone breakdowns and Wilson intervals.

## Timeout reconciliation — accounting only

Owner-supplied Groq log matches20b at September22 02:11:49AM IST
(September21 20:41:49UTC):HTTP200,**2,513 input+34 output=2,547 tokens**.
The full upstream request ID and answer are unavailable. The rounded$0.00 chart
is not precise per-request billing evidence.

D072/[amendment009](C06_QUOTA_AMENDMENT.md) records one native audited ledger
reconciliation with actual usage,no guessed cache credit,and unchanged zero-price policy.
A narrowly scoped external run-cost admission override checks this exact original
receipt and reconciled ledger/audit. It never rewrites the journal receipt,
grades a missing answer,creates replay content or waives a different unknown outcome.

Evidence:`output/c06-reconciliation-evidence-009.json`,private hash-bound screenshots,
`output/c06-reconciliation-009.intent.json`,`output/c06-reconciliation-009.json`,
`output/c06-recovery-amendment-009.json`,`scripts/c06_recovery_009.py`.
Local attempt:`e3a669a8071b43f790729bed841e3b37`.
Probe:`8435cffb799f9a0f76f33b1ad5a96b14d5f946d0a5684292a8be9b75afb6e2c2`.

## Usage: original receipts versus external supplement

| Accounting scope | Input | Output | Full tokens |
|---|---:|---:|---:|
| Matrix snapshot's known receipts | 1,024,215 | 20,534 | 1,044,749 |
| External timeout reconciliation | 2,513 | 34 | 2,547 |
| Matrix including external evidence | 1,026,728 | 20,568 | 1,047,296 |

Account including independent smoke/two diagnostics:**1,050,769 full tokens**,
623 attempts:616 completed,six rejected,one reconciled. No active or uncertain
reservation remains. Known configured cost$0 throughout;not a provider billing
attestation or measured paid-plan savings.

Final26 calls add64,695 input+911 output=65,606 full tokens;4,096 cached input
was explicitly reported. Original snapshot still marks the lost receipt's usage/cost
unknown:the frozen report does not ingest external reconciliation. Its known-subtotal
asterisk remains intentionally visible;use the supplement above for reconciled totals.
Native settlement-window accounting is retained conservatively;no quota/history reset.

## Verification

- Full local suite:**752 passed**,two existing service deprecation warnings,94.81s.
  Includes22 new accounting-recovery safeguards. Scoped lint/format pass.
- Archived report generation makes zero inference calls. Socket-disabled reproduction
  in `output/c06-live-report-249-offline` is byte-identical across all files.
  Both PNG figures visually inspected.
- All718 baseline223 entries,manifest/profile/execution identity preserved.
  620 unique matrix attempt IDs;no replayed result.
- All26 new recovery/status sidecar pairs bind009/source/evidence;
  case/admission event pairs bind unchanged004. All26 HTTP200,zero new
  input overruns,truncations or failed-case retries.
- Both archived/current core hashes still match their freezes. Operational
  amendments001–009 are disclosed separately,not hidden inside the engine freeze.

Execution:`dd8c88217a8a2b3d2ba4635b9a126f5cdb4776ee283047425603ce8a0b30de77`.
Snapshot:`output/c06-live-batch-249.json`.
Digest:`270fae3f67c1c5a670202ebe9567fcfc5111e5180d20c8ca23882defb6a6c4bd`.
FileSHA256:`d57af9b848cbecab884136da989ede3ddf9d160c50061aea6d61a4305c20dbdb`.

## Limitations and next checkpoint

1. Seven failed responses remain visible;no zero-error reliability claim.
2. Twelve historical A2/A3/900/120b provider inputs exceeded estimates and allowance
   (maximum actual/estimate1.781321). No primary A5 overrun. Frozen gates validate
   estimator/request consistency,not an exact provider-token guarantee. **Hard-budget
   calibration remains unqualified**;S12 requires a separately frozen experiment.
3. A5 retention falls from29/31 at900 to19/31 at3000. S11 records CAP/WINDOW
   interaction;no post-hoc tuning was applied.
4. One synthetic31-fact scenario is not held-out real-world/enterprise validation.
   Free-tier configured cost is not a paid cost-saving measurement.

Next:**C09 security and held-out real-world evaluation**,with these limitations
carried forward. Owner reviews C06 evidence;no owner acceptance is inferred.
C11 measured costs and C12 release still require their own evidence and review.
No additional C06 API calls or key/quota setup are needed to finish this frozen matrix.

For a read-only completion check:
`output/private/c06-frozen-env/bin/python scripts/c06_recovery_009.py`.
Do not rerun settlement or failed cases. Preserve all snapshots,receipts and amendments.

Earlier progress remains in [live history through223](C06_LIVE_HISTORY_223.md);
earlier preparation in [C06 history](C06_HISTORY.md).
