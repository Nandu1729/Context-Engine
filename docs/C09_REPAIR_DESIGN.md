# C09 offline repair design —0.9.2

2026-09-23 continuation after live001. This is development/regression work,not a
new live experiment or unseen-quality qualification. No further API calls.
Preserve all live001 scores,its0.9.1 wheel/execution environment,script,protocol and
receipts. The original PRD remains byte-identical.

## S11: explicit recovery of missing WINDOW source chunks

The PRD§13 searches only original turns outside WINDOW;this remains the default.
Add `RetrievalConfig(recover_capped_window=True)` as an opt-in SDK extension.
It admits original chunks from changed messages in selected WINDOW turns only when
the complete chunk text is absent from that same message's rendered working text.
Unchanged messages and fully present chunks stay excluded. Comparisons are exact,
per source-message identity,not another message with coincidentally matching text.

Chunk IDs/ranges/revisions/content hashes still refer to authorized originals.
Do not splice arbitrary pieces or normalize source text. A boundary chunk can
partially overlap visible text;existing chunk-to-chunk overlap suppression,top-k,
retrieval allocation and full-request budget checks remain unchanged. Shared WINDOW
membership is not expanded or replanned to spend leftover budget. The finalizer
revalidates sources and permits a WINDOW source only under explicit opt-in and
only if its chunk is not already fully represented. Persisted-index and freshly
chunked results must agree. Scope/deletion/cancellation invariants still apply.

Adding a configuration field changes new-version configuration fingerprints;
old persisted indices may require safe reindexing. No automatic database migration,
default-policy change or production recommendation is inferred from local tests.

## S13: exact machine-answer contract

Add an optional provider-independent JSON answer contract,not an automatic scorer
relaxation or provider call. One object with exactly one `answer` string. Reject
extra fields,duplicate keys,Markdown wrappers,trailing prose,malformed/oversized
documents,empty/multiline/control-bearing values and invalid Unicode. Never trim,
casefold,normalize Unicode,replace hyphens or extract answers from prose.

Kinds:text,ASCII identifier,canonical integer-string;all allow explicit `UNKNOWN`
abstention. Generate a bounded JSON schema and matching output instructions without
ground truth. Caller must explicitly include instructions in its budgeted system
policy;core assembly never rewrites system text. Parsing validates shape,not truth,
evidence provenance,authorization or safe actions. No schema-mode provider integration
or live improvement is claimed until separately implemented/measured.

## Evidence boundary

Use newly authored development regressions for changed/unchanged messages,repeated
text,partial chunks,Unicode,malicious markers,source integrity,zero reserves,tight
budgets,persisted-memory parity and exact-value parser behavior. Any reinspection of
the exposed heldout-v1 corpus is regression evidence only. A later qualification
requires a fresh independently reviewed corpus,predeclared primary/control targets,
model/generation contract and separately approved bounded inference budget.
