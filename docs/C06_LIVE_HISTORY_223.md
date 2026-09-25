# Archived C06 live progress through223 and recovery preparation

Historical record,not current instructions. See [current C06 report](C06_REPORT.md).

Updated: 2026-09-22. Frozen live package: 0.7.2. **ACCOUNTING RECOVERY — live benchmark incomplete.**

## Current result

**New owner evidence resolves the missing token counts:** matching Groq log shows
HTTP200,2,513 input+34 output. D072/amendment009 preserves screenshots and performs
audited accounting-only recovery.22 new offline tests pass;settlement/continuation
outcome pending. The answer is still missing and stays failed. Details in
[amendment009](C06_QUOTA_AMENDMENT.md);do not restart008. Earlier hold below is the
preserved pre-evidence state,not a request for another screenshot.

**718/744 recorded dispositions;26 untouched cases remain.** Batches178–223 add
43 successful responses,two confirmed HTTP400 rejections and one real network
timeout with unknown processing/usage. Six confirmed rejections remain failures;
the seventh error is uncertain,not eligible for the rejection-review procedure.
All672 baseline177 entries are unchanged. No live runner remains.

A4/3000/20b completes19/31 correct. A5/3000/20b has four correct responses,then
`database` times out at September21 20:41:49UTC / September22 02:11:49AM IST.
No response/status/provider request ID was observed. The account retains its
3,168-token uncertain reservation across day rollover;usage cannot be assumed zero.
Original organization,current private.env,free-tier/$0 scope remain unchanged.

Latest validation:730 local tests pass in86.84s,two existing service warnings.
Report223 reproduces byte-identically with sockets disabled;both figures inspected.
No new inference was dispatched during the September22 inspection. External
request-status/token evidence is needed;see Resume below. C06 is not complete.

### Previous validated session through177

**Latest continuation172–177:five additional successful answers,then one HTTP400.**
Snapshot177 records672/744 dispositions:544 successful answers,124 non-fits,
four preserved rejections and72 unrun. All666 baseline171 entries are unchanged.
The new rejection is the A3/3000/20b `timeout` fact;the fact's name is not a network
timeout diagnosis. Status177 recordsHTTP400;receipt is confirmed provider_rejected,
zero tokens/cost,not uncertain. Root cause unknown;no diagnostic/retry/substitution.

Controller005 stopped as specified. No runner or active/uncertain request remains.
This session used12,799 input+117 output=12,916 tokens. Account including diagnostics:
551 attempts/872,879 full tokens/configured$0. September21 uses67,231 full tokens,
no known cached credit;local132,769 remain. **This stop is new-error review,not quota.**
Next untouched case is A3/3000/20b region_backup,reservation3,246,snapshot178 after
further review. Current wrapper intentionally refuses the new fourth failure.

### Previous continuation through171

**September21 through171:21 successful answers and one new HTTP400.**
Snapshot171 records666/744 dispositions:539 answers,124 non-fits,three preserved
rejections and78 unrun. All644 baseline146 entries are unchanged. The controller
stopped on the new A3/3000/20b `feature` rejection,not quota. No active/uncertain
request remains. Root cause is unknown; no diagnostic or failed-case retry.
Account545 attempts/859,963 full tokens/configured$0;today54,315 tokens,local
145,685 available. Local allowance is not a live provider balance.

147–153 added seven answers and completed
A2/3000/20b (29 answers,two preserved rejections,zero correct). The first A3 case
exposed an operational admission bug: identical payloads across independent
ablations were mistaken for completed-case replay.154/155 made zero HTTP calls;
the repeat loop was stopped and partial156 sidecars preserved,with no active usage.

The separately disclosed [case-bound admission correction](C06_QUOTA_AMENDMENT.md)
(D066/amendment004) validates the claimed case/full request and prevents completed
case replay while allowing independent identical-payload evaluations. Old sources
and all651 baseline records stay unchanged.157–170 obtained14 successful responses,
then171 returned400. Identical A2/A3 payloads have distinct attempts,not replay.

