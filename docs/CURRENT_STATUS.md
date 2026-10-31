# Current status — 2026-10-31

Package **0.15.0**, released on **PyPI** (also 0.12.0, 0.12.1, 0.14.0); merged to `main` (PR #1) (`pip install context-engineering-core`); 0.12.0 also on PyPI/TestPyPI. Code in PR #1 (`feat/developer-launch`). Developer SDK and self-hosted local
service; not an enterprise-qualified release. Owner decisions: D109 in
[brain/DECISIONS.md](../brain/DECISIONS.md). Plan: [IMPLEMENTATION_ROADMAP](IMPLEMENTATION_ROADMAP.md).

## Works today (with test evidence)

| Capability | Evidence |
|---|---|
| Five layers + one-call `assemble_context`, budget-safe or typed error | `tests/test_layers.py`, `test_pipeline.py`, `test_core.py` |
| WINDOW recovery on by default (0.11.0): 31/31 retention at 900 and 3000 tokens | `context-engine strategy-eval`; `tests/test_strategies.py`; [BENCHMARK_REPORT](BENCHMARK_REPORT.md) |
| Rolling summaries (opt-in) and explicit summary refresh | `tests/test_summaries.py`, `tests/test_rolling_summary_example.py` |
| Durable SQLite memory, deletion-safe restore, tenant isolation | `tests/test_memory.py`, `test_service.py`, `test_c09_*` |
| Authenticated local `/v1` API with bounded workers | `tests/test_service.py`, `test_c09_workers.py` |
| Frozen benchmark integrity; historical runtimes replay from archived wheels | `tests/test_runtime_transition.py`, `test_retrieval_diversity_candidate.py` |
| Apache-2.0 license and package metadata; newcomer README with a tested example | `LICENSE`, `pyproject.toml`, `tests/test_readme_example.py` |
| Wheel (151 KB) and sdist (123 KB) build; clean installs from both | `context-engine check` → `deps ok`; README example runs; `recover_capped_window` default True |
| Dependency audit: 0 known vulnerabilities (OSV) after lock upgrades; all licenses permissive | [SECURITY_AUDIT](SECURITY_AUDIT.md) supply-chain row |
| Bounded live strategy-accuracy runner (no retries, free tier, amendment-bound skips) | `scripts/strategy_accuracy_live.py`; `tests/test_strategy_accuracy_live.py` (9, offline) |
| Provider/framework adapters: OpenAI, Anthropic, LangChain (optional), OpenAI-history import | `context_engine.adapters`; `tests/test_adapters.py` (11); real langchain-core 1.7.3 checked in a scratch venv |
| Inception (Mercury) provider | `tests/test_inception.py` (16, offline); live smoke D111: 1 call, mercury-3, 715/45 tokens, correct, free tier |
| MCP server prototype over `MemoryStore` (stdio) | `context-engine-mcp`; `tests/test_mcp_server.py` (10); Claude Code reports Connected; installed-binary round trip PASS |
| All-layers latency under 100 ms: 67 ms at 900, 80 ms at 3000 (was 247/481 ms in 0.11.0), identical output | 0.12.1; `tests/test_assembly_speed.py`, `tests/test_token_cache.py`; 310/310 outputs match 0.12.0 |

## Test results

Full suite, `uv run --locked --offline pytest -q`, macOS arm64, Python 3.12.13.
0.11.0: run 3 **1429 passed, 0 failed** (earlier runs 1–2 failures were fixed;
see the brain journal). 0.12.0: run 4 (adapters) 1450 passed; run 5 (Inception)
1466 passed; run 6 (MCP) 1476 passed; run 7 (latency) **1479 passed** (316 s, was 538 s).
All with 0 failed and 48 skipped (Windows-only and one private-screenshot test).

Lint: `ruff check src` passes. `python3 scripts/brain.py check` passes.
`benchmark-check`: V1/V2/V3/V5 PASS, V4 NOT_RUN by design.

## Live answer accuracy (D109/D110)

COMPLETE at 900 tokens, gpt-oss-20b free tier, 155 slots (153 answered, 2 zero-token
rejections, no retries, $0): combined (new default) 31/31, retrieval_window 31/31,
combined_no_recover 29/31, summary_window 1/29, recent_window 1/31. Accuracy equals
offline retention on this synthetic corpus. See [BENCHMARK_REPORT](BENCHMARK_REPORT.md).

## Published

- TestPyPI: `context-engineering-core` 0.11.0 (D110) and 0.12.0 (D111; wheel
  `9b289b16…`, sdist `0c44130b…`), both verified by a fresh install from TestPyPI.
- PyPI: 0.15.0 released 2026-10-31 (wheel `ab5c234f…`, sdist `34b2b33b…`, ~7 MB with the
  bundled model; fresh install with no extras and network blocked finds a reworded
  fact). 0.14.0 released 2026-10-31 (wheel `b9357141…`, sdist `b132bde0…`; fresh install
  with `[semantic]` PASS, hybrid finds a reworded fact). 0.12.1 released 2026-10-31 (wheel `1585cabd…`, sdist `db6d635b…`; owner ran the
  upload command; fresh install PASS). 0.12.0 released 2026-10-31 (D112), same files as TestPyPI (hashes match);
  fresh install from PyPI passes `context-engine check`, the README example and
  `context-engine-mcp --help`.

## Incomplete / blocked

| Item | Status |
|---|---|
| PyPI upload | TestPyPI done; real PyPI needs owner go-ahead |
| Live accuracy at 3000 tokens / paid models | Not approved |
| MCP in-chat use by a model | Owner restarts Claude Code and tries the tools |
| Reworded questions | 0.15.0 **default** hybrid retrieval (bundled model, weight 0.5): offline 3/31 → 21/31; live (D114, weight 0.7) keyword 3/31 vs hybrid 18/31 strict, 21/31 lenient (grading v2). Needle-in-filler + reworded still hard: 12/31 |
| Real-world evaluation data | None; single synthetic scenario |
| Production operations (load, SLOs, TLS, IdP, rate limits) | Later stages |

## Incident

While preparing release files, the assistant deleted the git-ignored local `dist/`
folder without inspecting it. Lost with no copy: 0.1.0–0.3.0 wheels, most older
sdists and the c02–c07 requirements files. No test or runner used them; archived
wheels for 0.4.0–0.10.0 and c06/c08/c09 requirements remain. See the brain journal.

## Repository state

D097–D115 work is merged into `main` through PR #1
(https://github.com/Nandu1729/Context-Engine/pull/1, merge commit `28f1649`); the
feature branch is deleted. README/PyPI doc links resolve on `main`.
