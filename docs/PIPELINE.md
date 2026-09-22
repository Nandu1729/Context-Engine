# Public assembly and offline inspection — C03

Introduced in package 0.3.0: `context_engine.assemble_context` and `AssembledContext`. Package 0.4.0 adds optional-layer controls without changing defaults. Importing the package alone does not initialize a tokenizer or load configuration. Layers remain independently callable; see [layer contracts](LAYERS.md).

C07 adds optional `chunk_index` input with exact history/configuration/source validation. Omit it for ordinary chunking, or use `MemoryStore.assemble` for managed persistence, indexing and revision checks. See [runtime memory](MEMORY.md); assembly does not authenticate callers or implicitly persist data.

## SDK contract

```python
from datetime import UTC, datetime

from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

scope = Scope("synthetic-tenant", "synthetic-session")
at = datetime(2026, 9, 7, tzinfo=UTC)
history = (
    Turn("t1", scope, (Message("m1", Role.USER, "Database: PostgreSQL"),), timestamp=at),
)
result = assemble_context(
    history,
    "Which database?",
    KeyedPins(scope),
    BudgetConfig(input_cap=900),
    system="Answer from supplied evidence.",
    at=at,
)
messages = result.messages  # Fresh API-ready dictionaries.
request = result.request.to_wire()  # Messages plus any tool definitions.
assert result.diagnostics.remaining_tokens >= 0
```

Required positional arguments: immutable `Turn` history (list or tuple), question (string or user `Message`), `KeyedPins`, `BudgetConfig`. Required keyword: nonempty `system`. Optional keywords: `at`, `token_counter`, `cap_config`, `retrieval_config`, `summary_policy`, `tools` (validated `ToolDefinition` list/tuple). No environment configuration is read by the SDK defaults. The CLI reads supported settings from the environment.

C04 adds `options=AssemblyOptions(cap=True, pins=True, retrieve=True, summarize=True)`, also exported from `context_engine`. False options explicitly disable the corresponding optional behavior; mandatory system/question reservation, WINDOW and final validation remain active. Disabled retrieval/summary receive zero reserves. Disabling pins is an explicit caller policy choice, never an automatic budget fallback. The benchmark uses these same controls for A1–A5; all existing default-API guarantees remain unchanged.

Supply a timezone-aware `at` for reproducible pin/summary expiry; omission means the current UTC time. Scope comes from `KeyedPins`, including empty history. Every history turn must match that scope. The caller must authorize the snapshot before invoking this API; scope labels are not authentication. A `Message` question must not reuse a history message ID; a string question gets a collision-free internal ID. Call this boundary again after new tool results arrive.

The result is immutable, with six ordered logical `blocks`, a validated `request`, and diagnostics. Empty optional blocks remain in diagnostics but do not produce empty data messages. The current question is always the final user message, exactly once as a dedicated block. Historical occurrences of the same text are not deduplicated. Historical system/tool/assistant messages are quoted JSON data, not active system instructions or executable tool calls. This preserves metadata without introducing unmatched tool-response messages into the outgoing request.

## Order and final admission

Execution: CAP → PIN → RETRIEVE → WINDOW → SUMMARIZE.

Messages: SYSTEM → PINNED → SUMMARY → WINDOW → RETRIEVED → QUESTION.

PIN reserves the entire mandatory request and optional allocations. RETRIEVE and WINDOW share the same capped, contiguous-suffix membership plan. Retrieval reads only uncapped originals outside that plan. Each optional admission includes full framing and the planned WINDOW. A caller-supplied summary must match the exact omitted history; there is no hidden summarization inference.

Final admission validates selected evidence against original source ranges, checks WINDOW/evidence content against the plan, and recounts the complete serialized request including tool schemas. Defensive overflow removal is deterministic:

1. Remove the whole optional summary.
2. Remove complete oldest WINDOW turns, one at a time.
3. Remove lowest-ranked retrieved chunks, one at a time.

Each removal triggers another full count. No mandatory system text, active pin, question, or tool definition is evicted; impossible mandatory content raises `RequiredContextTooLarge`. Invalid reserves fail before selection. A changed counting profile or stale/mismatched state fails closed. Removal is bounded by one summary plus the number of selected turns/chunks. No re-retrieval or reserve redistribution happens after shrinking; planned and final WINDOW IDs are both reported. Normal layer admission already fits; injected oversized selections in tests exercise the defensive path.

