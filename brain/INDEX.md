# Project brain index

Read this file and [STATE](STATE.md) at session start. These two files are the small working memory; deeper documents are loaded by topic. The source of truth is on disk, not previous chat recollection.

| Need | Read |
|---|---|
| Current progress / next action | [STATE](STATE.md) |
| Owner choices / durable defaults | [DECISIONS](DECISIONS.md) |
| Current delivery and acceptance evidence | [Checkpoints](../docs/CHECKPOINTS.md) |
| Product review / unresolved choices | [Owner review](../docs/OWNER_REVIEW.md) |
| Original requirement / scope | [Requirements map](../docs/REQUIREMENTS.md), then relevant [PRD](../CONTEXT_ENGINEERING_PRD.md) section |
| Interfaces / budget / retrieval / storage | [Architecture](../docs/ARCHITECTURE.md) |
| Implemented core contracts / setup / C01 evidence | [C01 report](../docs/C01_REPORT.md), then `src/context_engine/` |
| Five independent layers | [C02 report](../docs/C02_REPORT.md), [layer contracts](../docs/LAYERS.md) |
| Public assembly / offline CLI | [C03 report](../docs/C03_REPORT.md), [API guide](../docs/PIPELINE.md) |
| Frozen benchmark / resume snapshots | [C04 report](../docs/C04_REPORT.md), [harness guide](../docs/BENCHMARK.md) |
| Provider / replay / quota | [C05 report](../docs/C05_REPORT.md), [provider contracts](../docs/PROVIDER.md) |
| Run / model swap / reports / deferred live work | [C06 progress](../docs/C06_REPORT.md), [runner contracts](../docs/RUNNER.md), [Gemini setup](../docs/GEMINI_SETUP.md) |
| Runtime memory / indexing / deletion / latest handoff | [Memory contracts](../docs/MEMORY.md), [C07 report](../docs/C07_REPORT.md) |
| Authenticated API / integrations / C06 reminder | [Service guide](../docs/SERVICE.md), [C08 report](../docs/C08_REPORT.md) |
| Validity / proposed success targets | [Evaluation plan](../docs/EVALUATION.md), [owner pre-registration](../docs/PREREGISTRATION.md) |
| Security / operations / enterprise gates | [Enterprise scope](../docs/ENTERPRISE.md) |
| Improvement proposals | [Suggestions](SUGGESTIONS.md) |
| Why a past change happened | [Journal](JOURNAL.md), [C00–C08 archive](archive/JOURNAL_2026-09-07_to_C08.md) |
| Time-sensitive external facts | [Sources](../docs/SOURCES.md) |

Commands: `python3 scripts/brain.py status`, `context`, `search "topic"`, `index`, `check`.

Search is deterministic lexical discovery over allowed project Markdown. It is not the product's BM25 implementation. `brain/index.json` is derived and rebuildable. Never store credentials, private customer history, or raw provider responses in this brain.

Record new facts once in the appropriate canonical file and link to them. Keep hot memory short; archive history instead of deleting evidence. A missing or conflicting source should be investigated, not filled in from memory.
