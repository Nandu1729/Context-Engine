# C06 known-cached-token admission correction

Recorded September20, before batch132. Owner confirms the current `.env` key is
from the original organization and requests continued free-tier testing.

Groq's [rate-limit documentation](https://console.groq.com/docs/rate-limits)
excludes cached tokens. The original local guard counted every input/output token.
At snapshot131 plus diagnostic001, today's ledger contains197,221 full tokens,
including54,272 explicitly reported cached input tokens. The corrected conservative
quota projection is142,949 tokens, leaving57,051 of the unchanged200,000 allowance.
Unknown cache detail gets zero credit, not an estimated cache hit.

## Implementation boundary

`scripts/c06_cached_quota.py` is an explicit external admission override, **not part
of the archived engine freeze**. It substitutes a RuntimeStore subclass only for
the CLI's account store, inside the archived Python process. The benchmark journal,
engine package files, assembly, fixtures, prompts, generation, grades, thresholds,
account alias, price cards and quota ceilings remain unchanged. No usage rows,
timestamps, receipts, execution identities or completed results are rewritten.

The original profile's unchanged hash does not prove unchanged admission behavior.
Always accompany batch132 onward with `output/c06-quota-amendment-001.json`, its
source hash, per-batch `.admission.json` sidecars and `cached_quota_admission_v1`
ledger events. These explicitly document the operational amendment.

Admission uses one SQLite transaction, the same shared ledger, aggregate limits
across models and the same conservative local UTC daily window. It subtracts cache
only from validated completed receipts whose usage total equals recorded full
tokens. Monetary accounting and stored full usage are untouched. Each new request
reserves its full estimated input plus output; no prediction of future cache hits.
Request-count limits, minute pacing, clock guards, unknown/active usage stops,
explicit live opt-in, no-overwrite exports and no completed-probe resend remain.
The original controller remains available but counts full tokens conservatively.

## Commands

After the reviewed rejection at138, use the recovery controller described below;
the original commands retain their terminal-error hold.

Run from the project directory:

```bash
output/private/c06-frozen-env/bin/python scripts/c06_cached_quota.py
output/private/c06-frozen-env/bin/python scripts/c06_cached_quota.py --allow-live
```

The first command is read-only. The second holds the original controller lock and
loads only the current private `.env` file for each batch. It checks the archived
engine hash and admission amendment before dispatch. No key is displayed. No
background next-day task, provider quota increase, billing change or account reset.
Provider availability is still authoritative; a local admissible estimate is not
a guarantee of successful service or complete remaining daily capacity.

## Initial verification

23 new offline cases plus19 existing controller cases pass, covering known versus
unknown cache, mismatched receipts, active holds, token and request windows,
unchanged historical rows, audit events, concurrency, duplicate prevention,
scope/price/policy guards and opt-in. Scoped lint/format pass. Live continuation
and final report validation are recorded in the main C06 report. Full offline
regression completed:640 tests pass in81.11s, with two existing service deprecation
warnings. The intermediate amended snapshot132 validates through the unchanged
archived report validator as INTERRUPTED; incomplete matrix is not acceptance.

## Reviewed continuation after snapshot138

Owner requests continuation after the error handoff. Amendment002 records the
engineering review: `feature` has a confirmed rejected/non-uncertain receipt;
exact HTTP status/body and root cause are unknown. Do not retry or rewrite it.
All636 baseline terminal entries,including this error,must remain exactly equal.
`scripts/c06_recovery.py` continues only untouched cases,one logical case per
batch,using amendment001's unchanged accounting. Any new error/truncation,
uncertainty,drift or quota stop halts; no broad failure allowlist or future waiver.

