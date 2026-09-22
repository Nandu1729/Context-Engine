# Context Engine

A reusable context engine and evaluation harness for long-running agents, with an enterprise delivery roadmap.

**Current delivery:** C08 adds an optional authenticated local API, tenant/session roles, quotas/audit and integration examples around C07 persistent memory. See the [service guide](docs/SERVICE.md) and [C08 report](docs/C08_REPORT.md). The owner deferred unfinished C06 again to permit C08 offline; its live flagship passed and partial matrix is preserved in an isolated 0.7.2 environment. Return to [C06](docs/C06_REPORT.md) before C09 quality qualification. The project is not yet enterprise-qualified.

## Run the core

```bash
uv sync --locked --python 3.12
uv run --locked context-engine check
uv run --locked context-engine demo-budget
uv run --locked context-engine demo-layers
uv run --locked context-engine config
uv run --locked context-engine inspect
uv run --locked context-engine inspect --input examples/inspection-input.json --show-content
uv run --locked context-engine benchmark-check
uv run --locked context-engine benchmark-plan
uv run --locked context-engine provider-demo
uv run --locked context-engine memory-demo
uv run --locked context-engine benchmark-run --help
uv run --locked context-engine benchmark-report --help
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
```

Setup prints `deps ok`. The demo shows a valid mandatory request and a rejected oversized pin without inference. First-time installation/tokenizer vocabulary loading requires network access; subsequent checks use cached assets. No API key is required. Dependencies are resolved in `uv.lock`; the build backend is pinned separately in `pyproject.toml`.

The reference benchmark freezes Python **3.12.13**, source and dependency versions; use `uv sync --locked --python 3.12.13`. The current freeze identifies package 0.7.2 and [owner-approved targets](docs/PREREGISTRATION.md). Earlier wheels/protocols are preserved under `archives/` and historical results require their matching wheel. General SDK use remains Python 3.12+. Benchmark commands validate the packaged protocol; no paid inference has run.

Package 0.7.1 introduced free-tier accounting and private `--env-file` loading; 0.7.2 records approval before inference. See [runner safeguards](docs/RUNNER.md). A saved key alone never establishes account tier or target approval; those now have explicit owner confirmation. C06 live qualification remains incomplete.

The optional live transport installs with `uv sync --locked --extra provider --python 3.12.13`. `provider-probe --help` documents explicit authorization, credential, account limits and price-card requirements. Do not run it without a spending decision. The offline demo needs no key and uses synthetic pricing; it does not measure provider savings.

Install PNG reporting with `uv sync --locked --extra reports --extra provider --python 3.12.13`. `benchmark-run` and `model-swap` default to a synthetic UNKNOWN transport; only an explicitly authorized live mode can spend. `benchmark-report` regenerates outputs from a validated saved snapshot without inference. Follow the [bounded run/resume example](docs/RUNNER.md).

Use `from context_engine import assemble_context` for the public API. The [SDK/CLI guide](docs/PIPELINE.md) documents typed inputs, messages, diagnostics, shrink behavior and JSON inspection. `inspect` and `probe` make no inference calls and hide prompt bodies unless `--show-content` is given. `context_engine.layers` remains available for independent composition; `demo-layers` shows capped middle evidence recovered from originals.

Token totals are **local estimates** of the complete prompt-bearing request, with explicit framing/schema accounting, configurable overhead and calibration. The default canonical JSON serializer is not Groq's private prompt template; provider calibration remains C05/C06. The 1.07 factor is not a proven safety bound.

## Project entry points

- [Brain index](brain/INDEX.md): where to read for each task.
- [Current state](brain/STATE.md): verified progress and exact next action.
- [Checkpoints](docs/CHECKPOINTS.md): delivery gates from foundation to enterprise release.
- [Architecture](docs/ARCHITECTURE.md): contracts, budget rules, and trust boundaries.
- [Requirements](docs/REQUIREMENTS.md): all 73 PRD sections and all 27 V1 acceptance criteria mapped to checkpoints.
- [Original PRD](CONTEXT_ENGINEERING_PRD.md): unchanged source of requirements.

## Use the project brain

From this directory, using Python 3.12+ for project work:

```bash
python3 scripts/brain.py status
python3 scripts/brain.py context
python3 scripts/brain.py search "summary budget"
python3 scripts/brain.py index
python3 scripts/brain.py check
uv run --locked pytest -q
```

The brain utility also supports Python 3.11 for bootstrap. It uses only the standard library and makes no API calls. The product core requires Python 3.12+; use `uv run --locked python` for its scripts and tests if the system Python is older. Commands locate the workspace relative to the script, so they also work from another directory. Search returns bounded excerpts with file and line references. The index stores paths, hashes, and heading locations, not another copy of document content.

The development brain documents this project. The product's future runtime memory stores agent conversations, pins, summaries, and evidence. They are separate systems with different privacy and lifecycle requirements.

## Development direction

Python SDK and offline-tested Groq adapter are implemented; live benchmark proof is next, then durable runtime memory and a self-hosted service. Hosted SaaS is an owner decision. See [enterprise scope](docs/ENTERPRISE.md). No production readiness, model quality, provider savings or latency result is claimed before measurement.