Owner requests continuation. D067/amendment005 reviews only the three exact
confirmed rejections and preserves all666 baseline entries;new failures still halt.
Eleven new wrapper tests and81 prior controller safeguards pass;full suite697 passes
in84.44s,two existing warnings. Read-only preflight was ready;172–177 outcome above.
Admission004,all prior sources,failed outcomes and experiment unchanged.

### Previous completed continuation

**Latest D065 continuation (145–146):two additional successful HTTP200 answers.**
Snapshot146 records644/744 dispositions:518 successful answers,124 non-fits,
two preserved rejections and100 unrun. All642 prior terminal entries are unchanged.
Amendment003 reviewed only the two existing failures; no failed-case or diagnostic
retry occurred. No new errors,truncations,input overruns or uncertain requests.

The controller stopped on **local daily quota**:198,268 counted tokens,1,732
available versus3,245 reserved for the next20b/A2/3000 `endpoint` case. Full daily
usage259,452 minus61,184 confirmed cached input gives that projection. No claim
about the provider's exact remaining balance is inferred. Account including
diagnostics:523 attempts,805,648 full tokens,configured$0. No runner remains.

Next local window: **September21 00:00 UTC /05:30 IST**. Use recovery003 status
before resuming to147; upstream/project capacity may differ. Both errors remain
failures,not replayed successes. C06 is incomplete; no C09 start or acceptance.

### Preserved D064 recovery and diagnostic

**Latest D064 recovery (139–144):five additional successful responses,then one HTTP400.**
Snapshot144 has642/744 recorded dispositions:516 successful answers,124 non-fits,
two rejections and102 unrun. All636 prior terminal entries are unchanged. Six
one-case batches used the original key/account and frozen requests; HTTP statuses
are200,200,200,200,200,400. Amendment002 stopped on the new `region_backup` error,
as specified. No active/uncertain request or background runner remains.

One separately metered diagnostic reproduced the same region_backup request
payload/model without altering the benchmark. It returned HTTP200,2,561 input
+22 output tokens,one attempt,no retries. This suggests intermittent behavior,
not a demonstrated permanent payload error; exact rejection cause remains unknown.
It does not replace the failed benchmark result or qualify the run. Intent/result
artifacts: `output/c06-rejection-diagnostic-001.intent.json` and
`output/c06-rejection-diagnostic-001.json`. No key/provider body was printed or saved.

Account including diagnostics:521 attempts,800,464 full tokens,configured$0.
September20:254,268 full minus61,184 known cached =193,084 quota tokens,6,916
available. **This is a new-error stop,not quota exhaustion.** The current recovery
controller recognizes only the first reviewed failure and intentionally will not
continue unchanged. Preserve both failures; next untouched case is20b/A2/3000
`policy`,3,244-token reservation,new snapshot145 after further recovery review.

### Earlier continuation through138

**Latest continuation (D063, batches132–138):16 additional successful answers and one confirmed provider rejection.** Snapshot138 records636/744 dispositions:511 successful answers,124 non-fits,one error;108 cases remain unrun. The controller stopped for error review, **not daily quota**. September20 still has20,124 tokens of conservative local allowance. No runner or active/uncertain request remains. Full offline suite:640 tests pass, two existing service warnings. Do not ask the resolved organization/billing questions again.

Owner confirms the current `.env` key belongs to the original organization. We identified54,272 known cached-input tokens incorrectly included in the earlier local daily quota calculation. Groq excludes cached tokens. The explicit [cache-aware admission amendment](C06_QUOTA_AMENDMENT.md) corrects only this projection, leaving full usage, prices, quota ceilings and the frozen experiment intact. Its external override is not covered by the original engine freeze and is recorded separately with code hashes/sidecars/events. Known cached credit has since increased to58,880; unknown metadata receives no credit.

**Failure:** A2/3000/20b `feature` is saved as terminal error; the account receipt records `provider_rejected`, a confirmed non-429 4xx response. Exact status and provider error body were not retained by the archived adapter, so the underlying reason is unknown. This is not evidence of exhausted daily quota or an invalid key. One request counted,zero tokens charged by the confirmed-rejection rule; no blind retry/reset. Next untouched case: A2/3000/20b `trace`,3,246-token reservation. The existing controller deliberately refuses further dispatch after any terminal error; review recovery separately while preserving the failure.

