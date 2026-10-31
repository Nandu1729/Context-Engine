# Current state

Updated: 2026-10-31

## Objective

Build the context engine with measured quality/cost and owner checkpoints.
D108/D109 focus:developer-ready SDK(stage1 launch,stage2 adoption);no SaaS frontend.

## Verified facts

- Workspace: `/Users/nandyyy/Project/Context Engineering`. All73 PRD sections mapped;
  sourceSHA256 `1abb616cbd347aa8fea8064feb93af45727060acdb3e6a91708f4ee4ae39b43c` unchanged.
- C00–C08 READY, not owner-accepted. Five-layer core, provider/replay/quota,
  SQLite durable memory/deletion-aware restore, authenticated local `/v1` service.
- Package0.11.0(D109):`recover_capped_window=True` default;Apache-2.0;tested README;
  0.10.0 rolling summaries/strategy-eval kept. 0.10.0 wheel/freeze in
  `archives/c11-recover-default-0110`;code hash `1b40824e…4a91`. Lock patched
  (certifi,urllib3,PyJWT,Pillow;uv audit0);old dep wheels in archives/runtime-deps-pre-0110.
- strategy-eval(offline,frozen31 facts):combined31/31@900/3000;combined_no_recover
  29/31,19/31(S11:CAP trims WINDOW facts);retrieval+window31/31. Retention only.
- C06 complete at snapshot249:primary29/31 correct,95.18%estimated reduction.
  C09 live qualification FAIL(PRIMARY14/16);all inference budgets exhausted.
- Earlier evolution:0.9.2 recovery/AnswerContract,0.9.3 admission schema2,0.9.4–0.9.6
  Windows ACLs. All prior wheels/freezes archived;historical runners reject new code.

## Working decisions

- Owner controls acceptance,inference spend,publishing and defaults. T2 accepted(D109);
  T5 Postgres,T6 semantic proposed. Ask before each TestPyPI/PyPI upload.
- Preserve C06/C09/C10 archives,`.env`,private runtime;shared ledger append-only.
- Core independent of service/provider/evaluation;authorization precedes work;
  summaries/retrieval are data with provenance;no hidden model calls.

## Current checkpoint / next action

Stage1(D109/D110) done;real PyPI upload needs owner go-ahead.
Full suite1429 PASS/0 FAIL;wheel/sdist clean installs PASS. See docs/CURRENT_STATUS.
C09 ACTIVE(quality),C10 ACTIVE(operations),C11 ACTIVE,C12 BLOCKED as before.
Uncommitted work from D097–D108 remains for owner review/commit.

Live D109/D110 900-token run COMPLETE:combined31/31,retrieval31/31,no_recover29/31,
summary1/29,window1/31;2 zero-token rejections,$0. TestPyPI0.11.0 verified.
0.12.0:adapters,Inception(live smoke OK,D111),MCP stdio prototype,count cache
(247→95ms@900,481→208ms@3000);run7 1479 PASS. 0.12.0 released on PyPI+TestPyPI(D112),hashes match;PR #1 open for owner merge.
0.12.1 on PyPI(hashes match):latency67ms@900,80ms@3000,identical output;run8 1486 PASS.
0.13.0:reworded questions drop keyword retention31→3/31. 0.14.0(PyPI,D113):opt-in hybrid
retrieval(potion-8M+score fusion)3→21/31,originals31/31;run10 1522 PASS. Live D114:
keyword3/31 vs hybrid18/31 strict(21/31 lenient). 0.15.0(D115):hybrid default via
bundled int8 model,weight0.5,grading-v2;run1550 PASS. PR #1 merged(28f1649);0.15.0 on PyPI.
0.16.0(D116/D117,PR #3 feat/chat-memory-longmemeval):ChatMemory/AsyncChatMemory,
retrieval_share0.4,diverse_turns(ChatMemory default),examples,LongMemEval-S@3000:
core hybrid78.5%→ChatMemory94.2%(all45.9→79.3%). PR #3 merged(c3a214d);0.16.0 on PyPI.

## Open risks

- Synthetic corpus+LongMemEval evidence recall only;no real-world answer accuracy or injection claim.
- Token estimates:12 historical overruns,max actual/estimate1.781321.
- Extractive summaries add no retention on frozen corpus;model summaries unmeasured.
- OS scheduling/reaping,global limits,production load/IdP/TLS/audit,per-tenant rate
  limits unqualified.
- Resume by reading disk memory;drift remains possible.
