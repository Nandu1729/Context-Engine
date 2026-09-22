# Frozen benchmark and validity harness — C04

Implemented in package 0.4.0, separately from the reusable core. All C04 commands are offline. The [short report](C04_REPORT.md) is the owner handoff; [pre-registration](PREREGISTRATION.md) remains pending owner approval.

C05 continuation: the current packaged reference freeze identifies 0.5.0 source with unchanged corpus/protocol/targets. Original C04 freeze and wheel are preserved in `archives/c04/`, and original output snapshots are unchanged. Use the archived wheel with its archived freeze to reproduce those runs; a 0.4.0 resume snapshot is intentionally incompatible with changed 0.5.0 source. Provider execution is now implemented separately; benchmark-to-provider orchestration and live results remain C06.

C06 continuation: current package/freeze is 0.6.0; C05 is now archived too. [Runner contracts](RUNNER.md) document version-2 execution receipts, durable dispatch journaling, model-swap and regenerated reports. The original version-1 snapshot API remains available; it is not the new journal format. Full synthetic execution does not replace the missing live results.

## Run locally

```bash
uv sync --locked --python 3.12.13
uv run --locked context-engine benchmark-check
uv run --locked context-engine benchmark-check --fact database --budget 3000
uv run --locked context-engine benchmark-check --show-content --output output/new-check.json
uv run --locked context-engine benchmark-plan
uv run --locked pytest -q
```

`benchmark-check` validates frozen inputs, prepares A0/A5 for one fact, verifies saved-request integrity, reports independent evidence metrics and demonstrates five intentional corruptions. Default output excludes assembled request bodies. `--show-content` explicitly includes synthetic requests; `--output` refuses overwrite. `--data-dir` can test a copied/corrupted bundle but is checked against the installed package's reference freeze, not a replacement reference supplied by that directory.

`benchmark-plan` lists all 744 slots: 31 facts × six variants × two PRD model identifiers × two budgets. It neither sends requests nor reserves provider funds. The conservative input-plus-completion reservation before retries is calculated from the plan; it is not measured usage or a pricing quote. Provider availability, retry policy, quota admission and actual spend are C05/C06.

These commands use the frozen protocol, not environment overrides such as `CONTEXT_BUDGET_TOKENS`. A different Python patch version, dependency version, source file or resource byte fails the reference freeze. Use the recorded environment to reproduce C04; the general SDK remains Python 3.12+. First installation/tokenizer vocabulary loading may require networking, but there are no inference calls.

## Resource boundaries

Evaluation JSON resources live in `src/context_engine/evaluation/data/` and ship inside the wheel:

| File | Purpose |
|---|---|
| `scenario.json` | Authorized synthetic history, scope, fixed evaluation time and system instructions; no grading metadata. |
| `ground_truth.json` | Exactly 31 fact IDs, expected values/aliases, questions, source turn/message IDs and age zones. Never passed as an engine argument. |
| `summary_fixture.json` | Frozen background text and policy version; bound to exact omitted history without generating new text. |
| `pin_retention.json` | Separate synthetic PIN test, outside the retrieval-focused primary corpus. |
| `protocol.json` | Six variants, budgets, model/generation identifiers, layer settings, grading and proposed thresholds. |
| `freeze.json` | Exact resource hashes, code hash, package/Python/dependency identity. |

All 100 turns have stable IDs; Turn 82 includes paired historical assistant/tool messages with the flagship fact in the tool message's middle. The 31 facts occupy early (turns 1–33: 10 facts), middle (34–66: 11) and late (67–100: 10) zones. Every declared value occurs in exactly its declared source message. Unknown fields, duplicate JSON keys, malformed UTF-8, invalid sources and cross-source answer collisions fail validation.

The flagship raw request measures **15,521 serialized tokens / 16,608 calibrated estimated tokens**. The PRD's approximately 17,700 is illustrative; it is not copied into results. This fixture is a deterministic mechanism test, not a real incident transcript or representative workload benchmark.

## Public-engine ablations

A1–A5 use `assemble_context(..., options=AssemblyOptions(...))`; the core imports neither evaluation data nor a benchmark runner. The CLI is the composition entry point and may route to evaluation commands. Default assembly behavior is unchanged.

The six combinations are centrally declared in the protocol and checked against the implemented version-1 ladder: raw A0; WINDOW A1; CAP+WINDOW A2; CAP+PIN+WINDOW A3; add RETRIEVE A4; add SUMMARIZE A5. Disabling PIN is explicit and uses no durable facts; mandatory system/question reservation and final admission still run. Disabled retrieval/summary allocations become zero, leaving the rest to WINDOW. Disabled CAP uses untouched history for the working representation.