### Earlier September20 checks (superseded by D063 where noted)

Continuation check (September20 09:02 UTC): local admission still stops at2,779 available vs3,231 reserved. Current-key organization clarification remains unanswered; no additional inference, profile change or quota reset. Full offline regression suite rerun:617 passed in83.85s with the same two service deprecation warnings. This verifies software regressions, not the125 unfinished live cases.

**Current-key diagnostic (D062):** owner challenges quota and explicitly requests the current `.env` key. A fresh process loaded only that private file, ignoring an inherited key, and made one 32-output-token-capped synthetic request through the archived provider client and original shared ledger, with one attempt/no retries. Groq returned HTTP200: RPD limit1,000/remaining999 and TPM limit8,000/remaining7,894; headers do not expose daily-token balance or organization identity. Usage74 input +22 output =96 tokens, configured$0; this is not benchmark evidence. This corrects any implication that the earlier local2,875 balance was a live Groq quota reading or that all provider capacity was exhausted. Snapshot131 is byte-unchanged;619 terminal/125 pending. Determine whether the current key is from the original organization or another account before attributing provider counters to historical usage; no quota reset or account-switching bypass.

Post-diagnostic local ledger:497 completed requests (495 matrix, one flagship smoke, one quota diagnostic),743,417 tokens total; September20 local usage197,221,remaining2,779 vsnext3,231 reservation. Zero active/uncertain attempts. The local cap remains conservative admission policy, not proof of upstream daily exhaustion. All September20 benchmark usage before the diagnostic was on20b, so separating120b usage would not release local capacity today.

**Free-tier clarification (D061):** owner explicitly confirms Free tier, superseding the earlier upgrade report D060. New Organization Limits screenshots show unchanged GPT-OSS20b/120b caps:30 RPM,1K RPD,8K TPM,200K TPD; they show limits, not remaining usage or verified account identity. Keep the original $0 prices/caps, shared ledger and archived runtime. No paid ceiling or billing migration is needed. September20 08:30 UTC read-only check finds197,125 daily tokens used,2,875 left, below the next3,231 reservation; zero active/uncertain attempts. No new inference; all619 saved dispositions intact.

C08 is delivered and we have returned to C06 before C09 quality qualification. Approved numerical targets, saved key and Free-plan/$0 scope remain resolved. Do not repeat the paid-budget request after D061.

Earlier quota recheck (September20, before D061): read-only models GET returned HTTP200 but no documented rate-limit headers or billing tier. Browser discovery found no connected browser. D060's proposed paid transition was never implemented and is now superseded. Local usage accounting remains authoritative for this run; absence of provider quota headers does not establish additional capacity.

### Latest validated matrix

Latest validated snapshot: `output/c06-live-batch-223.json`. Matrix execution: `dd8c88217a8a2b3d2ba4635b9a126f5cdb4776ee283047425603ce8a0b30de77`. [Validated current leaderboard](../output/c06-live-report-223/leaderboard.md); [report177](../output/c06-live-report-177/leaderboard.md), [report171](../output/c06-live-report-171/leaderboard.md), [report146](../output/c06-live-report-146/leaderboard.md), [report144](../output/c06-live-report-144/leaderboard.md), [report138](../output/c06-live-report-138/leaderboard.md), [report131](../output/c06-live-report-131/leaderboard.md), [report100](../output/c06-live-report-100/leaderboard.md) and [report068](../output/c06-live-report-068/leaderboard.md) remain preserved.

