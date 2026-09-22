# C01 — Core contracts and token accounting

Date: 2026-09-07. Status: implementation and verification complete; READY for owner review. This checkpoint does not implement the five context layers, inference, or the benchmark.

## Delivered

| Component | Implementation | Evidence |
|---|---|---|
| Installable package | `context-engineering-core` 0.1.0, Python ≥3.12, typed package, CLI entry point | Wheel and source distribution built; wheel installed into a separate environment and executed outside the repository. |
| Validated configuration | Budget/headroom, layer reserves, tokenizer factor/overhead, explicit environment loading, module-relative paths | Rejects invalid/negative/boolean values, non-finite calibration, impossible output reservation and malformed paths. |
| Immutable originals | Messages, multi-message turns, tool calls, stable IDs, revisions, scope and content hashes | External list mutation cannot change stored data; working copies preserve identity; original call argument bytes are retained. |
| Source provenance | SourceRef and Chunk with Unicode code-point offsets, revision/hash verification | Wrong tenant, revision, content, offset or chunk value rejected. |
| Durable fact contract | KeyedPins and Pin with origin, effective/expiry time and optional source | Duplicate keys and scope mismatches rejected; expiry boundaries tested. Persistence/upsert transactions remain C07. |
| Blocks and carrier | Required block kinds, optional text counts, source refs, immutable carrier snapshots, typed layer diagnostics/protocol | Source scope, turn identity/order, tool metadata and question duplication checks. |
| Token accounting | Injected TokenCounter/RequestSerializer; tiktoken `o200k_harmony`; canonical JSON fallback | Complete messages, roles, call arguments/results and tool schemas counted; exact serialization count compared with encoding directly. |
| Budget admission | `plan_budget` and `validate_request`; immutable BudgetPlan | Exact-boundary acceptance; mandatory overflow and reserve overflow typed errors; generated allocation conservation cases. |
| Controlled diagnostics | Content-free structured configuration/contract/tokenizer/budget errors | Secret-bearing invalid input and simulated transport detail omitted from reported errors. |

## Reproduce

From the project directory:

```bash
uv sync --locked --python 3.12
uv run --locked context-engine check
uv run --locked context-engine demo-budget
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv lock --check --offline
uv pip check
uv build --offline
```

Observed on macOS ARM64 / CPython 3.12.13 / uv 0.11.16:

- Setup: `deps ok`.
- Tests: **55 passed**, including eight existing brain integrity tests and a Hypothesis-generated allocation test.
- Lint and formatting: pass.
- Lock consistency and installed dependency compatibility: pass.
- Source distribution and wheel: built successfully; wheel includes `py.typed` and excludes the project brain, `.env` and bytecode.
- Separate fresh virtual environment: runtime dependencies installed offline from a hash-checked lock export, then the built wheel installed without dependencies. `python -I -m context_engine check` and `demo-budget` pass from `/private/tmp`; imported package resolves inside that environment's site-packages.

Runtime dependency: tiktoken 0.14.0, with locked transitive dependencies. Development tools: pytest 9.1.1, Hypothesis 6.167.1 and Ruff 0.16.6. Build backend: hatchling 1.32.0, explicitly pinned. This is local verification; Windows/Linux CI qualification remains C10.

## Owner demonstration

The synthetic default demo uses system instructions, a supplied database pin and a question. Its 48 serialized tokens become 52 estimated tokens after calibration. Against B=3,000, the plan reserves 280 for retrieval and 80 for summary, leaving 2,588 for WINDOW. No window is selected in C01.

The oversized pin fixture produces 6,469 estimated tokens and a `required_context_too_large` error: allowance 3,000, overflow 3,469. The error contains counts, not the pin content. These are locally observed demo counts, not benchmark recall or provider usage results.

```python
from context_engine.budget import plan_budget
from context_engine.config import BudgetConfig
from context_engine.models import ChatRequest, Message, Role
from context_engine.tokens import TiktokenCounter

required = ChatRequest((
    Message("system", Role.SYSTEM, "Answer from supplied evidence."),
    Message("question", Role.USER, "What happened?"),
))
plan = plan_budget(
    required_request=required,
    config=BudgetConfig(input_cap=900),
    counter=TiktokenCounter(),
)
print(plan.to_dict())
```

The caller must supply all mandatory content to this low-level admission function. C02/C03 will compose system, active pins, current question and tools automatically. Admission never removes any supplied content.

## Contract details for C02

- Originals are frozen; CAP creates replacement messages/turns, keeping IDs, revisions, timestamps and tool metadata. It must not mutate or delete originals.
- Source ranges use Python string offsets (Unicode code points), not bytes or token IDs. Validate a chunk against its original before trusting its provenance.
- Raw tool-call arguments are preserved. Tool definition schemas use canonical immutable JSON; mutable wire dictionaries are fresh copies.
- Tool results must match pending calls; parallel calls may return in either order, but all results must complete before another non-tool message or inference request.
- Layer allocations are calibrated incremental request-token units, including added framing. `ContextBlock.text_tokens` is only an optional local content count. Final request admission must use `validate_request`, not sum block content counts.
- `BudgetPlan.window_turn_ids` is empty until C02's shared planner selects WINDOW. Both retrieval exclusion and WINDOW must use that one plan.
- Environment loading is explicit (`Settings.from_env`); `.env` is never automatically read. No key is used by C01. Output paths are resolved relative to `config.py` unless absolute; installed deployments should supply a writable output directory before later persistence work.
- Scope checks prevent inconsistent in-process inputs but do not authenticate the caller. Service authorization remains C08/C09.

## Limitations and follow-up

The canonical chat serializer counts the complete prompt-bearing JSON rather than the provider's private model template. The configurable factor and overhead are unverified estimates; diagnostics always state `provider_accounting_verified=false`. The provider adapter must supply appropriate serialization and measured calibration before production claims.

The current message contract covers text and function tool calls; multimodal payloads are not silently accepted. No summarization, retrieval, storage, external API calls, deployment or benchmark spending occurred. Next checkpoint: C02, the five independent layers and shared window/retrieval planning.
