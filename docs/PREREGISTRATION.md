# Evaluation v1 — owner review

Status: **owner-approved on 2026-09-13 (D047)**. The owner explicitly confirmed both the targets below and Free-plan-only live testing with $0 paid spending. Approval is not evidence that the targets have been achieved or that C06 is complete. The protocol was declared before C04 measurements and approved before live inference. This document summarizes the authoritative [protocol JSON](../src/context_engine/evaluation/data/protocol.json).

## Approved acceptance targets

For A5, the primary PRD model and a 900-token estimated-input budget:

- All 31 probes fit.
- At least 28/31 retain the answer at its declared source in the fitting prompt.
- At least 27/31 produce a correct answer; publish both all-planned and completed-response denominators.
- At least 90% median estimated-input reduction versus the same probes' raw requests.
- Zero truncated generations. Invalid, interrupted, unapproved or mocked runs cannot pass quality acceptance.

These are engineering gates, not established performance or population-level guarantees. Separate authorization is limited to the owner's confirmed Free-plan account and $0 paid spending; actual account quotas must be configured before execution. No paid upgrade is authorized.

## Frozen experiment

The [benchmark guide](BENCHMARK.md) describes the 100-turn incident corpus, 31 source-linked facts, six variants A0–A5, budgets 900/3,000 and PRD model identifiers. Primary pins are empty; a separate fixture tests durable pin retention. Summary content is fixed background with no answer aliases. A2/A3 may tie; that is an expected property of this corpus, not grounds to change the experiment.

Generation defaults are temperature 0, low reasoning effort and 256 completion tokens. These are recorded defaults, not verified live-provider compatibility. The tokenizer profile, CAP settings, BM25+ variant/chunking, grading policy and source-age zones are frozen together. C05 must verify provider options and calibration before live runs.

Approved protocol SHA-256: `789585023df970bcfea2723b5b7994a1251f0aa512f6ee5820b8ad7353eb571c`. The sole protocol change is approval state; thresholds, corpus, generation and grading are unchanged. Original owner-pending protocol/freeze and 0.7.1 wheel are preserved under `archives/c06-free-prep/`; approval-bound package is 0.7.2.

The [freeze record](../src/context_engine/evaluation/data/freeze.json) additionally binds exact resource bytes, package source hash, Python patch version and runtime dependency versions. Each manifest includes that freeze and the full selected configuration; deterministic probe IDs bind model, budget, variant and fact to its run ID.

## Change and review rules

Record explicit owner feedback in `brain/DECISIONS.md`. Approval changes the protocol approval state and therefore its hash/run ID. Changed thresholds, grading, fixtures or generation settings require a newly versioned protocol and paired reruns; never modify a saved result to make it pass. Preserve earlier artifacts and the corresponding package for historical verification. Do not automatically regenerate the freeze during tests or validation.

The corpus is synthetic and deliberately repetitive, not a held-out real-world sample. C09 must qualify broader workloads. C04 local fit and retention checks do not establish answer accuracy, provider cost savings, production security or enterprise readiness.