- 718/744 terminal dispositions:587 successful live responses,all124 raw non-fits without inference,six confirmed provider rejections and one uncertain timeout;26 fitting cases remain unrun. Terminal errors are not successful answers.
- All 372 cases for 120b are finished: 310 live answers and 62 non-fits, covering all six variants and both budgets. At 3,000 tokens, A4 and A5 each retain/answer 19/31 correctly; A1 scores 4/31, A2/A3 score 0/31. The larger budget does not improve this frozen fixture's retrieval result; S11 remains open.
- Both models'900-token groups are complete: each scores A1 1/31,A2/A3 0/31,A4/A5 29/31 correct. On20b at3,000 tokens,A1 is complete at4/31;A2 has29 successful answers,zero correct,two errors. A3 has27 answers,zero correct,four errors. A4 has31 answers,19 correct. A5 hasfour correct answers,one timeout and26 unrun. A0 is non-fit at both budgets on both models.
- Six confirmed provider rejections and one uncertain timeout;no observed truncated answer. No error is hidden or converted into success.
- Independent flagship smoke correctly answered shard-19: 804 estimated / 752 provider input tokens, 42 output. One success does not establish the 31-probe acceptance thresholds.

## Primary numerical targets met

All 31 A5/900/120b probes now have real responses. These observed numerical thresholds are met; **overall quality acceptance remains NOT_EVALUATED** because the full run is incomplete (V4 pending, overall INTERRUPTED).

| Criterion | Approved target | Observed |
|---|---:|---:|
| Fits input budget | 31/31 | 31/31 |
| Source facts retained | At least 28/31 | 29/31 |
| Correct answers | At least 27/31 | 29/31 |
| Median estimated input reduction | At least 90% | 95.18% |
| Truncated answers | 0 | 0 |

Primary provider usage: 22,614 input + 1,025 output tokens. Cached-input detail is absent for 22 responses, but input/output totals are present in all 31 receipts; missing cache detail is not missing total usage. Median estimated input is 801 tokens. Reduction is against estimated raw input, not measured paid-plan savings.

For the completed 900-token/120b groups, correct answers are A1 1/31, A2 0/31, A3 0/31, A4 29/31, A5 29/31. A0 is non-fit, not an executed incorrect answer. This fixture does not establish performance on unseen workloads.

The completed A1/3000 baseline scores 4/31 versus 1/31 at 900. This is a measured budget comparison on the frozen fixture, not a change to the primary A5 targets or evidence of general-world quality.

## Verification and safeguards

178–223:43 HTTP200,two HTTP400,one timeout without observed response. All672
baseline177 terminal entries,profile/manifest/identity unchanged. All46 recovery/status
sidecar pairs bind their respective006/007/008 revisions;46 case/admission event pairs
bind unchanged004. No new replay,input overrun,truncation or failed-case retry.
Both archived/current core hashes still match their freezes.

New known usage108,333 input+1,404 output=109,737 full tokens,including6,912 known
cached input;timeout usage remains unknown. Matrix subtotal959,520 input+19,623
output=979,143 known full tokens,594 unique attempts. Account including smoke and
diagnostics:597 attempts (590 completed,six rejected,one uncertain),982,616 known
full tokens plus unknown usage. Known configured costs$0;one unknown cost,not a
complete billing attestation. September21 subtotal176,968 full tokens minus6,912
known cached=170,056 known quota tokens,plus uncertain reservation/usage. No claim
of current available provider quota is made.

Snapshot223 digest: `7f8ae812c8abb757b9b21cea094866299835df9388cf694d38d0eced5e51157b`.
File SHA256: `d38d2924b4968ab61bd30164174be78aeb52660226bc2a3dd980554f0ab3b973`.
Full suite730 passes in86.84s onSeptember22,two existing service warnings.
Report223 validates INTERRUPTED/NOT_EVALUATED;socket-disabled regeneration is
byte-identical across all six files,both figures visually checked. No acceptance inferred.

### Preserved verification through177

172–177:five HTTP200 then oneHTTP400;all666 baseline171 terminal entries,
profile/manifest/identity unchanged. Six recovery/status sidecar pairs bind005;
six case/admission ledger event pairs bind004. No replayed result or rewritten
historical attempt. Matrix851,187 input+18,219 output=869,406 tokens;548 unique
matrix attempt IDs. Both archived/current source hashes still match their freezes.

Snapshot177 digest: `72875f945887b580e2cdbd8f74fb1c24197fa806e76423f5af18d5b5f477d8fd`.
Full suite697 passes in84.44s,two existing service warnings. Report177 validates
INTERRUPTED/NOT_EVALUATED;socket-disabled regeneration is byte-identical across all
six files. Both figures are byte-identical to visually checked171. Five new answers
are within input allowances;no new overrun. No checkpoint/owner acceptance inferred.

