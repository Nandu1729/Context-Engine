# Synthetic retrieval probe v1 — fixed diagnostic specification

2026-10-03, written before executing this probe. Offline engineering under D086/D104;
no new inference authorization, adoption or release gate changes.

## Scope fixed before results

Four author-visible synthetic cases, each at900 and3000 estimated input tokens:
single sensor fact;three dated completed field trials with direct wording;the same
three activities with differently worded query;missing sensor purchase price.
The paired event cases differ in source wording as well as question,so they are
not a controlled causal estimate of paraphrase sensitivity. They are regression
fixtures,not population accuracy evidence or copies of LongMemEval questions.

Each history has zero/one/three old evidence messages,four planning distractors,
and120recent maintenance messages. Each expected event is one short complete source
message including its date. All source turn timestamps share the fixed assembly
time;event dates are in text. This does not test automatic relative-date resolution.
Default CAP/retrieval behavior,280retrieval reserve,zero summary reserve;unchanged
core0.9.6. No embeddings,external services,query expansion or parameter sweep.

Only history,question,scope,pins,budget,system policy and fixed time enter assembly.
Expected-source markers are applied afterward to actual WINDOW/RETRIEVED data only.
Retrieved offsets/text must match originals;adjacent spans may cover an event,
unrepresented gaps may not. Question/system text and provenance alone never count.

## Criteria and interpretation

For the three answerable cases,report every expected event separately:1,3,3events
respectively. Full expected evidence is the desired condition,not an asserted
current capability. Show failures unchanged. Missing-evidence has no expected
event and must be NOT_APPLICABLE,not a vacuous successful answer/abstention result.
Without a model,answer accuracy,temporal reasoning and abstention are NOT_EVALUATED.

Every request must fit its estimated budget;original history must remain unchanged.
Python sockets disabled throughout execution;cached tokenizer required. Output
contains metadata,coverage counts,request/fixture/script/runtime identities only.
Optional output file uses exclusive creation and cannot replace prior evidence.
Runner exit0 means diagnostic execution completed,not that every evidence target
passed. No new mandatory CI quality gate is introduced by this diagnostic.

Before testing any candidate,retain this baseline and specify its identity. Require
no baseline-retained event lost,no budget/source regression,and examine all displaced
source spans separately. Do not silently retune these fixtures to make results green.
These eight conditions are necessary engineering checks,not sufficient approval for
production adoption or live comparison. Existing35development/70held-out partition,
frozen experiments and provider budgets remain unchanged.
