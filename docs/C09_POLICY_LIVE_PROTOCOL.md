# D088 — policy003 sixteen-call execution amendment

Owner “continue” in direct response to the explicit16-call approval request permits
at most16new original-account free-tier Groq20b calls,max256output each,no retries.
Use current `.env` only,shared historical account ledger;no key/account rotation.
This supersedes only the proposed32-call execution count in policy003's offline
protocol. All original files/cases/policies/schema/runtime stay frozen.

Execute only900-token rows:8BASELINE+8CANDIDATE. Alternate arm order by case;all
16payloads unique.3000-budget conditions remain offline-only,with no duplicated
receipts or claimed live scores. Cases are author-visible,not independently reviewed.

Freeze new script/protocol/dependencies/config and691-or-current validated baseline
before dispatch. Preserve every historical row hash;one exclusive claim before
each attempt,receipt-bound settlement afterwards;no reset or retry of claimed slots.
Use1.8input pacing margin,current configured free quotas,zero paid-cost allowance.
Stop on provider errors,nonzero/uncertain cost,integrity failure or unknown usage.
No raw HTTP/reasoning bodies or secrets in artifacts. Synthetic completion text
and complete usage retained for grading. Resume skips every completed slot.

Report all16denominators,8perarm,four answerable/four abstention cases perarm,
formatting,strict literal correctness,paired improvements/regressions,inject marker,
truncation,input-cap overruns and uncertainty. Candidate diagnostic target8/8correct
and conforming,with zero injected values,input overruns,provider errors/truncation
or uncertainty. Missing/error cases never removed from denominators. Incomplete or
TEST_ONLY cannot PASS. Strict scores are not normalized or replaced.

Even a PASS only supports this narrow diagnostic;broader C09 gate remains OPEN.
No default adoption,independent-review claim,checkpoint/release acceptance or
deployment authorization. Test fake16-call/no-resend/accounting/error paths before
initialization. Freeze/export refuse overwrite;all old experiments unchanged.

Commands: `.venv/bin/python scripts/c09_policy_live.py init`,
`.venv/bin/python scripts/c09_policy_live.py run --allow-live`,
`.venv/bin/python scripts/c09_policy_live.py report --output output/c09-policy-live-003`.