### Preserved verification through171

Through171:21 new successful answers use53,752 input+563 output=54,315 tokens.
Matrix total838,388 input+18,102 output=856,490. All644 baseline146 and651
baseline155 terminal entries are unchanged;542 unique matrix attempt IDs.
No new provider-input overruns. All15 recovery/status pairs157–171 bind004;
15 case/admission-event pairs bind cases/attempts and amendment004. Legacy001
admission sidecars alone do not establish complete operational provenance.

Snapshot171 digest: `910df5afaa2c38727a78f7a2cce2c9ee8aaac8c58f566689f16a45e790a56825`.
Report171 validates INTERRUPTED/NOT_EVALUATED;socket-disabled reproduction is
byte-identical across all six files,both figures visually checked. Full regression
after004:686 pass,two existing service warnings. No acceptance inferred.

### Preserved verification through146

Recovery145–146 adds5,118 input +66 output =5,184 full benchmark tokens. Matrix
usage now784,636 input +17,539 output =802,175. All642 prior terminal entries,
manifest/profile/identity remain unchanged. Both requests returned HTTP200; no new
provider-input overruns. Recovery/status sidecars bind amendment003,which binds
the unchanged recovery002 source,baseline144 and diagnostic evidence. Archived
engine and prior operational source files were not rewritten.

Snapshot146 digest: `92dbc7cc16eb2af9ef68c14974ab91ff59d120852fe3a80ba9891f790f6a35ca`.
Report146 validates INTERRUPTED/quality NOT_EVALUATED. Socket-disabled regeneration
is byte-identical across all files;both figures are byte-identical to the previously
visually checked report144 figures. Full regression673 passes in82.20s,including
10 new recovery003 tests,two existing service warnings. Scoped lint/format,brain
integrity and both archived/current core-freeze checks pass. No acceptance inferred.

### Preserved verification through144

Recovery139–144 adds12,798 input +131 output =12,929 full benchmark tokens. Matrix
usage now779,518 input +17,473 output =796,991. All636 prior terminal entries,
manifest and profile remain unchanged; no new estimate/allowance overrun. Six
recovery and HTTP-status sidecar pairs match amendment002/source hash; original
amendment001 admission sidecars/events remain in force. Both core freezes match.

Report144 validates INTERRUPTED/quality NOT_EVALUATED,digest
`aa50540114363efa74ff0b6cb35fe7c0417e73ce6d91b54f0d0a724c82636ea8`.
Socket-disabled regeneration is byte-identical across both report directories;
zone figure inspected,context/cost figure is byte-identical to the previously
inspected figure. Post-diagnostic full regression663 passes in78.01s,including
seven diagnostic and16 recovery tests; two existing service warnings. Both failures
stay visible. Scoped lint/format and project-brain integrity checks pass.

### Preserved amendment001 verification through138

Amended continuation132–138 adds41,128 input +407 output =41,535 full tokens. All619 snapshot131 terminal entries are exactly unchanged;511 successful matrix attempt IDs are unique. All16 new inputs are below their estimates and allowances; the12 historical overruns remain unchanged. Seven sidecars and17 same-ledger admission events bind the operational source hash and amendment to every new attempt, including the rejection. Both archived and workspace core hashes match their freezes.

Current matrix usage:766,720 input +17,342 output =784,062 full tokens. Ledger including smoke/diagnostic:513 completed requests +one confirmed rejection =514 attempts,784,952 full tokens,configured$0. September20:190 requests,238,756 full tokens minus58,880 known cached =179,876 quota-counted tokens;20,124 available. Full totals remain stored unchanged; exceeding200,000 full tokens is not exceeding the corrected quota projection.

Report138 validates INTERRUPTED/quality NOT_EVALUATED, digest `a44b63042959ba2388743f35f2721923963b5ad5c9cbc84c634f5e2e6265d080`. Socket-disabled regeneration into `output/c06-live-report-138-offline` is byte-identical across all report files,zero inference; both figures visually inspected. Full suite640 passes in81.11s,including23 cache-accounting and19 controller cases; two existing service deprecation warnings. No benchmark qualification or owner acceptance inferred.

