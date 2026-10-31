# Implementation roadmap

Updated 2026-10-31. Status: DONE (verified), ACTIVE, NEXT, LATER, BLOCKED (names
the missing prerequisite). Effort is rough engineering time, not a delivery date.
Checkpoint gates C00–C12 in [CHECKPOINTS](CHECKPOINTS.md) still apply; "DONE"
here is engineering evidence, not owner acceptance.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repository audit and current-state docs | DONE |
| 1 | Complete and stabilize the core engine | ACTIVE (T2 done in 0.11.0; CAP latency next) |
| 2 | Reproducible evaluation and benchmarking | ACTIVE (offline + live 900-token accuracy done; real data missing) |
| 3 | Package and publish the Python SDK | ACTIVE (license, README, audit done; TestPyPI awaits go-ahead) |
| 4 | Hosted REST API and authentication | LATER (self-hosted API exists) |
| 5 | Developer dashboard and usage analytics | LATER |
| 6 | Billing and monetization | LATER |
| 7 | MCP and developer integrations | ACTIVE (stdio prototype done; real-client check pending) |
| 8 | Public launch and customer acquisition | LATER |

## Phase 0 — Audit (DONE)

Files: `docs/PROJECT_AUDIT.md`, `CURRENT_STATUS.md`, `BENCHMARK_REPORT.md`,
`SECURITY_AUDIT.md`, `TECHNICAL_DECISIONS.md`, `PRODUCT_STRATEGY.md`,
`MONETIZATION_PLAN.md`, this file, `CHANGELOG.md`.
Acceptance: findings traced to code/test evidence. Met.

## Phase 1 — Core engine

| Task | Files | Status | Evidence |
|---|---|---|---|
| 1.1 Fix bare `pytest` collection (F5) | `pyproject.toml` | DONE | Full suite via `uv run --locked pytest` |
| 1.2 Rolling prefix summaries (F1) | `layers/summarize.py`, `summaries.py`, `layers/__init__.py` | DONE | `tests/test_summaries.py` (14) |
| 1.3 Keep summaries across uncovered appends (F2) | `memory/store.py` | DONE | `tests/test_summaries.py`, `tests/test_memory.py` |
| 1.4 SDK example + docs | `examples/rolling_summary.py`, `docs/PIPELINE.md` | DONE | `tests/test_rolling_summary_example.py`; 28/40 turns use a summary vs 0/40 before |
| 1.5 `recover_capped_window` default on (F4/T2, D109) | `config.py`, `harness.py`, `strategies.py` | DONE (0.11.0) | 31/31 at 900 and 3000 offline; full suite 1429 pass |
| 1.6 Reduce CAP cost (F6) | `tokens.py` | DONE (0.12.0) at 900: 247 → 95 ms; 3000: 481 → 208 ms, identical output | Further: cheaper admission counting at large budgets |

Risks: default changes alter historical reproducibility (mitigated by version
archives); summary misuse for exact identifiers (documented).

## Phase 2 — Evaluation

| Task | Files | Status |
|---|---|---|
| 2.1 Five-baseline offline comparison, precision/recall, latency | `evaluation/strategies.py`, `cli.py`, `tests/test_strategies.py` | DONE (19 tests) |
| 2.2 Saved evidence | `output/strategy-eval-0100.json` | DONE |
| 2.3 Answer correctness per strategy (bounded live run) | `scripts/strategy_accuracy_live.py` | DONE at 900 tokens: combined 31/31, no_recover 29/31; 3000 not approved |
| 2.4 Real or realistic multi-scenario corpus (paraphrased questions, multi-session) | `evaluation/data/` new bundle | NEXT; LongMemEval development rows exist offline (D098/D099) |
| 2.5 Model-summary quality (fact retention in summary vs leakage) | `strategies.py` + `PromptSummarizer` | BLOCKED with 2.3 |

Acceptance for 2.3: per-strategy accuracy with confidence intervals, pre-registered
targets, separate retention/accuracy/cost reporting.

## Phase 3 — SDK

| Task | Status |
|---|---|
| 3.1 Wheel builds and installs in a clean environment; public API smoke | DONE for 0.11.0 (see CURRENT_STATUS) |
| 3.2 License Apache-2.0 (D109); `LICENSE`, project URLs, classifiers; newcomer README | DONE |
| 3.2b Dependency vulnerability + license scan | DONE: 71 advisories patched, re-scan 0 |
| 3.3 Publish to TestPyPI, then PyPI | TestPyPI DONE (0.11.0, verified install); PyPI needs owner go-ahead |
| 3.5 OpenAI/Anthropic message helpers; LangChain adapter (optional extra) | DONE (0.12.0) |
| 3.6 Inception (Mercury) adapter, offline-tested first | DONE (0.12.0); live smoke passed (D111) |
| 3.4 Trim install: make `pywin32` and evaluation data optional? | LATER: measure wheel size first |

## Phase 4–8 (LATER)

- **4 Hosted API:** per-tenant rate limits and quotas (SECURITY_AUDIT gap),
  PostgreSQL storage behind `MemoryStore` tests, self-service API keys, TLS/ingress,
  observability. Effort: weeks. Depends on Phase 3 adoption evidence.
- **5 Dashboard:** usage, token-reduction and retention reports per project.
- **6 Billing:** metering from the existing usage ledger concepts; card processor.
- **7 MCP:** thin server exposing `add_turn`, `pin`, `get_context`, `delete` over
  `MemoryStore`. Effort: days. Can start after 3.1.
- **8 Launch:** docs site, examples for major frameworks, integration sprints.

## Immediate next tasks

2. Owner: try the MCP server in a real client (config in docs/MCP.md).
3. Owner: approve committing D097–D110 work on a feature branch.
4. Owner: go-ahead to publish 0.12.0 to TestPyPI, then PyPI.
5. Engineering: cheaper admission counting for large budgets; paraphrased-question
   corpus to test lexical-retrieval limits (2.4).
