# Evolution backlog

Entries are proposals unless marked implemented. Evaluate at the relevant checkpoint or when new workload evidence arrives. A suggestion needs an owner decision only when it changes material product scope, cost, or commitments.

| ID / stage | Suggestion | Expected benefit | Cost / risk | Proof before adoption |
|---|---|---|---|---|
| S01 / C02 implemented | Chunk original tool output with stable source offsets from the first retrieval release. | Recovers facts removed from message middles by CAP. | Index size and chunk-boundary complexity. | Verified by C02 middle-fact, boundary, provenance and deduplication tests. |
| S02 / C03 implemented | Ship an offline context inspector with block accounting, layer selection reasons and source references. | Makes incorrect inclusion/exclusion understandable. | IDs/hashes still reveal metadata; raw inspection can expose sensitive data. | C03 tests and saved synthetic demo pass; prompt bodies require explicit opt-in. Implementation ready, owner acceptance pending. |
| S03 / C06 | Measure marginal cost per correct answer across all six variants. | Identifies which layers earn their latency and token costs. | Depends on valid, paired runs. | Report raw quality counts plus cost, not a blended opaque score. |
| S04 / C07 | Store pins as versioned keys with origin, expiry and supersession. | Prevents contradictory or stale durable memory. | Requires concurrency semantics and conflict handling. | Simultaneous updates; expiry/deletion invalidates all dependent context. |
| S05 / C08 | Make provider access optional: return context to the caller or use the Groq adapter. | Useful to existing agent stacks without forcing provider migration. | More public interface compatibility work. | Two independent integration examples using the same core. |
| S06 / C09 | Add a multilingual and adversarial held-out corpus. | Tests failures that 31 English facts cannot expose. | Fixture creation/review effort. | Predeclare splits and prohibit tuning on held-out results. |
| S07 / C11 | Classify BM25 misses and low-value matches before adding hybrid retrieval. | May reduce filler tokens and recover paraphrases. | Filtering can harm recall; embeddings add cost/privacy/dependencies. | C04 flagship retrieves t82 first plus low-relevance t20/t90 chunks. Do not tune the frozen corpus; test filtering/hybrid proposals on separately frozen held-out data with paired quality/cost measures. Owner adoption pending. |
| S08 / C11 | Reuse summaries by history watermark, policy version and expiry. | Avoids regenerating summaries every turn. | Stale or lossy summaries. | Summary-age metric; changed/deleted source invalidates cache. |
| S09 / C11 | Bypass inference for verified structured lookups. | Saves inference for deterministic requests. | Wrong intent classification produces confident errors. | Restricted opt-in schema and provenance; abstain when ambiguous. |
| S10 / C11 | Add automated memory extraction as reviewed proposals. | Reduces manual pin maintenance. | Memory poisoning, false facts, extra calls. | Source-backed candidates; no automatic authority elevation. |
| S11 / proposed after C06 evidence | Investigate retrieval exclusion of CAP-shortened WINDOW turns. | Prevents larger context budgets from losing evidence: A5 retains 29/31 at 900, but 19/31 at 3,000 on the frozen synthetic corpus. | Re-querying window turns can duplicate evidence or change PRD behavior; needs a new protocol and paired comparison, not retroactive tuning. | At 3,000 t82 enters WINDOW after CAP removes its middle; retrieval excludes that turn. At 900 t82 is retrieved from the original. Compare source-chunk-level deduplication under a separately frozen experiment and held-out workload. Owner adoption pending; no algorithm change made in C06. |

## S12 — Provider-token calibration before hard-budget claims

Stage: proposed from C06 live receipts; owner adoption pending. No frozen runtime or acceptance criteria changed.

- Evidence: snapshot047's completed 900-token/120b groups contain 12 provider input counts above both the local estimate and allowance: four A2 and eight A3. Counts range 1,052–1,566 against estimates 877–880; maximum actual/estimate ratio is 1.7814 rounded upward. Snapshot061 confirms these observations with per-probe evidence in `output/c06-token-audit-061.json`; no such exceedance in primary A5 or the 81 completed larger-budget responses. These are provider-reported observations, not an established tokenizer-error cause or universal bound.
- Benefit: measure and reduce unexpected provider input usage before claiming hard token caps or reliable production capacity.
- Cost/risk: extra separately authorized calibration calls, smaller usable context and potentially lower recall; cache/accounting and serialization effects need investigation. A worst observed ratio on this synthetic corpus is not a safe universal multiplier.
- Experiment: preserve this baseline; independently freeze a provider/accounting audit and held-out multilingual/tool-schema sample. Compare saved wire requests, provider usage/cache detail and estimates; publish over-budget counts and paired retention/accuracy. Predeclare acceptable risk and owner-approved call budget before execution. Do not silently tune C06 or resend completed probes.

Review rule: inspect regressions and workload feedback first; refresh external sources when relevant; write one experiment with an acceptance threshold; compare cost and quality; retain, revise, or reject with evidence. This runs during project work, not through an implied background agent.

## S13 — Separate machine-answer conformance from semantic and retention quality

Stage:D088 policy003 diagnostic completes16calls:5/8correct each arm,one improvement
and one regression. Candidate not adopted;stop this prompt-only experiment.
See [live report](../docs/C09_POLICY_LIVE_REPORT.md). No further calls authorized;
semantic reliability and calibration remain open,no default adoption/gate waiver.

D085 adds an offline opt-in evidence-policy candidate after confirming both
conflicting facts were present.32development assemblies preserve prior retention;
later D088 quality target FAIL. See [analysis](../docs/C09_CONFLICT_ANALYSIS_REPORT.md).

- Evidence:strict8/32 matches;12 outputs contain the expected literal with extra
  wording,3 change ASCII identifier hyphens to U+2011,9 abstain with missing evidence.
  Current scores remain unchanged. This diagnoses failure types,not post-hoc regrading.
- Benefit:machine consumers receive exact identifiers;measure formatting,unsupported
  claims and source retention independently instead of conflating them.
- Cost/risk:response schema/parser integration and new cases;normalization may
  corrupt meaningful identifiers. Do not indiscriminately strip prose or map Unicode.
- Experiment:predeclare a provider-independent answer-field contract and strict
  conformance checks,plus source-chunk retention comparison(S11). Freeze fresh
  independent scenarios and explicit primary-versus-control targets before measuring.
  No auto-relaxation of WINDOW's already-failed90% target. New live calls need a new
  bounded approval;offline design/regressions can proceed without more quota.

S11 implementation note(D078):0.9.2 adds explicit SDK opt-in for missing original
chunks within CAP-shortened WINDOW messages. Default PRD exclusion is unchanged;
development recovery/source/deletion/budget tests pass. This is mitigation,not
independent quality proof or approval to change the default. Fresh qualification
and owner adoption remain pending;C06/live001 results are not rerun or regraded.