### Historical verification through131

The 0.7.2 archived environment validates the original snapshot and its zero-call resume was byte-identical. All 416 terminal entries from snapshot100 remain unchanged in snapshot131; its 495 provider attempt IDs are unique. Both archived and current core sources still match their freezes. No core/generation/threshold changes, ledger reset or paid upgrade. Gemini diagnostic results remain separate; discussion of switching providers did not replace the approved Groq protocol.

Latest continuation (September20, batches101–131): 172 new live responses and 31 non-fits; 191,294 input +5,831 output =197,125 new tokens. The foreground controller completed every 900-token group and advanced 20b A1/3000 to its last question, then stopped on daily quota. No active/uncertain requests or background runner remains. All new provider inputs are below both their estimates and allowances; the 12 historical A2/A3/900 overruns remain unchanged.

Current matrix usage: 725,592 input +16,935 output =742,527 tokens. Including the independent smoke, the ledger has 496 completed requests /743,321 total tokens /configured $0 across four UTC days. September20 used197,125, leaving2,875 below the next3,231-token reservation. This is a quota stop, not completion of all cases. Nineteen controller tests were rerun and passed today; the full617-test result below is the September19 baseline.

Report131 validates as INTERRUPTED with quality NOT_EVALUATED. Snapshot131 digest: `15b7372e2d8af1f39cc9edde3e913c65c3692c8d0381568805e04c7b5ce2c0db`. Both figures were visually inspected. Regeneration into `output/c06-live-report-131-offline` with socket creation blocked is byte-identical to the full report directory, with zero inference. All 27 controller/brain regression tests and scoped lint/format pass; the brain index, source and local links validate.

### Preserved earlier verification

The September19 continuation (batches069–100; owner D059 “complete all cases”) saved 75 new live responses and 31 more non-fits. New usage: 165,116 input +2,775 output =167,891 tokens. Batch069 was invoked directly; the tested foreground controller paced070–100 through minute windows without stopping at group boundaries. It finished the entire first model, started the second, then exited safely on daily quota exhaustion. No active/uncertain attempts, canceled request or background runner remained at that stop.

At snapshot100, matrix usage was 534,298 input +11,104 output =545,402 tokens. Including the independent smoke, the account ledger had 324 completed requests /546,196 total tokens /configured $0 across three UTC days. Daily totals: September13 148,494; September14 198,729; September19 198,973. Each was within the 200,000-token local policy; no ledger reset. September19's remaining 1,027 could not cover the next 1,050-token reservation. This was a real quota stop, subsequently resumed September20.

Controller verification: 19 new offline cases; full suite **617 passes**, with the same two service test-client deprecation warnings. Scoped lint/format and current/archived core-freeze checks pass. The controller stays outside frozen package code; it reads status without a key by default and never edits quota policy, provider identities or result records. See [runner guide](RUNNER.md).

Report061 validates as INTERRUPTED with quality NOT_EVALUATED. Both figures were visually inspected; network-disabled regeneration into `output/c06-live-report-061-offline` reproduces every report file with identical hashes and zero inference. Snapshot061 digest: `e620587c555a0c80b638d74d469471f2b220959205e1e81fe3ca9f15cacf92e6`. Eight brain tests and scoped lint/format pass. No source or frozen-package changes were required.

Earlier report068 also validated as INTERRUPTED with quality NOT_EVALUATED; its network-disabled regeneration was byte-identical. Current report100 validates with the same incomplete-run status. Snapshot100 digest: `dd47b21817670bd10683983c5e792062fa1a1f2255f031c062782dfb227656c6`. This remains a progress handoff, not checkpoint completion or owner acceptance.

Report100 verification completed: both figures visually inspected; `output/c06-live-report-100-offline` regenerated with socket creation blocked is byte-identical to the entire original report directory, with zero inference.

