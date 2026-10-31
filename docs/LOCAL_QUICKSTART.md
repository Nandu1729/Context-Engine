# Start here: your local context-engine demo

You do not need an API key, a downloaded dataset or programming knowledge to inspect
this demo. It uses a **made-up incident conversation**, not your personal messages
and not LongMemEval. The engine selects conversation evidence;it does not generate
an AI answer in this demo.

## 1. Open the prepared example

On this Mac, open Terminal and paste these two lines together:

```sh
cd "/Users/nandyyy/Project/Context Engineering"
open output/local-demo-001/index.html
```

This opens a saved local HTML file. No server, login or deployment is needed.
On another computer, open `output/local-demo-001/index.html` from its file manager.

## 2. Understand what you are looking at

The fictional story has12 conversation turns:

- `t01`: checkout-v42 changed the service connection pool from20 to80.
- `t08`: rollback was only being considered.
- `t09`: rollback actually happened,to checkout-v41,and the pool returned to20.
- `t11`: a deliberately hostile tool message tries to claim checkout-v99 is active.
  This stays untrusted history data,not a new system instruction.
- `t12`: no final root cause has been established.

The question asks what changed and what rollback was recorded. Expand the original
history and compare it with the assembled messages. Find `checkout-v41` in the
assembled output. That shows relevant text survived selection—not that a model
answered correctly or that every conversation detail was retained.

The sample fits838estimated input tokens within900. It deliberately uses an80token
per-message cap;the product default is35. This teaching sample does not change the
default or demonstrate every workload will retain its answer. The retrieval-union
research candidate is **not** used here.

## 3. Run the real local checks

In the same Terminal window:

```sh
uv run --locked --offline python -m scripts.local_demo
```

Expected output begins:

```text
PASS: local synthetic demo (not production qualification)
SDK: 12 sample turns -> 838/900 estimated input tokens; deployment and rollback evidence retained.
Memory: restart, index reuse, deletion and deletion-safe restore checks passed.
No AI answer generated. No API key needed. No model calls made.
```

This uses the public Python SDK to assemble the sample and separately tests memory
with temporary synthetic databases. Those temporary databases are cleaned up when
the check finishes;your project stores and original dataset are not touched.
It does not launch the HTTP service or test production operations.

Optional: save a new metadata-only report. Pick an unused path each time:

```sh
uv run --locked --offline python -m scripts.local_demo --output output/local-demo-MY-RUN/report.json
```

## If a setup error appears

The current project environment is already set up. On a fresh machine,installation
and the first public tokenizer download require internet access,but no API key:

```sh
uv sync --locked --all-extras --python 3.12.13
uv run --locked context-engine check
```

Then repeat step3. If it fails,send the short error here. Do not add credentials or
run a live benchmark to troubleshoot this offline demo. The script blocks Python
socket connections while checking;this is not an operating-system network sandbox.

## 4. Try using the engine from Python

The next example shows how your own application can call the engine. It uses three
short, made-up incident records, not the downloaded Hugging Face dataset. Paste:

```sh
cd "/Users/nandyyy/Project/Context Engineering"
uv run --locked --offline python examples/sdk_quickstart.py --show-context
```

Look for `CONTEXT READY` at the top. Below it are the messages prepared for a model.
They include the recorded rollback to `checkout-v41` and the pool size of `20`.
This is **prepared context, not a generated answer**. Nothing is sent to a model or
saved to a database. Without `--show-context`, only a short status is printed.

Your small practice task: change only the question by running:

```sh
uv run --locked --offline python examples/sdk_quickstart.py --show-context --question "Has the root cause been confirmed?"
```

The final user message changes to your question; the history still says the root
cause is not confirmed. Small histories may retain the same evidence for different
questions. You do not need to edit any files or approve dataset ratings.

For a developer: `examples/sdk_quickstart.py` is a standalone example using only
the installed public SDK and Python's standard library. `prepare_context()` returns
an `AssembledContext`; `result.messages` provides fresh message dictionaries for a
separately configured model adapter. It does not generate answers or persist memory.
The caller must authorize history access; tenant/session labels are not authentication.
Do not print real conversation content by default or put secrets in command arguments.

