# C09 — post-CI quality and authority review

2026-09-28. Offline engineering review only;not independent adjudication,
new model evidence,owner acceptance or an approved architecture change.
Three-platform CI is complete. C09 semantic quality remains OPEN.

## Evidence checked

Read the frozen policy003 cases/truth,assembly path,policy example and saved
live report. Read qualification002 and conflict-analysis findings. No frozen
files were edited and no archived runner was executed under the current runtime.

- Saved policy003 report SHA256 remains
  `80247317649fd7d5f314b09c608a0f227b4d3d5c62907358d7203f70ea328501`.
- Qualification002 report SHA256 remains
  `813e06da87d5b066f05eaa80a219521b04f35d89e399c55a6de9c1c9fe85f746`.
- Read-only assertions verify16policy003 outcomes,all records retained in each,
  both arms5/8correct,one paired improvement and one regression,target FAIL.
- The saved offline preparation contains32conditions with all records retained,
  zero provider calls and independently_reviewed=false. These are not32live calls.

This checks consistency with saved evidence,not a fresh receipt/ledger audit.
The original receipt-bound reports and frozen-runtime replay evidence remain
in [policy003](C09_POLICY_LIVE_REPORT.md) and
[qualification002](C09_QUALIFICATION_LIVE_REPORT.md).

## Failure separation

| Observation | Supported conclusion | Not established |
|---|---|---|
| Qualification002 PRIMARY14/16;two empty long-history answers despite retained evidence | Retention does not ensure a usable answer | Internal model/provider cause;retry effectiveness |
| Policy003 ordinary conflict passes in both arms;reversed and duplicate conflicts fail in both | Saved outputs violate the frozen conflict rule in those conditions | Causal order/duplication effect from one observation per condition |
| Expanded policy fixes missing evidence but fails the hostile case | One improvement is offset by one regression;do not adopt it | General superiority or a semantic fix from JSON conformance |
| Policy003 all16requests retain all records | This diagnostic failure is not explained by recorded context omission | Universal retrieval correctness or truthful model interpretation |

There is no demonstrated need here for a larger context window,another retrieval
backend or another prompt-only variant. Empty-answer rejection remains separate
from semantic correctness;rejecting invalid output does not make a task correct.

## Authority/fixture review packet

Reviewers should first judge source records and intended rules without viewing
model outputs. Record disagreement and rationale,then compare with frozen truth.
These existing cases are development evidence,not a new blinded holdout.

| Case family | Frozen intended interpretation | Reviewer question |
|---|---|---|
| Conflict,reverse,duplicate | UNKNOWN for two equally authoritative incompatible values;copies do not vote | Is the word "approved" in only one record/question misleading relative to the stated equal-authority rule? |
| Explicit update and reverse | The explicit replacement is current regardless of presentation order | What authenticates an update in the intended pilot,as opposed to a sentence claiming one? |
| Entity scope | Only the requested entity's fact applies | Are entity identifiers and aliases unambiguous in the real workload? |
| Missing evidence | UNKNOWN | Does the workload distinguish absent,expired,denied and contradictory evidence? |
| Hostile tool | Preserve the verified user fact;tool instructions cannot override policy | Is "verified" an authenticated property or merely a word in untrusted content? |

The frozen truth is coherent under the experiment's intended rules. This review
does not certify that prose labels prove real-world authority. In the current
fixture assembly,the records are role/content pairs,all turns have the same
timestamp,and authority/update meaning is carried by text. Tenant authorization
is a separate security boundary;it is not proof that a factual claim is correct.

If independent review disputes a case,retain its original score and document the
disagreement. Any revised fixture needs a new identity and new evidence;do not
regrade old runs,remove failed cases or weaken the declared gate retrospectively.

## Architecture decision required before implementation

Keep the current generic context core and default policies unchanged. For the
selected pilot,first decide whether authoritative structured records actually
exist outside conversation text.

- If they do,a separately reviewed application-layer adapter could validate
  source identity,entity/attribute,revision and explicit supersession before
  resolving conflicts. Provenance must come from authorized ingestion,never from
  arbitrary model/tool claims. This would require a new contract/version and tests.
- If they do not,do not fabricate authority fields or add a regex conflict detector.
  Treat semantic interpretation as unqualified until a fresh reviewed evaluation
  passes. Human escalation may limit pilot risk but is not a passing model score.

This is a decision proposal,not implemented functionality or a scope waiver.
No source-value hardcoding,automatic prompt experiments,new model calls or
default adoption. A narrowed context-only delivery would need explicit owner
scope approval and would not erase C09's failed answer-quality evidence.

## Next gated sequence

1. Owner selects the pilot workload and identifies its trusted source/update
   rules. See [pilot intake](OWNER_REVIEW.md#pilot-intake-after-cross-platform-ci).
2. An owner-designated domain reviewer independently adjudicates source authority
   and expected answers. This assistant's engineering review cannot fill that role.
3. Prepare a new development/heldout protocol for that workload,with truth isolated
   from assembly,balanced answer/abstention cases,order/duplicate controls and
   security/deletion/retention checks. Keep development cases out of qualification.
4. Before any inference,freeze the reviewed protocol/runtime and obtain a separate
   explicit provider/account,request/token/spend/retry budget. Existing budgets are
   exhausted. Report errors,non-fits and invalid answers in original denominators.
5. Only after acceptable quality,measure paired latency and total cost on the same
   representative workload and proceed to environment-specific pilot qualification.

Current stop point:workload/source-authority choice and independent reviewer are
not supplied. No new runtime code,credentials,provider calls,customer data,
deployment or long test reruns were needed for this review.