## Diagnostics and privacy

`result.to_dict()` is metadata-only. `result.to_dict(include_content=True)` explicitly adds the assembled wire request. Diagnostics include total allowance/remaining tokens, tokenizer/version/serializer, calibration/overhead, per-block content counts and serialized incremental costs, source references, planned/kept/omitted/retrieved IDs, layer reason codes, final drops, evaluation time, package version and fingerprints.

`base_request_tokens` counts tool schemas and empty-question framing. Adding each block in final order produces signed calibrated `input_delta_tokens`; base plus all deltas equals the final estimate. Raw `content_tokens` are explanatory and are not additive across serialization boundaries. Final admission always uses the complete request count.

Source ranges refer to original Unicode code-point offsets. WINDOW lineage identifies original messages even when their working content is capped; it does not claim the rendered WINDOW is verbatim. Summary lineage proves the source snapshot, not factual correctness of generated prose.

The request fingerprint covers serialized prompt bytes; the input fingerprint covers source/working history, pins and question; the config fingerprint covers budget/layer/counting parameters. These are diagnostic hashes, **not replay-cache keys or a complete reproducibility manifest**: summary policy version, provider/generation settings and dependency/fixture hashes must be separately frozen at C04/C05. Keep source IDs opaque: metadata is not anonymized and hashes can reveal equality. Neither default output nor the project brain should receive credentials or customer bodies. Inspect customer data only in an authorized, protected location.

Token safety remains a local estimate, not a provider guarantee. Canonical JSON is not Groq's private template, and the 1.07 multiplier remains uncalibrated until C05/C06. No answer accuracy, cost savings, prompt-cache benefit or enterprise readiness is inferred from these tests.

## CLI and version-1 input

```bash
uv run --locked context-engine config
uv run --locked context-engine inspect
uv run --locked context-engine probe --budget 900
uv run --locked context-engine inspect --input examples/inspection-input.json --show-content
uv run --locked context-engine inspect --output output/my-new-inspection.json
```

`config` shows validated budget/tokenizer/CAP/retrieval settings, never API keys. `inspect` and `probe` are offline context operations: zero inference, no model answer. With no input path they use the fixed 12-turn synthetic demonstration and its fixed layer/budget settings; tokenizer settings still come from the environment, and `--budget` overrides the demo allowance. Initial installation/tokenizer-vocabulary loading may require networking; inspection uses cached vocabulary thereafter.

The [example JSON](../examples/inspection-input.json) shows the file format. Required fields: `schema_version: 1`, `scope` (`tenant_id`, `session_id`), `system`, string `question`, ISO timezone-aware `at`, and `history`. Each turn has `turn_id` and `messages`, optional `revision` (default 1) and `timestamp` (default `at`). Each message has `message_id`, `role`, `content`; optional `tool_call_id` and `tool_calls` with `call_id`, `name`, `arguments_json`.

Optional `pins` entries require `key`, `value`, `origin`; optional `revision`, `effective_at`, `expires_at`. Optional `tools` entries require `name`, `parameters` JSON schema, and optional `description`. Optional `budget`, `cap`, `retrieval`, `tokenizer` objects override validated settings by dataclass field name. Optional `summary` contains `content`, ordered `covered_turn_ids`, `policy_version`, `created_at`, and optional `expires_at`; it is reused only when coverage exactly matches omitted history.

Unknown/missing fields, duplicate JSON keys, nonfinite constants, malformed UTF-8, invalid contracts and oversized input return structured errors. Input files are limited to 2,000,000 bytes and 10,000 turns; these are CLI safeguards, not comprehensive SDK CPU/memory quotas. `--output` explicitly writes a new JSON file and refuses overwrite. `--show-content` applies to both console and saved output. Custom files are conservatively labeled `synthetic_input: false` because their provenance is unknown. Exit status: 0 on success, 1 on structured engine errors, 2 on command-line syntax errors.

## Evidence

Tests: `tests/test_pipeline.py` and `tests/test_inspection.py`, alongside earlier checkpoint suites. Saved demonstration: `output/c03-inspection.json` (explicit content export of synthetic data only). It recovers `shard-19` from old turn `t1` with a 637/900 local estimate and zero inference calls. The owner's concise handoff is [C03 report](C03_REPORT.md). The 100-turn benchmark and answer scoring are C04/C06 work, not this demonstration.
