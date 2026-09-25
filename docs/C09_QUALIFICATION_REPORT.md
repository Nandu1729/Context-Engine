# C09 qualification preparation —002-r1

2026-09-23. Offline increment complete for owner review;**C09 remains ACTIVE**.
No new API calls,credentials,ledger writes or default-policy changes. Package0.9.2
and sourcefreeze298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc
are unchanged. Original live001 score8/32 and C06 evidence remain untouched.

## Delivered

- [Frozen protocol](C09_QUALIFICATION_PROTOCOL.md),eight fresh synthetic scenarios,
  separate evaluator truth,and a runtime/file-bound manifest. Cases are author-visible,
  **not independently reviewed**. Owner review and live authorization are pending.
- External `scripts/c09_qualification.py`:offline preparation and TEST_ONLY strict
  JSON scoring. AnswerContract instructions now enter the budgeted system message
  in this harness. No provider schema-mode integration or inference capability.
-32 paired slots:default retrieval CONTROL versus explicit recovery PRIMARY,
  eight cases at900/3000. Exact parsed strings;no normalization or answer repair.
  Conformance,correctness,abstention,forbidden output and retention remain separate.
  Missing,error and non-fit entries stay in the planned denominator.

## Observed local evidence

[Saved preparation](../output/c09-qualification-002/preparation.json) reproduces
identically with sockets disabled. All32 requests fit their estimated input caps.

| Input cap | Default CONTROL retention | Recovery PRIMARY retention |
|---|---|---|
|900|6/7|7/7|
|3000|6/7|7/7|

The default loses the middle tool fact;recovery retains it. No-answer cases are
excluded only from retention,not quality denominators. This is exact source-literal
inspection of synthetic contexts,**not model-answer accuracy**. Total estimated
input24,504tokens;32×256 reserved output gives32,696estimated tokens. Proposed
cap-based ceiling70,592tokens is not actual usage or a provider quota guarantee.
Model accuracy,calibration,latency and cost remain NOT_EVALUATED.

Freeze identity:`c09-qualification-002-r1`.
Manifest fingerprint:`cc01c28009e178dcbe0a1ee4db053f28c2af6e8295ea0c4f2318f1943eddc9c5`.
Preparation fingerprint:`e095d6b81d420ec200b6deab8597fa0d8ab811679de83ecbf377df958b4c543a`.
Harness SHA256:`349bff1335599084e8fcd9bc0a05f2e49e1979a4d34b6e97d7d4c0b57d17e588`.

Initial002 preflight hit an empty-block decoding bug before producing a report.
The original script/manifest are [archived](../archives/c09-qualification-002-preflight/README.md);
r1 corrects only that evaluator bug and identity. Cases,targets,protocol and engine
unchanged. This is disclosed rather than silently replacing an earlier freeze.

## Verification and next action

Focused tests cover offline replay,strict conformance,truth isolation,budgeted system
instructions,forged/duplicate/stale/live records,missing/error/non-fit denominators,
empty optional blocks and preserved preflight evidence. Full run:997 passed,two
documentation-fixture failures,2 existing warnings,in162.90s. Both failures were
the missing archive README in the isolated brain-test copy;added that fixture.
The affected brain tests subsequently passed8/8. No product code failure or
weakened assertion. Final combined qualification/brain rerun:37 passed in10.21s;
no second full-suite rerun,following the owner's speed/usage request.
Installed0.9.2 wheel reproduces preparation with sockets disabled;original live001
script/protocol hashes unchanged. Lint,format,lock and diff checks pass.

Owner review:approve this fresh synthetic comparison and at most32 **new** Groq20b
requests,original account/current key,256 output each,no retries or paid usage.
Before dispatch,freeze a separate receipt-bound live runner and verify quota/stop
behavior offline;do not modify or reuse live001 claims. No independently reviewed
qualification,provider improvement,default adoption or checkpoint acceptance is
claimed by this preparation. C10 remains planned.
