# Diversity candidate v1 — bounded offline experiment

2026-10-03. Fixed before execution. Scope:isolated research candidate,not a change
to0.9.6 or the saved probe/union/live runners. No inference or dependencies added.

Hypothesis:redundant high-ranking passages occupy a fixed retrieval reserve;favoring
distinct passages may retain more events. This is a lexical diversity intervention,
not semantic understanding,negation reasoning or a synonym repair.

Method inspired by [Goldstein and Carbonell's MMR paper](https://aclanthology.org/X98-1025/):
retain existing eligible chunks/query/BM25+ scores. At each accepted selection rank
remaining chunks by0.5*(BM25/max positive score)-0.5*(largest term-set Jaccard similarity
to an already selected chunk). Initial redundancy0;tie-break by chunk ID. Fixed0.5,
no parameter sweep. Score threshold,top-k,source validation,overlap suppression,
WINDOW policy and full-block token checks stay unchanged. Duplicates are penalized,
not deleted or treated as one historical event. Content/dates are never rewritten.

Exactly the frozen four synthetic cases ×900/3000,280retrieval reserve. Run unchanged
baseline to recover source spans and require its request hashes match the saved
probe001. Labels enter only after assembly. Record all event gains/losses,estimated
tokens,request identities,and every lost baseline retrieved interval. Verify WINDOW,
system and question unchanged. Output metadata only,exclusive creation.

Continuation gate:all baseline-retained events preserved,all three paraphrase events
retained at both budgets,and all budget/source/required-content checks pass. If that
gate fails,stop:this candidate is rejected for further development testing;no private
dataset or held-out access,no parameter tweaks or automatic alternative experiment.
Even if it passes,source-span losses preclude automatic adoption. Broader offline
development comparison and separately approved model-quality evidence are required.

Use isolated single-thread process-local layer substitution only;restore it even on
exceptions. Separate config fingerprint binds candidate code/protocol. No installed
SDK/service wiring or production use. Cached tokenizer and Python socket denial;
no .env/provider/ledger access. Emit DIAGNOSTIC_ONLY,not a misleading test-suite PASS.