A0 constructs and counts the raw chronological request without context-layer selection. Its oversized request is recorded `non_fit`, never given a response or silently truncated. Literal answer presence in an oversized A0 request does not count as usable retained evidence. Raw historical tool pairing is validated by the shared request contracts.

## Independent measurements and five gates

`fact_present` tests literal normalized aliases in the final message contents using identifier-aware boundaries: `shard-1` cannot match `shard-19`. `retained_evidence` additionally requires that the actual rendered WINDOW message or retrieved chunk matches the declared original source. An original-source tag alone cannot claim a fact removed by CAP survived. Ground-truth values are used only after assembly for measurement.

Answer grading accepts a normalized exact alias or a JSON object with only a string `answer` field. Extra prose, conflicting answers, duplicate JSON keys and unsupported structures fail grading. No LLM judge is used. Unicode compatibility, case and whitespace are normalized; declared aliases, not substring luck, permit alternate values. `UNKNOWN` is an abstention. Summary leakage detection is deliberately more conservative than answer grading; neither detector proves absence of semantic paraphrase leakage.

| Gate | Implemented check |
|---|---|
| V1 | Schema, 100/31 cardinality, stable/unique IDs, source/value locations, zones, summary time and separate pin fixture. |
| V2 | No answer aliases in system/questions/summary, no primary answer pins, no evaluator fields in scenario inputs. |
| V3 | Reassemble/recount each saved request; compare request, estimates, evidence, slot identity and response grades; reject duplicate/unknown IDs and admitted non-fit requests. |
| V4 | Every planned probe has a disposition; preserve errors and finish reasons; truncations invalidate acceptance. Missing/pending generations remain incomplete. |
| V5 | Resource bytes, source/version/runtime and full manifest agree with the reference freeze. |

`PREPARED` means admitted contexts await inference, not a passing model run. Missing slots produce `INTERRUPTED`; integrity/truncation failures produce `INVALID`. Fully completed synthetic response fixtures are `TEST_ONLY`, even if all gates pass. `VALID` means measurement integrity, not good quality. Quality acceptance additionally requires owner-approved registration and a complete primary workload; a valid run can fail quality.

Statistics separate model/budget/variant groups, literal measured presence, fitting source-backed retention, all-planned correctness and completed-response correctness. Zero denominators produce null rates. Counts for errors, abstentions, non-fit, pending and truncated outcomes remain visible. Wilson intervals are provided without treating a single correlated synthetic scenario as population evidence. Unknown provider usage and cost stay unknown; no model answer is inferred from retrieved text.

## Resume without reinterpreting results

`evaluation.protocol.make_manifest` selects declared facts/models/budgets/variants and assigns stable run/probe hashes. `evaluation.harness.prepare_probe` preflights then assembles a slot. `evaluation.results.record_response` accepts supplied response data with explicit `test`, `live` or `replay` provenance; it does not call a provider. Real completed responses require provider request IDs, and replay requires an ancestry reference. These fields are audit metadata, not cryptographic proof of a provider call; C05 supplies trusted adapter/cache records.

`save_run(path, bundle, freeze, manifest, records)` writes a new immutable snapshot only after validation. `load_run(...)` checks the embedded manifest/run ID and reassembles saved requests before returning pending probe IDs. Prepared/missing slots remain pending; non-fit and recorded terminal errors do not get silently retried. Retry/attempt accounting belongs to C05. Snapshot files are bounded at 32 MB; individual bundle inputs at 2 MB. This is local snapshot integrity, not transactional multi-worker storage.

The [saved resume example](../output/c04-resume.json) contains only synthetic requests, with A0 non-fit and one A5 slot pending; the [owner check](../output/c04-benchmark-check.json) hides request bodies. The latter records Turn 82 as the first retrieved source, 804/900 estimated input tokens, no model answer, and five intentional invalid examples. Additional low-relevance chunks are visible in diagnostics; settings were not tuned to force a perfect retrieval result.

Verification: 233 tests, including 84 C04 cases and preparation of all 31 primary probes at 900 tokens. Source/fixture freezing, alias boundaries, all four presence/correctness combinations, ablation behavior, response truncation, corruption and resume round-trips are covered. Installed-wheel resources must pass the same offline checks outside the repository.