The original engine/profile/generation/transport settings stay frozen. External
HTTPX response hooks record only integer status and timestamp in exclusive
`.http-status.json` sidecars; no bodies,headers,keys or prompts. `.recovery.json`
sidecars bind source/amendment before dispatch. Both external operational changes
are outside the original engine freeze and must accompany reports. Sixteen new
offline tests plus42 existing controller tests pass before dispatch.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery.py --allow-live
```

First command is read-only; second holds the same single-controller lock. Saved
errors remain reportable failures even if every remaining case later completes.

Outcome through144: five HTTP200 responses then new HTTP400; amendment002 correctly
halts rather than ignoring the new failure. A separately metered,single-use
diagnostic001 repeats that payload with one attempt and returns HTTP200; its success
does not replace either benchmark error. Original rejection cause remains unknown.
Current recovery commands therefore stop for further review. See C06_REPORT.md for
saved artifacts,accounting and the next untouched case. Full suite663 passes.

## Review after the second rejection (amendment003)

Owner requests continuation. Both saved failures are confirmed rejected,not
uncertain; the second has HTTP400 evidence and a separately metered successful
identical-payload diagnostic. This does not establish root cause or repair either
benchmark result. Amendment003 binds snapshot144,diagnostic001,the unchanged
recovery002 source,and `scripts/c06_recovery_003.py`. The small wrapper supplies
only the two exact reviewed failures and new baseline/provenance to the original
one-case controller. All642 baseline entries remain immutable; any NEW failure
still stops. No new error waiver,diagnostic retry,quota change or core rewrite.
Ten new tests plus58 previous controller tests pass before dispatch145.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_003.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_003.py --allow-live
```

First command is read-only. After this review,the second continues untouched
cases within remaining quota. Sidecars reference amendment003,which binds the
unchanged parent implementation. Earlier commands/artifacts remain preserved.

Outcome145–146:two HTTP200 answers,no new errors;controller stops on local daily
quota (1,732 available,next reservation3,245). All642 baseline entries unchanged.
Report146 is offline-identical;full suite673 passes. Recheck after next local
window before resuming147. No background task or provider-reset guarantee.

## Case-bound duplicate protection (amendment004)

September21 completed A2/3000/20b at snapshot153 (29 answers,two preserved errors).
A3 merchant has an identical request/estimate/key to independent A2 merchant.
Amendment001's completed-request-key guard incorrectly treated that as replay;
154/155 exported zero-call quota pauses while status remained ready. The repeated
loop was stopped; partial156 sidecars remain,no new attempt/uncertain state.

Amendment004 replaces only external account admission: validate the one claimed
prepared benchmark case against its full reconstructed key,model,reservation and
frozen identity; use durable case/attempt events to block completed-case redispatch.
Distinct scientific cases may share payload/key. Journal completion protection,
active/uncertain holds,full reservations,cache projection,request limits and prices
remain. No key/profile/receipt/result rewriting or synthetic replay substitutions.
The original archived runner always expected independent A2/A3 evaluations.

`scripts/c06_recovery_004.py` preserves previous sources and adds fail-fast handling
for a zero-progress ready loop,plus snapshot numbering that skips any existing
sidecar.13 focused tests pass before157. New recovery/status sidecars bind004;
legacy `.admission.json`001 describes quota projection only and must not be read as
complete enforcement provenance. Ledger case/amendment events supply the new binding.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_004.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_004.py --allow-live
```

Only the two reviewed historical errors remain allowed; any new failure stops.

Outcome157–171:14 successful answers,then A3 feature HTTP400. Combined with147–153,
September21 added21 answers/one new rejection;666 terminal/78 unrun. All651
baseline155 entries unchanged. No active/uncertain requests;145,685 local tokens
remain. Report171 is offline-identical,figures inspected;686 regression tests pass.

## Third rejection review (amendment005)

Owner asks to continue. Exact A3 feature rejection is bound to snapshot171 and its
HTTP400 sidecar;receipt is confirmed rejected,zero tokens/cost,not uncertain.
Underlying provider cause remains unknown. No diagnostic/retry/result replacement.
New wrapper `scripts/c06_recovery_005.py` preserves666 baseline entries and allows
only the three exact historical failures. Any new failure still halts. One-case
dispatch,lock,pacing,case admission004 and its ledger events stay unchanged.
Recovery/status sidecars bind005,which binds004;legacy admission sidecars bind001
quota projection only. None of these external revisions changes the core freeze.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_005.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_005.py --allow-live
```

First command is read-only. Next untouched case cache/20b/A3/3000 starts172.

Outcome172–177:five successful HTTP200 answers then timeout-fact HTTP400;672 terminal,
72 unrun. All666 baseline171 entries preserved;no active/uncertain requests. This
is fourth-error review,not quota (132,769 local tokens remain). Commands above
now intentionally stop;do not automatically add this new failure to the reviewed
set. No failed-case/diagnostic retry or result substitution. Next untouched case
region_backup/20b/A3/3000,reservation3,246,snapshot178 after separate review.
Full suite697 passes;report177 validates INTERRUPTED/NOT_EVALUATED and reproduces
byte-identically offline. Frozen core and all prior operational sources unchanged.

