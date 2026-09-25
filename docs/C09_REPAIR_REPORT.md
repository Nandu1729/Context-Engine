# C09 repair001 — offline0.9.2 increment

2026-09-23. Implemented and verified;**C09 remains ACTIVE**,not owner-accepted.
No new inference calls or account/ledger changes. Old live001 score stays8/32.

## Delivered

- Opt-in `RetrievalConfig(recover_capped_window=True)` searches original chunks
  missing from CAP-shortened messages that are still selected in WINDOW. Exact
  source-message comparison suppresses fully represented chunks;unchanged messages
  remain excluded. Partial boundary overlap is allowed,not arbitrarily cut away.
- Source range/hash/revision/scope validation,shared WINDOW planning,chunk overlap
  suppression,top-k,reserves and final full-request accounting remain enforced.
  Finalizer requires explicit opt-in for any retrieved WINDOW source and rejects
  a fully represented chunk. Original histories are unchanged.
- Default remainsFalse,matching PRD§13's old-history-only retrieval. This is a
  deliberate optional SDK extension,not silently enabled for the service/CLI or
  promoted as a universally better production policy. Config identity changes may
  require reindexing;old artifacts/runtime are not migrated in place.
- Optional provider-independent [AnswerContract](ANSWER_CONTRACT.md) generates
  output instructions/schema and strictly validates a single JSON answer string.
  Text,ASCII identifier and canonical integer kinds;exact UNKNOWN abstention;
  bounded input;no repairing prose,identifier glyphs,duplicate keys or malformed
  JSON. A well-formed answer may still be factually wrong:conformance is not truth.

## Verification

`.venv/bin/pytest -q --tb=short`: **970 passed**,2 existing service dependency
deprecation warnings,in153.94s. Includes57 new development regressions and218 C09
tests overall. Focused repairs/layers/pipeline:118 PASS in0.69s.

Development regression:the synthetic QZ-681 middle fact is absent by default but
recovered under opt-in at700/900/3000 budgets,with unchanged WINDOW membership,
protected system/question and valid estimated caps. These are three settings of
one constructed case,not independent quality measurements. Additional checks
cover full/partial duplicate chunks,message identity,forged provenance,index drift,
zero reserves,persisted-memory parity,deletion and generated budget variations.
Parser tests cover exact Unicode preservation,ASCII-hyphen rejection,integers,
duplicate/malformed/oversized JSON,control-bearing values and sanitized errors.

Ruff,scoped formatting,lock and diff checks PASS. Offline wheel/sdist build PASS.
Clean installed wheel in `/tmp/context-c09-092-wheel.JQzUPT` verifies version,source
freeze,optional-import isolation and parser. Installed process-backed loopback HTTP
demo PASS:authentication,tenant separation,export denial,API/SDK equivalence and
content-free audit;zero external/inference calls,no persistent server.

New package sourcefreeze:
`298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc`.
Package/lock advanced0.9.1→0.9.2;third-party dependency versions unchanged. Default
old-history exclusion tests were preserved,not weakened to allow the opt-in policy.

## Historical evidence preserved

Before edits,installed the archived0.9.1 wheel with exact dependency pins into
`output/private/c09-frozen-env`. Byte-identical runner/protocol audit copies and
dependency pins are in `archives/c09-live-001/`;prior archives unchanged.
After0.9.2 edits,the frozen environment reproduced the entire live001 report
byte-for-byte with sockets disabled. No new provider request or old-score rewrite.

Use the preserved environment for old evidence:

```sh
output/private/c09-frozen-env/bin/python scripts/c09_live.py status
```

The evolving `.venv` intentionally fails live001's source-identity check. Never
change that guard,refreeze the old experiment or reset its completed32-call journal.
Unit tests of the external runner use explicitly TEST_ONLY evolving-package
fixtures;they do not rebase the actual live001 evidence.

## Remaining work

S11 is mitigated only when the new mode is explicitly selected and relevant chunks
rank/fit. Default behavior and tight-budget/lexical-retrieval limits remain.
The answer contract is not automatically wired into provider calls;actual model
compliance and improved quality remain **NOT_EVALUATED**. S12 hard-token guarantees
and broader operational/independent-quality qualification are still open.

Next:freeze fresh independently reviewed development/evaluation cases,explicit
primary-versus-control targets,and exact answer-contract integration. Review that
plan before approving a new bounded live-call budget. No C10 migration,changed
release targets,default-policy adoption or owner acceptance is inferred.
