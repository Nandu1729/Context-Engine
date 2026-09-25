# C09 empty-answer diagnosis and caller boundary

2026-09-23. Offline only;105 targeted tests PASS in0.43s,including20 new checks.
No API calls,credential access,real-ledger writes,package changes or regrading.

## Finding

The five live002 empty receipts have `content=""`, `finish_reason="stop"` and
47–63 output tokens,below the256 limit. The Groq parser copies message.content
verbatim;for stop responses it does not convert null to empty or extract reasoning.
Null would fail validation. The client maps stop to transport-level success and
settles actual usage;it does not validate whether an application answer is usable.

Local regression tests reproduce that distinction through parser,client and a
temporary ledger:one empty stop completion,one charged87-token test attempt,then
caller rejection without extra requests or accounting mutation. Text is not
lost by this parser path. The evidence supports an empty final-content field at
the adapter boundary,not output-cap exhaustion or the retrieval engine deleting
a generated answer. Original raw HTTP bodies were not retained,so the upstream
reason remains unverified. Do not reconstruct an answer from reasoning or usage.

## Delivered

[Opt-in caller example](../examples/validated_answer.py) supplies `validate_answer`
and a sanitized `UnusableAnswer` error. It accepts only success/replay with a stop
completion,then rejects blank text or a malformed exact-answer contract. It returns
valid values verbatim,including UNKNOWN. It never retries,changes result status,
rewrites receipts or loses the original ModelResult/usage. Syntax is not truth.

This is a **repository integration example**,not a package/service default change
or a fix proven to make the provider produce answers. Existing0.9.2 and both frozen
live experiments remain unchanged and reproducible. Callers must explicitly use
the check;the historical provider client still uses protocol-level success semantics.

## Verification

`pytest -q tests/test_c09_answer_boundary.py tests/test_providers.py --tb=short`:
105PASS,0.43s. Covers actual five saved failures,verbatim parser behavior,null-stop
rejection,reasoning exclusion,empty/whitespace/invalid JSON,Unicode identifiers,
valid answers/UNKNOWN,replay,non-success dispositions and exact usage preservation.
Ruff check/format PASS. No redundant full-suite run under the owner's speed request.

## Remaining

C09 remains ACTIVE. Live002 stays25/32 overall,PRIMARY14/16,strict target FAIL.
Provider-side empty-content cause and independently reviewed qualification are
unresolved. Next decision is whether to authorize a narrowly bounded provider
diagnostic with sanitized response-shape metadata;not another full32-call matrix.
No diagnostic call is authorized or performed here. Any eventual production
adapter change must preserve the0.9.2 runtime first and get its own version/tests.
