# PRD traceability

The original `CONTEXT_ENGINEERING_PRD.md` is unchanged. This maps every numbered section to accountable delivery checkpoints. A mapping is not implementation evidence. Until checkpoint evidence exists, the corresponding runtime requirement remains unimplemented.

C01 evidence: [core contracts and token accounting report](C01_REPORT.md) covers its assigned contract, configuration, dependency, setup and accounting portions. Requirements that also need layers, pipeline or provider calibration remain incomplete; none of the 27 end-to-end V1 items is promoted to complete by C01 alone.

## All 73 PRD sections

| PRD | Subject | Checkpoint |
|---|---|---|
| 1 | Executive summary | C00 |
| 2 | Product vision | C00 |
| 3 | Problem statement | C00 |
| 4 | Goals | C00, C06 |
| 5 | V1 non-goals | C00, C11 |
| 6 | Target users | C00, C12 |
| 7 | Real-world example | C03, C06 |
| 8 | High-level architecture | C00, C03 |
| 9 | Execution order | C02, C03 |
| 10 | Final assembly order | C03 |
| 11 | CAP | C02 |
| 12 | PIN | C02 |
| 13 | RETRIEVE | C02 |
| 14 | WINDOW | C02 |
| 15 | SUMMARIZE | C02, C04 |
| 16 | Context blocks | C01, C03 |
| 17 | Turn model | C01 |
| 18 | Original vs working representations | C01, C02 |
| 19 | Budgeting on every call | C03, C08 |
| 20 | Budget formula | C01, C03, C05 |
| 21 | Default budget | C01 |
| 22 | Output reservation | C01, C05 |
| 23 | Token counting | C01 |
| 24 | Tokenizer calibration | C01, C05, C06 |
| 25 | Prompt cache strategy | C03, C06 |
| 26 | LLM inference | C05 |
| 27 | Generation configuration | C05 |
| 28 | Provider rate limits | C05 |
| 29 | Daily ledger | C05 |
| 30 | Replay cache | C05 |
| 31 | Pricing model | C05, C06 |
| 32 | Measurement harness | C04, C06 |
| 33 | Benchmark scenario | C04 |
| 34 | Ground truth | C04 |
| 35 | fact_present | C04 |
| 36 | Grading | C04 |
| 37 | Six ablations | C04, C06 |
| 38 | Pre-registration | C04 |
| 39 | Five validity gates | C04 |
| 40 | Frozen summary / leakage | C04 |
| 41 | Single probe | C03, C05 |
| 42 | Small-N statistics | C06 |
| 43 | Scorecard | C06 |
| 44 | Two figures | C06 |
| 45 | Leaderboard | C06 |
| 46 | Model-specific results | C06 |
| 47 | File structure | C00, C01 |
| 48 | Central configuration | C01 |
| 49 | Configuration dependency rule | C01 |
| 50 | Environment variables | C01, C05 |
| 51 | Security | C01, C05, C09 |
| 52 | Unicode runtime reliability | C05 |
| 53 | Cross-platform requirements | C01, C10 |
| 54 | Dependencies | C01 |
| 55 | Setup validation | C01 |
| 56 | API-ready output | C03 |
| 57 | Primary pipeline interface | C03 |
| 58 | Context carrier | C01 |
| 59 | Layer contracts | C01, C02 |
| 60 | CLI | C03, C05, C06 |
| 61 | Live demo | C06 |
| 62 | Canonical end-to-end benchmark | C04, C06 |
| 63 | Performance | C02, C10, C11 |
| 64 | Cost | C05, C06, C11 |
| 65 | Observability | C03, C05, C10 |
| 66 | Error handling | C01, C03, C04, C05 |
| 67 | Build gates | C01, C04, C05 |
| 68 | Reproducibility | C04, C06 |
| 69 | V1 acceptance | C06 |
| 70 | Future enhancements | C07, C11 |
| 71 | Product differentiator | C00, C06 |
| 72 | Final product definition | C03, C06 |
| 73 | Glossary | C00 |

## V1 acceptance checklist — PRD §69

IDs below are stable and correspond to the source checklist in order. Evidence is pending until populated with a test/result artifact and version at the owning checkpoint.

