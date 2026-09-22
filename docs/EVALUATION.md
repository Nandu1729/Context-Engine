# Evaluation protocol proposal

Status: C04 implemented this protocol; numeric targets were explicitly owner-approved on 2026-09-13 (D047) before live inference. See [pre-registration](PREREGISTRATION.md), [implemented harness](BENCHMARK.md) and [historical report](C04_REPORT.md). Partial live results are now recorded in [C06 progress](C06_REPORT.md); qualification remains incomplete. Owner changes require a new frozen identity; never rewrite criteria to fit observed scores.

## Fixed experiment

- Synthetic 100-turn incident history with exactly 31 planted facts and stable IDs, source turns, expected values, aliases, probe questions and age zones.
- Include the flagship Turn 82 `shard-19` probe. Approximate 17,700 raw tokens is a fixture target to measure, not a fabricated result.
- Stress input cap 900; normal input cap 3,000; reserve 256 completion tokens initially. Count complete messages and schemas.
- Baseline models and generation defaults follow the PRD; record exact configuration and observed provider metadata. Temperature zero does not guarantee identical outputs.
- Frozen summary contains broad background and no planted answer aliases. Ground truth never reaches engine/provider except when independently present in permitted history or explicit approved pin fixtures.
- Questions must not contain their expected answers. Source attribution distinguishes retrieval, window, pins and summary contributions.

## Six centrally declared variants

| ID | Layers | Comparison purpose |
|---|---|---|
| A0 | None; raw history | Measure fit and cost of no-layer baseline. Oversized prompts are recorded and not sent. |
| A1 | WINDOW | Recency-only baseline. |
| A2 | CAP + WINDOW | CAP contribution relative to A1. |
| A3 | CAP + PIN + WINDOW | Supplied durable facts relative to A2. |
| A4 | CAP + PIN + RETRIEVE + WINDOW | Exact historical retrieval relative to A3. |
| A5 | CAP + PIN + RETRIEVE + WINDOW + SUMMARIZE | Broad summary relative to A4. |

System and current question are mandatory in every variant; PIN toggles durable facts. Set query-answer pins to empty in the retrieval-focused corpus; verify supplied-answer pin retention in a separate declared fixture. Therefore A2/A3 may tie on the primary task, and that is an honest finding. A frozen summary without answers may improve continuity without improving exact-fact recall. Do not claim that every layer must increase this one score.

## Proposed success criteria

At the 900-token budget, A5 must fit all 31 well-formed probes, preserve facts in at least 28/31, and answer correctly in at least 27/31 for the primary model on valid completed calls. At least 90% median input-token reduction relative to raw input is a proposed efficiency target. These are engineering acceptance proposals, not statistically proven population claims.

Evaluate comparison-model results separately; do not select the best run. Report fit, factual presence, answer accuracy, abstention/error/truncation counts, latency, provider/replay caching and marginal spend. No imputation of successful answers for provider failures. Publish both all-planned-probe and completed-call denominators.

Primary retained-evidence grading requires expected value/alias and valid source lineage in the assembled context. Also publish the literal `fact_present` metric required by the PRD, over the final prompt, to expose accidental answer appearance. Answer grading uses normalized exact or declared structured matching; identifier-aware boundaries prevent `shard-1` matching `shard-19`.

## Five validity gates

| Gate | Check | On failure |
|---|---|---|
| V1 Fixture integrity | Exactly 100 turns and 31 unique facts; valid source references, planted values present, disjoint metadata; schema/version/hash match. | Stop before inference; INVALID. |
| V2 Leakage | No expected value/alias in frozen summary or question; no ground-truth metadata in engine input; declared pin rules enforced. | Stop before inference; INVALID. |
| V3 Request integrity | Saved request equals measured assembly; token/config/model accounting consistent; no oversized request sent. A0 oversize is expected scored non-fit, not protocol corruption. | A corrupted/admitted-oversized request invalidates run. |
| V4 Generation completeness | Every planned probe has a disposition; finish reasons and errors preserved; proposed zero tolerated truncations for acceptance. | INTERRUPTED for resumable transport/quota stop; INVALID for completed protocol with unacceptable truncation. |
| V5 Reproducibility | Frozen hashes, code/config versions, replay provenance and settings consistent across paired comparisons. | INVALID; rerun under a new manifest if configuration changes. |

A valid run may FAIL quality. An interrupted or invalid run never appears as a passing leaderboard entry. Completion-budget changes create a new run manifest; rerun paired comparisons consistently rather than patching a few weak results.

## Statistics and cost

Report raw counts with percentages and Wilson 95% intervals for binary metrics; note that correlated probes in a single scenario are not independent real-world samples. Compare variants on the same probes, show discordant pairs and avoid a broad superiority claim from n=31. C09 adds separately frozen, held-out scenarios before production quality claims.

Cost includes non-cached input, cached input, output, retry charges when known, and any summary generation. Report unknown usage as unknown. Separate paid inference, local replay, and estimated avoided cost. Keep CPU/storage and local assembly latency visible even though retrieval consumes no inference tokens.

Six variants × 31 probes × two models gives 372 planned probe slots per budget before repeats; many raw-baseline slots may be rejected locally. At 900 input + 256 output, a deliberately conservative all-calls token reservation would be 430,032 tokens before retries, so the PRD's 200,000 daily example is not a one-day full-run guarantee. The runner must calculate the actual plan and pause/resume under the account's shared limits.

## Deliverables

`results-<model>-<run-id>.json` with immutable manifest and per-probe outcomes; generated scorecard and leaderboard; `context_cost.png` and `recall_by_zone.png`; all regenerated offline from saved results. Replayed responses may support reproducibility checks but cannot be treated as independent repeated samples or fresh provider cache measurements.
