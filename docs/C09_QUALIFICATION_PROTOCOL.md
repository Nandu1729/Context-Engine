# C09 qualification002 candidate — offline preparation

2026-09-23. Separate experiment, not a rerun or rescore of live001. Package0.9.2
is unchanged. This protocol and fresh synthetic fixtures are author-visible;
**independent/owner review is pending**. They are not unseen held-out evidence.
Freeze before the first preparation; do not tune cases, thresholds or engine after
seeing outcomes under this identity. Corrections require a new experiment identity.

## Fixed comparison and proposed targets

Eight new cases: stale update, unresolved conflict, paraphrase, Spanish evidence,
hostile tool instruction, absent answer, long history, CAP-middle fact. Six are
answerable and two require UNKNOWN. One example/category cannot establish general
accuracy. Explicit unresolved conflict overrides recency; tool claims never gain
instruction authority. No customer data, credentials or original benchmark answers.

32 planned slots: eight cases ×900/3000 input caps ×two conditions. PRIMARY is
CAP_RETRIEVE_WINDOW with recover_capped_window=True; CONTROL is identical except
False. Both receive the same AnswerContract instructions in the system message
**before** assembly/token accounting. PIN remains enabled with empty pins,
SUMMARIZE disabled, all other package defaults unchanged. Completion reservation256.
Order: case-file order,900 then3000,CONTROL thenPRIMARY. Fixed evaluation time
2026-09-23T00:00:00+00:00. No optimizer or provider dispatch exists in this harness.

Predeclared engineering qualification target: PRIMARY must score8/8 at each budget
(the unchanged90% threshold rounded up for eight cases),8/8 conforming JSON answers,
2/2 correct abstentions,zero forbidden outputs,provider errors,truncations or actual
input-cap overruns. Missing/error/non-fit slots stay in denominators. CONTROL is a
diagnostic comparator,not a primary release gate: publish its complete score and
paired changes at both budgets,including regressions. This is a **new** target
allocation,not a retroactive waiver of live001's failed every-condition target.
Owner has not accepted these targets or approved default-policy adoption.

Report exact answer match,JSON conformance,correct/wrong abstention,forbidden-output
incidence and source-literal retention separately. Exact match uses the parsed
answer string with no casefold,NFKC,whitespace trimming or hyphen substitution.
Canonical JSON escaping may decode to the same exact string. Malformed JSON cannot
earn correctness;forbidden sentinels are also searched case-insensitively in raw
output so a malformed response does not hide an attack. This is a conservative
substring diagnostic,not semantic security detection. Retention reads actual
rendered WINDOW/RETRIEVED fragments at designated sources,with exact substring
matching;conflicts require both statements,no-answer retention is not applicable.
Report actual/estimated input ratios separately from cap violations;no exact
provider-budget guarantee follows from tokenizer estimates.

## Evidence and execution boundary

`scripts/c09_qualification.py` verifies a frozen manifest binding its own bytes,
this protocol,case bytes and complete runtime identity. Ground truth is evaluator
only: assembly receives allowlisted scenario fields,never truth. Preparation binds
every request hash and includes the system contract's token cost. Reproduction
must be identical;bad/missing resources or runtime drift fail closed.

The only response importer is explicitly TEST_ONLY: it checks preparation and
request hashes,duplicate/unknown slots,strict envelope fields,errors and missing
answers. Even perfect supplied answers remain **answer_quality=NOT_EVALUATED**.
It cannot create live evidence. No .env access,provider import,network,ledger writes,
retry,old claims modification or existing artifact edits. Local prepared requests
are not evidence of provider schema-mode support;this plan uses prompt instructions
and strict parsing,not automatic JSON schema enforcement by a provider.

Future proposal,**not authorization**: maximum32 new Groq20b requests on the original
account/current key,256 output each,temperature0,reasoning low,no retries or paid
usage,shared accounting and immutable per-slot receipts. A separately frozen live
dispatcher must first bind this reviewed plan and prove one-attempt/uncertainty/
quota handling offline. Live001's script/32 consumed claims remain untouched.
Request new owner approval only for this exact new budget;stop on error,uncertain
usage,quota exhaustion or freeze drift. Proposed maximum input+reserved output
budget70,592tokens (16×900 +16×3000 +32×256);this is not a billing guarantee or quota
availability claim. Provider calibration can exceed estimates;use conservative
admission in any future dispatcher. Current increment makes **zero API calls**.

Commands (from workspace, installed0.9.2 environment):

```sh
.venv/bin/python scripts/c09_qualification.py prepare
.venv/bin/python scripts/c09_qualification.py score-test path/to/test-only-responses.json
```

Output is JSON on stdout;the harness never overwrites saved reports or artifacts.
Owner must review cases/targets;any requested change becomes a new frozen version.
