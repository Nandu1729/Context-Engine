# C11 — diversity candidate evaluated and rejected

2026-10-03,D106. Completed one fixed lexical-diversity experiment and broader
development check. Decision:REJECT this candidate for adoption. Keep working
core0.9.6 and application behavior unchanged. A safe retrieval repair is still open.

## Implementation

Research-only `scripts/retrieval_diversity_candidate.py` retains BM25 relevance and
adds a fixed redundancy penalty based on lexical term overlap. It favors distinct
passages without deleting repeated source events or rewriting text. This is an
MMR-inspired lexical experiment,not semantic retrieval. The
[synthetic protocol](C11_DIVERSITY_PROTOCOL.md) links the original research and fixes
weights/tie-breaking/budgets before results;no parameter sweep was performed.

Process-local layer replacement is confined to an offline single-threaded runner
and restored on exceptions. It is NOT safe concurrent service integration. The
original layer also executes for validation;no speed/cost saving is claimed.
Separate configuration identity binds candidate script/protocol. No new packages.

## Synthetic gate passed,but broader check failed

All eight synthetic conditions fit and reproduce baseline request hashes.
Single facts stay1/1;direct event cases stay3/3;paraphrase events improve0/3→3/3 at
both900/3000. Missing evidence remains NOT_APPLICABLE,not verified abstention.
Six conditions displace baseline retrieved intervals. Synthetic success alone
does not justify adoption or establish model quality.

After fixing a [separate development protocol](C11_DIVERSITY_DEVELOPMENT_PROTOCOL.md),
executed35 existing development cases ×2 budgets,date-aware recovery-OFF. No held-out
cases,no changed prompts/labels/budgets,no model generation. Labels enter only after
assembly. All70requests fit;WINDOW/system/question unchanged;zero finalizer drops.

| Measure |900|3000|
| --- | ---: | ---: |
|Baseline complete marked messages|19/56|18/56|
|Candidate complete marked messages|10/56|10/56|
|Cases improving complete-message count|0|0|
|Cases regressing complete-message count|9|8|
|Conditions losing retrieved source spans|27/35|25/35|
|Lost baseline retrieved characters|6,626|6,554|
|Aggregate estimated input-token change|+165|+65|
|Largest candidate request|885|2,998|

Regressed source rows at900:16,49,105,159,210,263,346,392,410. At3000 the same list
except105. Known106/262 remain0 complete marked messages;no answer-quality repair
can be claimed. Complete-message retention is not answer-span recall or a model
accuracy score. Unannotated text loss is not assumed harmless.

This defeats the no-regression requirement. Reject based on the full fixed
comparison,not whether the small synthetic example looks better. Do not ship,
expose through sample_app,retune under this identity or renew model calls to mask it.

## Evidence and verification

- Synthetic output:`output/retrieval-diversity-001.json`;baseline unchanged.
- Development plan/results:`output/private/retrieval-diversity-review-001/`.
- Candidate SHA256:`a17348ea627b95be2ce60cb37b958a3d26376ff856c1c5fafeec79395bab608b`.
- Original protocol SHA256:`eeb48dc7ccbbfec7b8ec64a0cc63f0fb13fc621fdbe3b4c3955ea4ed6169c175`.
- Development report SHA256:`7cdf58643283d724a78bee00ac04d99fb72fbf0fa0cbcd2aba6aa84a8af845ff`.
- Candidate/protocol/runtime and all recorded input/label/assembly/split/helper
  hashes checked before/after. Core stays
  `304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.
- 152focused tests PASS2.41s:21candidate/runner checks,13probe checks and118existing
  layer/pipeline/recovery checks. Cover diversity/ties,rejected candidates,overlap,
  tight/zero budgets,source/index/deletion checks,cancellation checkpoints,restoration,
  displaced intervals,exclusive output and continuation guards. Saved synthetic
  report reproduces exactly offline. Initial2tests caught a wrong helper call
  signature;fixed before experiments. Frozen artifacts were not rewritten.
- No credentials,provider or ledger accessed;zero new inference calls. Original
  downloaded dataset not reopened or altered;converted development files read-only.
  No70held-out cases used,no full-suite/remote CI rerun,deployment or acceptance.

## Next boundary

Final verification:8 additional project-memory tests PASS0.90s (160focused total);
Ruff/format/source/link/index/whitespace checks PASS,hot memory889/900words. Final
manifest audit confirms all recorded files unchanged and70report rows bound to plan.

The local connected demo is already complete. This candidate review is complete;
C09/C11 quality and C12 production gates are not. Keep the stronger existing
baseline. Do not spend on cosmetic demos or retune this failed candidate.

A future research step should address semantic relevance rather than lexical
redundancy alone,with explicit local-model/dependency/latency constraints and the
same fixed no-regression evaluation. That is a new candidate,not an approved
provider budget or an implemented feature. Owner need not download another dataset
or manually grade unfamiliar conversations to finish this engineering review.
