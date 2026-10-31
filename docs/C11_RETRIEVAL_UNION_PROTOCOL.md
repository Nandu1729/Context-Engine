# Offline overlap-union development protocol v1

2026-10-02. One isolated research candidate, not a production/default change.
No provider calls, credentials, original corpus rewrite, deployment or held-out use.

Hypothesis: rejecting every overlapping chunk discards novel source text. Greedily
merge intersecting spans from the same validated source message, keeping exact
Unicode offsets and checking the entire proposed block against the original budget.
Reject over-budget merges without losing the previous selection. Fully covered
chunks are no-ops. Never bridge an unselected gap or merge distinct sources.

Keep BM25 ranking, lexical tokenization, chunk size/overlap, top-k stopping rule,
CAP, WINDOW, summary policy and all budgets unchanged. No answer-aware selection,
stopword tuning, query expansion, model calls or repeated parameter search.
Use unchanged0.9.6 core; candidate lives only in an offline single-threaded script.
Process-local layer substitution must restore on exceptions. Candidate diagnostics
carry a different configuration fingerprint bound to script/protocol hashes.

Before reading candidate development outcomes: synthetic tests must exercise novel
overlap, containment, adjacent/disjoint spans, Unicode, distinct sources, malformed
provenance, zero/tight budgets, indexed parity, cancellation and patch restoration.

Then execute exactly35 already-selected development cases from saved split
aab5693329fa716acd05621b4d791e508779c6e80471e22e94021d6537229279,
date-aware recovery-OFF arm at900 and3000 estimated tokens:70candidate assemblies.
Use saved baseline assemblies; no additional baseline/model reruns. Labels remain
separate until after assembly. Plan records all input hashes and candidate/runtime
identity before execution. Exclusive outputs; failures remain in denominator.

Measure paired complete annotated-message coverage, input-token differences,
finalizer drops and candidate latency. This is not semantic quality, answer-span
recall, a randomized speed comparison or total cost per useful answer. Report every
regression; no automatic adoption even if aggregates improve. Row454's known
answer-span omission is a targeted development diagnostic, not an unseen test.
Inspect that span after the fixed run; do not tune the candidate to its answer.

No full corpus or70held-out assemblies. No changes to old claims/receipts/reports,
core package, lockfile, original source or existing reviewer scripts. Broader quality,
operations, cost and release gates remain open regardless of outcome.