| ID | Acceptance requirement | Checkpoint | Evidence |
|---|---|---|---|
| V1-01 | Five independent layers | C02 | C02 verified: tests/test_layers.py; C02_REPORT.md |
| V1-02 | One-call assembly | C03 | C03 v0.3.0: tests/test_pipeline.py; C03_REPORT.md |
| V1-03 | Final token budget validation | C03 | C03 local-boundary/shrink/mandatory-overflow tests; C06 observes 12 A2/A3 provider-input overruns at 900 tokens, so exact provider bounds remain unqualified (S12) |
| V1-04 | Original uncapped history retrievable | C02 | C02 verified: original-source and middle-fact tests |
| V1-05 | BM25 old-history retrieval | C02 | C02 verified: singleton/no-match/exclusion tests |
| V1-06 | WINDOW respects remaining budget | C02 | C02 verified: suffix/boundary/generated budget tests |
| V1-07 | PIN protects supplied facts | C02 | C02 verified: active pins, revision updates and overflow tests |
| V1-08 | SUMMARY background without leakage | C02, C04 | C04 frozen background/leakage gates verified; tests/test_evaluation.py |
| V1-09 | Retrieval near prompt suffix | C03 | C03 exact-order test; output/c03-inspection.json |
| V1-10 | Controlled Groq inference | C05 | Offline controls tested; live 120b flagship succeeds with captured provider usage in output/c06-live-smoke.json; broad calibration pending |
| V1-11 | Replay cache | C05 | C05 scoped keys, TTL, corruption rejection and zero-new-cost replay; tests/test_providers.py |
| V1-12 | Daily ledger | C05 | C05 atomic quota reservations, usage/cached pricing, uncertainty/reconciliation and concurrency tests |
| V1-13 | Single probe | C03, C05 | Live A5/900/120b answers shard-19 correctly; output/c06-live-smoke.json and validated smoke report; not full benchmark acceptance |
| V1-14 | 100-turn scenario | C04, C06 | C04 frozen corpus verified; C06 snapshot249 completes744 live dispositions on this scenario,not held-out quality |
| V1-15 | 31 gradable facts | C04 | C04 unique source/alias/zone/plant checks and deterministic grading |
| V1-16 | Six benchmark configurations run | C06 | Snapshot249:all744 dispositions across A0–A5/two models/two budgets;613 responses,124 non-fits,seven preserved errors. C06_REPORT.md |
| V1-17 | Independent fact presence / answer correctness | C04 | All four combinations tested; final primary A5 has29/31 retained and29/31 correct,separately reported.20b/A5/3000 retains19/31 but answers18/31 with one missing answer |
| V1-18 | Pre-registered criterion | C04 | Targets frozen before context measurements; explicit owner approval 2026-09-13, D047, before live inference; PREREGISTRATION.md |
| V1-19 | Five validity gates execute | C04 | C04 corruption/partial/truncation/drift cases tested; output/c04-benchmark-check.json |
| V1-20 | Frozen-summary leakage gate | C04 | C04 identifier/Unicode alias leak rejection before inference |
| V1-21 | Model swap | C06 | Both frozen Groq models fully disposed under one identity in249;immutable reports retain model-specific results/errors. No cross-provider substitution |
| V1-22 | Statistics | C06 | C06 raw counts, explicit denominators, zone retention, known/unknown usage/cost; tests/test_execution.py |
| V1-23 | Scorecard | C06 | Final report249 VALID/five gates PASS/primary quality PASS;seven errors and unknown original receipt remain visible,with external accounting supplement in C06_REPORT.md. Not enterprise qualification |
| V1-24 | Leaderboard | C06 | Generated output/c06-report/leaderboard.md, invalid/pending outcomes preserved |
| V1-25 | Two figures without new API calls | C06 | Context/cost and zone PNG generation; locked-environment network-disabled reproducibility tests |
| V1-26 | CLI full run | C06 | Live runner exits0 at249,all744 terminal/zero pending. Resume preserves prior outcomes;amendment009 reconciles one timeout's accounting without rewriting its failure. No further calls required |
| V1-27 | Reproducible results | C06 | Both core freezes intact;final249 reports byte-identical with sockets disabled,figures inspected. Requires disclosed operational amendments001–009/source hashes/sidecars/events and external reconciliation evidence. C06_REPORT.md;hard-budget calibration/production gates still unqualified |

## Enterprise extension accountability

| Requirement group | Owner checkpoint | Specification |
|---|---|---|
| Runtime persistence, memory revision, retention and deletion | C07 | MEMORY, C07_REPORT; tests/test_memory.py: persistence, conflict, index resume, invalidation, export and deletion-safe restore; production recovery remains C10 |
| Identity, tenancy, API and SDK compatibility | C08 | SERVICE, C08_REPORT; tests/test_service.py and synthetic loopback evidence; production IdP/TLS/load remain unqualified |
| Threat model, negative isolation tests, held-out quality | C09 | C09_REPORT, C09_THREAT_MODEL, C09_EVALUATION_PROTOCOL;139 C09 tests including process containment and TEST_ONLY scoring; ACTIVE: local engineering verified, independent live quality/calibration pending approval |
| Recovery, observability, load, release artifacts | C10 | ENTERPRISE |
| Measured optimization and controlled evolution | C11 | SUGGESTIONS |
| Customer pilot, operating ownership and release acceptance | C12 | ENTERPRISE, CHECKPOINTS |

Scope changes require a decision ID and updates to affected rows. Preserve prior evidence when a requirement is superseded.
