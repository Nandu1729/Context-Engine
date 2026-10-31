# C11 — synthetic retrieval regression baseline

2026-10-03. Completed the next offline engineering step: a reproducible eight-condition
probe built from four small synthetic cases. Working core0.9.6 unchanged. The
[specification](C11_RETRIEVAL_PROBE_PROTOCOL.md) was written before execution.

## Results

| Case | Evidence retained at900 | Evidence retained at3000 |
| --- | ---: | ---: |
|Single sensor fact|1/1|1/1|
|Three explicitly named field trials|3/3|3/3|
|Three activities, differently worded question|0/3|0/3|
|Missing purchase price|Not applicable|Not applicable|

All eight requests fit their estimated budgets;original histories remain unchanged.
The paraphrase conditions fail their evidence target. These failures are retained,
not skipped or converted to passes. The missing-evidence case does not establish
that a model would abstain. No model answers were generated or graded.

This small author-created set makes the observed wording-gap problem reproducible
without opening the private dataset or making provider calls. It is not an official
benchmark,independent evaluation or proof of a universally correct diagnosis. The
direct/paraphrase cases change source wording as well as question wording,so their
contrast is not a controlled measure of paraphrase sensitivity.

## Delivered

- `scripts/retrieval_quality_probe.py`:fixed cases,network-disabled public SDK
  assembly,post-assembly evidence scoring,source-slice validation and exclusive
  metadata-only export. No new packages,providers or production defaults.
- `tests/test_retrieval_quality_probe.py`:diagnostic correctness tests,including
  gap-aware interval coverage,source validation,system/question exclusion,wrong
  source exclusion,annotation mismatch,deterministic real assembly,and no overwrite.
- `output/retrieval-quality-probe-001.json`:saved baseline with per-event coverage,
  request hashes,script/fixture identities and runtime information. Preserve it.

The probe prints the saved results with this optional read-only command:

```sh
uv run --locked --offline python -m json.tool output/retrieval-quality-probe-001.json
```

To regenerate in memory: `uv run --locked --offline python -m scripts.retrieval_quality_probe`.
Do not reuse the existing output path;exclusive creation rejects overwrites.
Exit0 means diagnostic execution completed,not that all quality targets passed.

## Next boundary

Verification:13 probe tests plus8 project-memory tests PASS (21total,1.78s);scoped
Ruff,formatting,source/link/index and whitespace checks PASS. Saved report reproduces
exactly offline;core hash unchanged. No full-suite or remote CI rerun. Test success
checks the probe's correctness,not success of its deliberately reported quality failures.

The connection work and this diagnostic baseline are complete. A repair needs a
separately identified retrieval candidate that improves missing-event coverage
without losing baseline evidence or violating source/budget limits. Retain single
facts,direct-event cases and missing-evidence controls. Examine displaced source
text,not just aggregate counts. Do not tune using the held-out set or add dataset
answers to retrieval. No such candidate was adopted during this step.

No private dataset,credentials,ledger or held-out data accessed;zero provider calls.
All exhausted live budgets remain exhausted. C09/C11 remain ACTIVE;this diagnostic
is not release approval or replacement for future paired model-quality evidence.