Provider-token audit (`output/c06-token-audit-061.json`): 12 of the 155 completed 900-token/120b responses report input above both the estimate and allowance (four A2, eight A3): 1,052–1,566 actual versus 877–880 estimated, maximum ratio 1.781321. Primary A5 has no observed exceedance; neither do the 81 completed 3,000-token responses. The frozen fit gate checks estimates, not an exact provider-token guarantee. This limitation prevents hard-budget/calibration claims even where numerical primary targets are met. S12 proposes a separately frozen accounting/calibration experiment; no multiplier, protocol or saved result was changed.

September19 extension through100: all 87 new receipts today report inputs below both their estimates and allowances. All 155 completed 3,000-token/120b responses have no observed overrun. The earlier 12 lower-budget overruns are unchanged; the historical audit artifact is preserved rather than rewritten. These observations do not establish a universal tokenizer calibration bound.

Organization quotas are conservatively aggregated across both models: 30 RPM, 8,000 TPM, 1,000 RPD, 200,000 TPD. Lower project limits or other traffic can still throttle. Configured charge is $0; this is not a provider billing attestation. Minute limits are temporary; daily limits may spread the workload across days.

## Resume

**Current hold:unknown usage for A5/3000/20b database at223. Do not restart live008.**
The six earlier rejections are reviewed,but this timeout is not a confirmed rejection.
No reserved/inflight attempts remain;one uncertain attempt blocks across UTC days.
No new key,quota reset or alternate account resolves missing processing evidence.

Look in the original Groq project's Dashboard → Logs/Usage for
`openai/gpt-oss-20b` around **September22 02:11:49AM IST / September21 20:41:49UTC**.
[Groq project documentation](https://console.groq.com/docs/projects) describes these
views;it does not guarantee this individual request is visible. Share matching status
and actual input/output token counts (cached usage if available),or provider confirmation
that the request was not processed. Absence of a dashboard row alone is not proof.
Hide API keys. Console access was unavailable in this session;owner was asked.

- Local attempt ID: `e3a669a8071b43f790729bed841e3b37` (not a Groq request ID).
- Probe ID: `8435cffb799f9a0f76f33b1ad5a96b14d5f946d0a5684292a8be9b75afb6e2c2`.
- Created epoch:1790023309.5457401. Reason:timeout. Reserved:3,168 tokens.
- Usage,charged tokens,cost,completion hash and settlement are absent;HTTP status
  sidecar223 has no observed responses. Request processing remains unknown.

Future recovery needs a separately reviewed,audited accounting procedure based on
external evidence. The ledger supports `resolve_uncertain` with actual usage or
confirmed-not-processed evidence. **Ledger reconciliation alone is insufficient:**
the benchmark journal's immutable failed receipt has unknown cumulative cost and
independently blocks dispatch. Preserve snapshot223,the failed result and all historical
receipts;do not silently edit the journal,retry the failed case,assume zero usage or
use reserved tokens as observed consumption. No reconciliation has been performed.

Read-only status from the project directory:

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_008.py
```

This read-only command stops for recovery review. Do not rerun live or expand the
reviewed-error set to waive uncertainty. Next export224 only after evidence-backed
recovery;26 untouched A5/3000/20b cases remain. Diagnostic001 stays single-use.
Preserve all eight operational amendments and sidecars. Current0.8.0 workspace
code is not this experiment. No paid transition,account switch/reset,quota-ceiling
increase or next-day background task. The local window is not a verified Groq
reset time or a guarantee of provider availability.

Capacity planning only: the historical offline full matrix estimated 1,171,296 input tokens (1,330,016 including every 256-token output reservation). Actual live usage differs, but this explains why the conservative shared 200,000-token/day policy can spread full qualification across several quota days. No completion-time or provider-billing guarantee is inferred.

## What remains

Resolve the external processing/usage evidence and review accounting recovery,then finish the26 untouched cases. Validate both models and all variants,assess approved primary targets honestly,and regenerate final reports/figures offline. Preserve all seven errors;finishing the remaining cases does not erase them or guarantee qualification. C06 is not complete or owner-accepted. C09 quality,C11 measured costs and C12 release still require this live evidence.

Earlier preparation, offline evidence, approvals and C08 preservation details are retained in [C06 history](C06_HISTORY.md). The known CAP/WINDOW retention regression remains separately proposed experiment S11, not tuned after live results.
