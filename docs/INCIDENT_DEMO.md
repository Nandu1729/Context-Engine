# Local incident demo — sample data first

This is a browser-viewable context inspection, not an answer-generating chatbot.
It uses the real context engine with twelve synthetic incident turns. No API key,
model call, web server or Hugging Face download is needed. The HTML has no scripts
or external resources. Expand history records and compare the assembled messages.

## Open the prepared demo

From the project directory on macOS:

```sh
open output/incident-demo-002/index.html
```

The prepared sample uses838estimated input tokens within a900token allowance.
Seven turns contribute WINDOW context;four older turns contribute retrieved
chunks. These counts do not imply complete retention. Read the actual output.
The sample explicitly uses an80token message cap;the product's35token default
can clip the rollback version from the middle of a kept turn. No core default
was changed. This illustrates why source IDs alone cannot establish retention.

## Change the sample or question

Edit `examples/incident-demo.json`, then generate a new report. Never overwrite
an earlier report. The first draft at `output/incident-demo-001/index.html` used
the smaller default cap;use002for the current prepared example.

```sh
uv run --locked --offline python scripts/incident_demo.py --show-content --output output/incident-demo-003/index.html
open output/incident-demo-003/index.html
```

Or try another question and budget:

```sh
uv run --locked --offline python scripts/incident_demo.py --question "Is a final root cause recorded?" --budget 1200 --show-content --output output/incident-demo-004/index.html
```

Without `--show-content`, only aggregate counts and estimates are exported;
question,history,source IDs and diagnostics are withheld. With the flag,HTML
contains plaintext data and must be protected like its input. Avoid sensitive
questions on the command line because shells can retain them. Set those in a
private input file instead. Existing output paths are refused before assembly;
exclusive creation also protects against concurrent overwrite.

The existing project environment and tokenizer cache are prerequisites.
`--offline` stops uv downloads;the generator also blocks Python socket
connections/DNS. Missing tokenizer vocabulary fails instead of downloading it.
This guard is not an OS network sandbox. No new dependencies were added.

## Later: replace the sample with Hugging Face data

First choose a dataset URL,configuration,revision,split and a small row range.
Check its license and permission to use the data;review/redact sensitive fields.
No dataset or field mapping is assumed yet. Different datasets need different
mappings;the generator does not directly accept arbitrary CSV,JSONL or Parquet.

Map a bounded selection to the existing inspection-v1 JSON shape used by the
sample: `schema_version`, `scope`, `system`, `question`, `at`, and `history`.
History contains unique turn IDs and messages with unique message IDs,roles and
content. Use timezone-aware timestamps. Keep unrelated sessions separate.
Keep dataset-provided answer labels,solutions and evaluation metadata in a
separate file,never in history,pins or system instructions. System instructions
must be application-controlled,not copied from an untrusted dataset row.
Only map evidence actually available before answering the question.

The loader accepts at most2,000,000bytes/10,000turns;start much smaller for an
interactive workflow. Unsupported fields,duplicate JSON keys and invalid
contracts are rejected. Public dataset provenance does not establish truth.

```sh
uv run --locked --offline python scripts/incident_demo.py --input output/private/hf-demo-input.json --show-content --output output/private/hf-demo-001.html
```

This command reads an already mapped local file;it downloads nothing. Do not
commit real inputs or content-enabled reports. Future dataset integration and
any model-backed answer demo require separate source selection and approval.

## Development checks

Ten new tests cover real assembly/selection,explicit CAP behavior,determinism,
privacy,HTML escaping/no active resources,question/budget/cwd overrides,strict
input rejection,network blocking/restoration,redacted failures and overwrite
protection. Local browser rendering inspected at1440×1050. Prior cross-platform
CI did not include these new repository-only files. Core0.9.6 and frozen quality
evidence are unchanged;this demo does not satisfy the open C09 quality gate.

Final local run:64tests PASS2.40s across demo,incident preflight,inspection and
brain-integrity modules. Scoped ruff,brain index/check and diff whitespace checks
PASS. No full-suite or remote CI rerun was performed for these repository additions.
