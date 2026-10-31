# C11 — multi-event retrieval diagnosis

2026-10-03. Read-only offline diagnosis of two previously failed development cases.
The application connection already works. This investigation addresses missing
evidence, not connection setup. No core change, new candidate, model call, dataset
download, held-out evaluation or default adoption.

## Confirmed mechanism

Both date-aware recovery-OFF requests at3000 estimated input tokens reproduce
their saved request objects exactly. Reconstructing BM25+ ranking and selection
also reproduces the actual selected chunks exactly. The retrieval allocation is
still280tokens; increasing the overall request allowance does not automatically
increase this reserve.

| Development row | Selected ranks | Best ranks of marked event messages | Outcome |
| --- | --- | --- | --- |
|106, multi-session acquisition count|1,3|5,6,16,57,371|All five rejected by the remaining retrieval budget|
|262, temporal sports-event order|1,2|213,472,543|All three rejected by the remaining retrieval budget|

All eight marked messages are outside WINDOW and eligible for retrieval. Each has
one ranked chunk; none is selected. No finalizer drops occur. These omissions are
not caused by the overlapping-chunk suppression seen in row454, nor by the
capped-WINDOW recovery toggle. The top-k ceiling is4, but only2chunks fit each
request, so simply increasing top-k is not a demonstrated remedy.

For106, the second selected chunk shares only `i`, `last`, `the`, `two` with the
question. For262, both selected chunks share only `i`, `in`, `of`, `past`, `the`,
`three`, `to`; none shares `sports`, `events` or `participated`. The marked sports
messages also overlap the query only on common words. This supports a lexical
relevance/wording-gap diagnosis; removing common words alone would not create the
missing semantic match. It is not proof that a particular replacement ranker works.

The280-token budget then locks in the earlier selection. More output tokens or a
stronger answer model cannot be assumed to recover events never supplied. Correct
abstention from incomplete context remains preferable to unsupported guessing,
even though the end-to-end dataset task fails.

## Verification and provenance

Two unchanged assemblies, with Python socket connections disabled. An observation
wrapper called the original `RetrieveLayer.apply` unchanged and retained its input
and result in memory. Ranking was then reconstructed using the original window
eligibility, lexical tokenizer, BM25+ parameters, score/chunk-ID ordering, overlap
rule, full-block budget checks and top-k limit. Reconstructed selection equalled
the actual `retrieved_chunks` tuple in both cases. No runtime/source files edited.

Labels were opened only after assembly/ranking, to locate annotated messages;
neither labels nor reference answers entered ranking or selection. Both rows were
checked against the existing development partition. No held-out case was loaded.

Source files reside under `output/private/longmemeval-review-001/row-NNN/`.
Input, label and saved-assembly file hashes were checked before/after; all unchanged.
Canonical request SHA256 values:

- Row106: `d6d0cb5494490976b2e97c248ef43195556a108c918f6bbb6217a300b3b23221`.
- Row262: `abf51ebe488b031f78d97d1db71062a98801f9ae720857b761d3da2ea2775ef2`.

Core hash verified:
`304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.
No provider, credential or ledger access. The historical failed answers remain
unchanged. This is post-hoc development diagnosis, not independent quality scoring.

Documentation verification:8 project-memory tests PASS0.88s;source/link/index and
whitespace checks PASS,hot memory889/900words. No full-suite or remote CI rerun.

## Next engineering step

Keep the working application and existing candidate unchanged. Before implementing
another candidate, specify a separate offline relevance experiment with synthetic
multi-event/wording-gap cases, distractors, dates and strict source/budget checks.
Measure event-span coverage and displaced evidence, not just complete-message
counts. Include single-fact and abstention controls; freeze criteria before the
development comparison. Do not inject dataset answers, marked-source IDs or a
case-specific synonym list into retrieval, or automatically add vector services.

Only a candidate that clears those checks should proceed to a separately approved
paired model-quality test. No additional inference is authorized now. Local demo
integration is complete; C09/C11 quality gates and production acceptance remain open.