## Fourth rejection review (amendment006)

Owner requests completion of remaining tests. Exact timeout-fact HTTP400 at177
is confirmed rejected,not uncertain;zero charged tokens/cost. Root cause unknown.
Amendment006 binds snapshot177,status177,predecessor005 and unchanged admission004.
All672 prior terminal entries and four exact failures remain immutable. Continue
untouched cases only;new failures stop for evidence review,not automatic waiver.
103 focused controller tests pass before178. Original ceilings/prices/core unchanged.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_006.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_006.py --allow-live
```

Read-only preflight ready132,769 local tokens;next region_backup/20b/A3/3000.

Outcome178:one confirmed region_backup HTTP400;zero tokens/cost,no uncertainty.
All672 old entries unchanged;673 terminal/71 unrun.006 stopped as specified.
Full regression708 passed before007;error root cause unknown,no failed-case retry.

## Fifth rejection review (amendment007)

D069 explicitly reviews178/status400/confirmed rejected receipt;five exact errors
remain failures. Immutable007 binds predecessor006,baseline178/status178 and
unchanged admission004;protects673 prior entries.114 focused tests pass before179.
New failures still stop for evidence review;no automatic waiver or core change.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_007.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_007.py --allow-live
```

First command read-only;original account/ceilings/prices/history preserved.

Outcome179–183:four successes then shard HTTP400;678 terminal/66 unrun. All673
baseline178 entries unchanged;no active/uncertain usage. Local122,427 tokens remain.
007 stops as specified. Full suite719 passes before008.

## Sixth rejection review (amendment008)

D070 explicitly reviews183/status400/exact zero-token rejected receipt;root cause
unknown.008 binds baseline183/status183,immutable predecessor007 and admission004;
protects678 terminal entries and six exact failures.125 controller tests pass before184.
Untouched cases only,new failures still halt for review;no automatic waiver/retry.

```bash
output/private/c06-frozen-env/bin/python scripts/c06_recovery_008.py
output/private/c06-frozen-env/bin/python scripts/c06_recovery_008.py --allow-live
```

## Current hold after008 — 2026-09-22

The live command above is historical authorization,not a current resume instruction.
184–223 produced39 successful responses then a real A5/3000/20b database timeout.
Snapshot223 has718 terminal/26 untouched,including six confirmed rejections and one
uncertain timeout. All678 baseline183 entries remain preserved. No runner remains.
The3,168-token uncertain reservation persists across UTC rollover;no response or
usage was observed. Do not expand the reviewed-rejection set,assume zero usage,
reset accounting or retry the case. D071 requires external processing/usage evidence.

See [C06 report](C06_REPORT.md) for exact IDs/time and evidence needed. Future recovery
must separately address both audited ledger settlement and the immutable journal
receipt's unknown cumulative cost,preserving223 and its failed outcome. No further
amendment or reconciliation has been performed. Full suite730 passes;report223
reproduces identically offline. Software checks do not resolve missing live usage.

## Evidence-backed timeout accounting (amendment009) — 2026-09-22

Owner has supplied the matching Groq Logs row:20b,September22 02:11:49AM IST,
HTTP200,2,513 input+34 output tokens. Full provider ID and answer are unavailable;
the chart's rounded$0.00 does not independently prove exact request cost. Original
free-tier zero-price policy remains in force. Screenshot copies are private and
hash-bound by `output/c06-reconciliation-evidence-009.json` and immutable plan009.

`scripts/c06_recovery_009.py --reconcile` uses native audited settlement once,with
actual2,547 tokens and no cache credit. Original ledger identity/price/reservation
and all journal results remain unchanged except the ledger's explicit reconciliation
fields/event. Native settlement-time quota attribution is retained conservatively.
There is no new answer,replay entry or failed-case resend.

The separately hashed009 run-cost admission override requires the exact old receipt
AND externally reconciled ledger/audit before substituting its known configured cost
in the admission sum only. It does not edit the receipt,grade,report or frozen package.
Other unknown costs,new failures,identity/evidence drift still stop. New recovery/status
sidecars bind009;unchanged case/admission events bind004. Pre-dispatch22 tests pass.

Use only archived Python for009. Default read-only;`--reconcile` is separate from
`--allow-live`,which continues untouched cases only. Never rerun a consumed settlement
intent. Preserve223 and all eight predecessors. Final report must show the original
missing usage receipt plus the external2,547-token accounting supplement separately.
