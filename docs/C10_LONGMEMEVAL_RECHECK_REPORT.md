# LongMemEval saved-answer recheck

2026-09-29, D102. Assistant review of all14 saved D100 responses, their dataset
references and emitted context. No new inference, assembly experiment or core change.
The owner worksheet still has14 blank ratings; these are assistant judgments,
not owner approval, independent grading or an official LongMemEval score.

## Findings

| Development category / source row | Recovery OFF | Recovery ON | Main observation |
| --- | --- | --- | --- |
| Abstention /232 | Reference-consistent | Reference-consistent | Missing fare correctly acknowledged; a different transport fare is not substituted. |
| Knowledge update /390 | Reference-consistent | Reference-consistent | Latest location appears in a retrieved tail even though neither marked message is retained in full. |
| Multi-session /106 | Incorrect abstention | Incorrect abstention | None of the five marked messages supplying the acquisition events reaches the request. |
| Assistant history /454 | Incorrect abstention | Incorrect abstention | Correct source retrieved, but the answer-bearing span falls between selected chunks. |
| Preference /156 | Incomplete / partial | Incomplete / partial | Both hit256 output tokens; some relevant suggestions, but weak personalization and missing preference context. |
| User fact /49 | Main fact reference-consistent | Reference-consistent | OFF adds a color-specific description not established as an exact product variant. |
| Temporal reasoning /262 | Incorrect abstention | Incorrect abstention | All three marked event messages absent; ordering ability is not isolated by this test. |

Each arm has3 main-answer reference-consistent responses,3 incorrect abstentions
against the dataset and1 incomplete/partial response. The user-fact OFF caveat
prevents treating this as an all-claims-grounded score. Missing evidence makes the
abstentions understandable from the supplied request; the end-to-end task still
fails. Do not encourage unsupported guessing to improve this count.

The original literal-equality result remains0/7 per arm and original semantic fields
remain PENDING. Paraphrases explain several literal mismatches. Five pairs have
identical payloads; only two test different recovery payloads, and neither changes
the judgment above. No evidence here supports adopting recovery by default.

## Confirmed chunk-selection defect

For row454, replaying lexical ranking from the saved date-aware OFF input reproduces
these ranks within the same source message. Character offsets are zero-based,
half-open. No reference answer was supplied to the ranker.

| Rank | Source span | Saved selection | Contains requested count |
| ---: | --- | --- | --- |
|1|[280,640)|Selected|No|
|2|[0,360)|Not selected; overlaps rank1|No|
|3|[560,920)|Not selected; overlaps rank1|Yes|
|4|[840,1200)|Selected|No|

The requested count is at[793,804), inside the unrepresented gap[640,840).
`RetrieveLayer.apply` skips overlapping candidates before evaluating their budget
fit. Rank3 is therefore skipped after rank1 is selected, despite containing novel
answer-bearing text. This is a confirmed selection mechanism, not proof that simply
adding rank3 would fit the280-token retrieval reserve or improve general accuracy.
The source is outside WINDOW, so capped-WINDOW recovery does not repair this gap.
This case evaluates recall of a historical assistant statement, not its scientific
truth. No medical claim has been independently verified.

Other failures need separate treatment: multi-session aggregation and temporal
ordering require several relevant events, while the preference request loses one
important preference message and also truncates. No finalizer drops were recorded
in these examined cases. Increasing output alone is not an established remedy.
Whole-message retention is not answer-span recall: row390 succeeds with0/2 complete
marked messages, whereas row454 retrieves the correct source but misses its answer.

## Evidence and limits

- Original [live report](C10_LONGMEMEVAL_LIVE_REPORT.md), runner, protocol, receipts,
  requests, source dataset, split and core remain unchanged.70held-out cases unused.
- Network-disabled report reconstruction matches the saved report. Ledger remains
  721attempts/1,151,595tokens, with no new calls or accounting writes.
- Final verification: original report/worksheet hashes and all14 slot mappings
  PASS;8 project-memory tests PASS0.87s, index/link/source checks and whitespace
  checks PASS. No full-suite or CI rerun;no implementation changes to qualify.
- Private per-response assessment: `output/private/longmemeval-live-report-001/assistant-review.md`.
  Owner worksheet remains separate and unchanged.
- This is post-hoc development diagnosis by the implementing assistant, not a new
  frozen evaluation or independent estimate of population accuracy.

## Next work, in order

1. Owner checks just the two judgment-sensitive examples first: preference row156
   and the extra specificity in user-fact row49. Record disagreement in the original
   worksheet; no terminal commands, credentials or API calls required.
2. Scoped offline repair should first reproduce overlap suppression with a synthetic
   non-benchmark example, then assess novel-span selection under the unchanged token
   budget, source validation, deduplication and deletion guarantees. Preserve0.9.6
   evidence and version any candidate separately; do not patch the frozen runner.
3. Review multi-event relevance separately on the existing development set. Keep
   held-out data untouched; never feed reference answers or marked-message labels
   into retrieval. Agree on criteria before any subsequent comparison.

No repair or expanded experiment was implemented during this review. D100 is
exhausted; further provider work requires a new bounded approval. C09 quality and
independent review remain open; C10 ACTIVE and C12 BLOCKED.
