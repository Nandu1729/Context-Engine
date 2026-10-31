# D100 — bounded LongMemEval development comparison

Frozen before dispatch, 2026-09-29. Owner's explicit “approve” authorizes at most
14 new Groq `openai/gpt-oss-20b` calls on the existing confirmed free-tier account,
current `.env`, max256 completion tokens each, no retries or paid use. Only selected
public LongMemEval context may leave this machine. No customer data, whole-corpus
upload, training, held-out execution, default adoption or acceptance is authorized.

## Fixed comparison

Use unchanged0.9.6 and existing `longmemeval-review-001` preparation/split. Select
one of its35 development examples per category: abstention, knowledge-update,
multi-session, single-session-assistant, single-session-preference,
single-session-user, temporal-reasoning. Exclude examples whose source audit says
sessions occur after the question; do not repair dates or select by answer,
retention, model outcome or annotation coverage. Within each category choose the
smallest canonical SHA256 of `["longmemeval-live-development-v1", question_id]`,
then source row as tie-breaker. Missing category or malformed preparation stops.

Each selected example uses the saved exact3000-budget `dated` and
`dated_recovery` wire requests. Alternate arm order by category: OFF/ON then
ON/OFF. CAP35, retrieval reserve280, summary reserve0, date mapping and questions
remain unchanged. No added answer schema/prompt repair/reassembly. The two payloads
may be identical; still report two separately authorized observations, not two
independent examples. Seven examples is exploratory, not population accuracy.

Labels stay local and separate. The70 held-out rows remain unassembled/unscored.
The prior split has shared background sessions; it is not independently blind.
Source duplicate IDs/order/date caveats remain visible; no corpus quality claim.

## Safety and accounting

Separate external `scripts/longmemeval_live.py` and fixed private identity
`output/private/longmemeval-live-001`; never execute/re-freeze an old experiment.
Freeze runner, protocol, runtime/dependencies, selected input/label/assembly file
hashes, complete preparation report/split/plan, and every historical ledger row.
Verify original dataset hash before initialization/run/report. The account's
existing `c06-live-account.sqlite` receives append-only new usage; no quota reset.

Use existing ProviderClient/GroqTransport with temperature0, reasoning low,
max_completion_tokens256, include_reasoning=false, no tools/streaming, replay OFF,
max_attempts1, attempt20s/total25s. No model/account fallback. Read-only model-list
preflight must list the exact model active; it is not an inference probe or proof
of upstream billing. Existing zero-price free-tier policy remains required.

Account ceilings:30RPM/8000TPM/1000RPD/200000TPD, zero configured paid allowance.
Conservative external admission uses ceil(estimated input×1.8)+256; actual usage
is settled by the unchanged client. No claim of exact native input token safety.
Minute waits are at most30seconds each/300seconds per slot; daily quota or unsafe
account stops. Refuse unresolved reservations/unknown costs or new unclaimed
account traffic. No concurrent dispatch; exclusive lock, stale locks fail closed.

Write durable exclusive claim BEFORE dispatch and receipt AFTER settlement; bind
receipt content/usage/model to ledger completion hash and request key. A claim
without receipt is uncertain and never resubmitted. Preserve all files on error.
Stop on provider/transport error, unknown accounting, integrity drift or exceeded
allowance. Known-settled empty, truncated or filtered results remain failures for
answer usability but do not trigger retries; continue only to other planned slots.
Completed rerun makes zero calls. At most14 claims/attempts, not14 successes.

## Reporting

Retain all14 planned denominators, including not-attempted/uncertain/error/empty/
truncated results. Report actual tokens, configured cost (not a billing attestation),
latency, native input-cap overruns and nonempty successful answers separately.
Literal exact equality with the local reference is descriptive only: references
include long prose and no official semantic judge runs. No calls to another judge.
Semantic review is PENDING unless separately recorded as assistant-assisted review;
it must never become independent-human review or official LongMemEval accuracy.

No predeclared release-quality pass follows from this exploratory comparison.
Keep failed C09 evidence and all acceptance gates unchanged. Exhausting D100 does
not authorize further prompts, larger completion limits, reruns or held-out calls.