The example uses default CAP/retrieval behavior and an explicit900token budget with
no summary reserve. No product defaults changed. As with step3, dependencies and
public tokenizer vocabulary must already be cached: `uv --offline` restricts uv,
not arbitrary Python networking. First-time setup is described above.

## After the Python example

The owner has now run both SDK questions and the authenticated local API demo;
the supplied API output reports PASS for all five checks and a stopped server.
Those walkthrough steps do not need repeating.

`sample_app.py` now provides the small application connection. To ask a question
interactively, run:

```sh
uv run --locked --offline python sample_app.py --show-context
```

Type a question about the made-up incident and press Enter. The application calls
the existing SDK and displays prepared messages, not an AI answer. It exits after
one question; no conversation is saved. Ctrl+C cancels. Omit `--show-context` for
status-only output. This app requires the repository's `examples/sdk_quickstart.py`.

For a non-interactive run:

```sh
uv run --locked --offline python sample_app.py --question "Which version did we roll back to?" --show-context
```

This connection has already been tested end to end; rerunning it is optional.
A persistent server is unnecessary for this direct Python integration.

## 5. Use your existing LongMemEval dataset

The dataset connection is complete. No new download, Hugging Face account, API key
or manual conversion is needed on this machine. Run:

```sh
uv run --locked --offline python sample_app.py --longmemeval
```

Expected output includes:

```text
LongMemEval development row 49: existing baseline input, recovery OFF.
Loaded source turns: 512
CONNECTED: your application received prepared context, not an AI answer.
Estimated input tokens: 892/900
```

This uses the existing converted `row-049/input-baseline.json` under
`output/private/longmemeval-review-001/`. It loads the saved question and conversation,
not the sibling reference-answer file. The question concerns a bedside-lamp bulb.
It does not assemble all500dataset rows or use the70reserved held-out examples.
Successful assembly does not mean every fact was retained or an answer was correct.

To inspect the prepared messages locally, explicitly add `--show-context`:

```sh
uv run --locked --offline python sample_app.py --longmemeval --show-context
```

Keep dataset content private; don't paste the full output into public issues.
The original download and saved experiment files are never overwritten. The app
does not store new conversations, score answers or contact a model.

For another already-converted development input, use `--input PATH_TO_INPUT.json`.
Use only one source option. Dataset mode uses its saved question, so do not combine
it with `--question`. The strict loader rejects raw corpus arrays, label files and
unsupported fields;do not pass the original277MBdownload directly. Input files are
bounded to2MB. Settings in a converted input are honored rather than silently changed.

The shortcut resolves from the app's directory,not the current working directory.
On a machine without the private converted file, it fails without downloading or
reading credentials. This repository app blocks Python socket connections during
preparation and requires cached tokenizer vocabulary;this is not an OS sandbox.
Earlier standalone SDK examples do not provide that socket guard.

## 6. View the completed AI-answer test

The separately approved one-request test is complete. It used development row49's
prepared context and returned a successful answer consistent with its local
reference. See the [one-request report](C10_SAMPLE_ANSWER_REPORT.md).

To show the saved answer without calling a model again:

```sh
uv run --locked --offline python -m scripts.sample_answer status --show-answer
```

This reads the recorded receipt and verifies it against the shared ledger. It does
not send another request. The normal sample app remains an offline context tool.
The one-call approval is consumed;do not reset evidence or reinitialize another run.

To change the question later,use the [incident demo guide](INCIDENT_DEMO.md).
For integration,use the public `assemble_context` function documented in the
[SDK guide](PIPELINE.md),or the separately configured authenticated local API in the
[service guide](SERVICE.md). Repository demo scripts are not installed SDK commands.

This completes a local development demonstration,not enterprise acceptance.
Original C09–C12 qualification gates remain open;see the
[completion audit](PROJECT_COMPLETION_STATUS.md).
