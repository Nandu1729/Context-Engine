# LongMemEval local import and offline demo — TEST_ONLY

2026-09-29, D098. The owner supplied `longmemeval_s_cleaned.json` after requesting
a small Hugging Face dataset demo. Import and inspection are complete; answer
quality, official benchmark evaluation and production qualification are not.

## What happened to the supplied file

Read `/Users/nandyyy/Downloads/longmemeval_s_cleaned.json` without modifying it.
Validated all 500 rows, their parallel session lists, roles, dates, UTF-8 text,
question identities and annotation contracts. Size: 277,383,467 bytes. SHA-256
before and after processing:

```text
d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442
```

Read-only Hugging Face metadata for the
[publisher dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
reported the same size and LFS SHA-256 at revision
`98d7416c24c778c2fee6e6f3006e7a073259d48f`. This establishes file identity, not
factual correctness, privacy approval or redistribution rights. No corpus upload,
second download, training, credential access or model inference occurred.

## Adapter and outputs

Added `scripts/longmemeval_demo.py` and synthetic regression tests in
`tests/test_longmemeval_demo.py`. Reused `scripts/incident_demo.py`
with a configurable title.
Core 0.9.6 and source freeze remain unchanged:
`304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.

The deterministic selection takes the first source row in each of five categories,
without filtering by answer availability or assembly success. Each original
message becomes one inspection-v1 turn, retaining its exact role, text, order
and session timestamp. Positional IDs avoid collisions; a separate mapping retains
original session IDs and positions. This is an adapter convention, not a claim
that a source session equals an engine turn.

Expected answers, answer-session IDs and `has_answer` annotations are stored only
in separate `labels.json` files and never supplied to assembly. Annotations are
consulted afterward for conservative emitted-text coverage. Natural evidence
already present in the original history remains unchanged.

Created `output/private/longmemeval-demo-001/`: 32 files, 10,725,467 bytes:

- Five complete mapped `input.json` files and five separate `labels.json` files.
- Ten content-enabled HTML inspections and ten assembly JSON exports.
- One HTML index and one metadata/coverage `report.json`.

The output directory is Git-ignored and created owner-only on this Mac. Content
exports contain corpus text: keep them local/private. Existing outputs are never
overwritten. No entire-corpus copy or persistent memory database was created.

## Actual results

All 10 assemblies completed under their estimated budgets. Default CAP35,
recovery OFF, retrieval reserve280 and summary reserve0 were retained. No settings
were tuned to improve these observations. Source messages are preserved in inputs;
assembled working contexts intentionally omit or cap content to fit the budget.

| Category | Source row (zero-based) | Sessions / messages | Tokens at 900 / 3000 | Complete marked messages at 900 / 3000 |
| --- | --- | --- | --- | --- |
| Single-session user | 0 | 53 / 550 | 846 / 2963 | 1 of 2 / 0 of 2 |
| Multi-session | 70 | 44 / 484 | 843 / 2957 | 1 of 3 / 1 of 3 |
| Temporal reasoning | 233 | 48 / 484 | 837 / 2983 | 0 of 2 / 0 of 2 |
| Knowledge update | 366 | 40 / 413 | 858 / 2902 | 2 of 2 / 1 of 2 |
| Abstention | 64 | 52 / 523 | 896 / 2956 | Not applicable / Not applicable |

“Complete marked messages” requires exact original text coverage in emitted
WINDOW/RETRIEVED content, not merely a retained source ID. A partially retained
message may still contain the answer; this metric is neither answer-span recall
nor answer accuracy. The abstention example has no positive message annotations;
that is not proof the engine or a model would abstain correctly. There are only
five source examples, not ten independent examples or a full 500-example benchmark.

The larger budget did not consistently improve complete-message retention.
Review emitted evidence before inference or optimization; do not call these
assemblies a quality pass. Per-call local timings are diagnostic, not an SLO.

## Source and mapping caveats

Across 500 rows: 13 have duplicate session IDs, 211 have dates out of order and
76 have sessions dated later than their question. Counts overlap. These were
flagged, not silently deduplicated, sorted or removed. Selected temporal/update
examples have out-of-order dates; none of the five has future sessions or
duplicate session IDs.

Source dates lack a timezone. The adapter uses an explicit UTC schema convention
and retains original date strings separately; the real timezone is unverified.
Turn timestamps are not automatically included in the current model-facing text.
This limits temporal interpretation and must be addressed in a separately
reviewed evaluation mapping before temporal-answer qualification. Cases with
future sessions must not be treated as valid historical cutoffs without review.

The adapter rejects malformed/oversized inputs rather than silently truncating
them. Source size is bounded at350MB, rows at1000 and mapped inspection inputs at
the existing2MB limit. Rejected selected cases retain both planned budget slots.
Assembly runs under the existing Python network guard; cached tokenizer data is
required. No new dependency or Hugging Face SDK was installed.

## Open and repeat

Verification: all 19 adapter tests and 64 related demo/preflight/inspection/brain
checks pass (83 scoped tests). Scoped Ruff checks pass. Independently compared
every selected exported message's text, role and order, the current question and
input hashes against the downloaded source. Inspected the dashboard in an isolated
headless browser at1440×1050 and stopped that browser afterward. No full-suite or
remote CI rerun; historical three-platform evidence does not include these files.

Open the prepared dashboard locally:

```sh
open "/Users/nandyyy/Project/Context Engineering/output/private/longmemeval-demo-001/index.html"
```

To repeat intentionally, use a new output directory from the repository root:

```sh
uv run --locked --offline python -m scripts.longmemeval_demo \
  --input /Users/nandyyy/Downloads/longmemeval_s_cleaned.json \
  --output output/private/longmemeval-demo-002
```

Next: inspect the five cases, especially missing/partial evidence and temporal
mapping. Expand offline coverage only after reviewing the mapping; do not yet
download another large corpus or claim real-world answer quality. Any inference
needs a separate approved bounded budget. License/privacy review is still required
before redistribution or use beyond this local inspection.
