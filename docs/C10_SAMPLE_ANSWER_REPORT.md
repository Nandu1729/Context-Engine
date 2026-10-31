# D105 — one-request application answer completed

2026-10-03. Owner approved exactly one model request after connecting the existing
LongMemEval development input. The request completed successfully;authorization is
now exhausted. No retries,second example or larger-output rerun is authorized.

## Result

- Input:development row49,existing baseline mapping,recovery OFF,900estimated
  input allowance,unchanged prepared request.512source turns selected into892
  estimated input tokens;not all source content is retained.
- Model:`openai/gpt-oss-20b`,temperature0,reasoning low,max256completion tokens.
- Status:`success`,finish reason`stop`,nonempty answer,one provider attempt.
- Actual usage:827input+88output=915tokens. Output includes65reasoning tokens;
  no raw reasoning was requested or saved. Input stays below900;output below256.
- Configured cost:0microusd under the existing confirmed free-tier policy.
  This is local accounting,not independent verification of provider billing.
- Post-dispatch assistant comparison:answer names the same bulb as the separate
  reference,without extra unsupported specificity. Main answer consistent with
  reference;not literal string equality,official LongMemEval scoring,independent
  review or evidence of broad answer quality.

Reference labels never entered preparation or dispatch. Reference read only after
the returned answer was recorded. The full response remains in the private receipt.

## Safety and preservation

Separate runner and [protocol](C10_SAMPLE_ANSWER_PROTOCOL.md) frozen before dispatch.
Reused unchanged read-only/accounting/preflight utilities from longmemeval_live,
not its historical initializer,dispatcher or report. No historical script changed.
Read-only authenticated model list confirmed exact model active. Local accounting
had no unresolved holds and enough quota for the conservative1862token admission.
The model list does not expose an authoritative billing tier or upstream quota balance.

Durable exclusive claim was written before the single dispatch and ledger-bound
receipt after settlement. Every721historical attempt row hash remains unchanged.
Shared account now722attempts/1,152,510charged tokens,zero unresolved reservations.
Original corpus hash,input hash and0.9.6source freeze unchanged. No held-out use,
account fallback,quota reset,prompt repair,model retry or private-data publication.

Completed-run resume verified with Python sockets disabled and credential loading
forbidden:zero additional calls,identical ledger. Failed/uncertain claims also never
resend in synthetic tests. Do not delete/reset claims or run under a new identity
to reuse this approval.

## Verification and identities

20new single-call safety tests plus23existing LongMemEval runner tests:43PASS2.43s.
Eight brain tests PASS0.87s before freezing;51focused tests total at dispatch.
Scoped Ruff lint/format,source/link/index and whitespace checks PASS. No full-suite
or remote CI rerun;the safety tests use synthetic transports and temporary stores.

- Execution identity:`be4b225109296473898b2221f72d129db98e587cfadc38f881f26d412edc2226`.
- Runner SHA256:`b9311829919b55b1c3ea9033f199883c411e12f721d0074525adc11ab2c6ce01`.
- Protocol SHA256:`96cb8be5bddcc3385f599decfaaed929d805b75cea62f0c4f97f1d7ad471b382`.
- Receipt SHA256:`7126922a161e6418434b06299218befd7ec7c7c52963265d1e4ad44a2ee9a42c`.

Evidence:`output/private/sample-answer-001/manifest.json`,exclusive claim and
`receipt.json`. Existing private directory permissions retained;no credentials
or full dataset added to reports. The frozen runner/protocol must not be edited
under this identity.

## Handoff

To display the saved answer without another request:

```sh
uv run --locked --offline python -m scripts.sample_answer status --show-answer
```

The ordinary `sample_app.py` remains offline;it does not gain automatic live calls.
Data→engine→one model answer is demonstrated. D105 is exhausted and enterprise
C09–C12 gates remain unchanged. Broader quality evaluation or more generated
answers requires a separately reviewed scope and bounded approval.

Final post-report brain verification:8PASS0.87s;source/link/index/whitespace checks
PASS,hot memory886/900words. Frozen runner/protocol unchanged after dispatch.
