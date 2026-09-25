# Project brain index

Start here and in [STATE](STATE.md); load deeper documents by topic. Disk is authoritative.

| Need | Read |
|---|---|
| Current progress / next action | [STATE](STATE.md) |
| C09 active work / security / evaluation | [C09 report](../docs/C09_REPORT.md), [response diagnosis](../docs/C09_RESPONSE_DIAGNOSTIC_REPORT.md), [caller guard](../docs/C09_EMPTY_ANSWER_REPORT.md), [qualification live002](../docs/C09_QUALIFICATION_LIVE_REPORT.md), [repair001](../docs/C09_REPAIR_REPORT.md), [live001](../docs/C09_LIVE_REPORT.md), [threat model](../docs/C09_THREAT_MODEL.md) |
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
| Current release blockers / operational evidence | [C12](../docs/C12_REPORT.md), [C10](../docs/C10_REPORT.md), [C11](../docs/C11_REPORT.md), [runbook](../docs/OPERATIONS.md) |
| Improvement proposals | [Suggestions](SUGGESTIONS.md) |
| Why a past change happened | [Journal](JOURNAL.md), [C00–C08 archive](archive/JOURNAL_2026-09-07_to_C08.md), [C06 completion archive](archive/JOURNAL_C06_COMPLETION_2026-09-22.md) |
| Time-sensitive external facts | [Sources](../docs/SOURCES.md) |

Commands: `python3 scripts/brain.py status`, `context`, `search "topic"`, `index`, `check`.

Search is lexical Markdown discovery, not product BM25. `brain/index.json` is rebuildable. Never store credentials, customer histories or raw provider responses here.

Record facts once and link them. Archive history; preserve evidence. Investigate missing or conflicting sources.
