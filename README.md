# Context Engine

Fit long conversations into a fixed token budget for any LLM, and know exactly
where every piece of context came from.

`context-engineering-core` is a small Python library. You give it the full chat
history, the new question and a token budget. It returns a list of chat messages
that fits the budget. Those messages keep the recent turns, the facts you pinned,
and the older evidence that matches the question. It never calls a model by
itself, so you send the messages to any provider you like.

> **Status: alpha (0.14.0).** Good for developers to try locally. It is not yet
> proven on real-world data, and there is no hosted service. See
> [What is not proven yet](#what-is-not-proven-yet).

## Install

Requires Python 3.12+.

```sh
pip install context-engineering-core        # after the first PyPI release
```

From source:

```sh
git clone https://github.com/Nandu1729/Context-Engine.git
cd Context-Engine
uv sync --locked
uv run context-engine check                  # prints "deps ok"
```

The first run downloads the tokenizer vocabulary (tiktoken `o200k_harmony`) once.
After that, everything works offline.

## Quick example

```python
from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

scope = Scope("my-app", "chat-1")
notes = [f"Note {i}: shipment {i} left from dock D-{i}." for i in range(300)]
history = [Turn(f"t{i}", scope, (Message(f"m{i}", Role.USER, text),)) for i, text in enumerate(notes)]

result = assemble_context(history, "Which dock did shipment 42 leave from?", KeyedPins(scope),
                          BudgetConfig(input_cap=900), system="Answer only from the context.")
print(result.diagnostics.estimate.estimated_tokens, "of", result.diagnostics.input_allowance)
print("evidence from turns:", result.diagnostics.retrieved_turn_ids)
messages = result.messages  # ready for any chat-completions API
```

The 300 notes are far over the 900-token budget. The result fits (about 716 of
900 tokens), and turn `t42`, the one with the answer, is among the retrieved
evidence. Then send `messages` to OpenAI, Anthropic, Groq or a local model.

## Use it with your provider

`context_engine.adapters` reshapes the result for common clients. None of them is
a dependency of the engine:

```python
from context_engine.adapters import anthropic_messages, langchain_messages, openai_chat, turns_from_openai

openai_client.chat.completions.create(model="...", **openai_chat(result))             # OpenAI, Groq, local servers
anthropic_client.messages.create(model="...", max_tokens=512, **anthropic_messages(result))
chat_model.invoke(langchain_messages(result))  # pip install 'context-engineering-core[langchain]'

history = turns_from_openai(existing_openai_messages, scope)  # reuse a chat history you already have
```

### Better recall for reworded questions (optional)

Keyword search needs the question to reuse the fact's words. Add a small local
embedding model so meaning matches too ("retailer" finds "merchant"):

```python
# pip install 'context-engineering-core[semantic]'   (~30 MB model, downloaded once)
from context_engine.embeddings import Model2VecEmbedder

embedder = Model2VecEmbedder()   # pinned minishlab/potion-base-8M; loads only when you create it
result = assemble_context(history, question, pins, budget, system=system, embedder=embedder)
```

Ranking becomes 0.7 x meaning score + 0.3 x keyword score. Prefer accuracy over
speed? `FastEmbedEmbedder("BAAI/bge-small-en-v1.5")` (extra `[fastembed]`). Or wrap
your own embedding function or API with `FunctionEmbedder`.

### Use it from an MCP client

`context-engine-mcp --data-dir ./context-memory` runs a local MCP server (stdio) with
`add_message`, `pin_fact`, `get_context` and `forget` tools. Prototype; see the
[MCP guide](https://github.com/Nandu1729/Context-Engine/blob/main/docs/MCP.md).

## How it works

Every call runs five steps, in this order:

| Step | What it does |
|---|---|
| CAP | Shortens very long messages (keeps the start and end). |
| PIN | Always includes facts you pinned with `KeyedPins`. |
| RETRIEVE | Finds older text that matches the question (BM25), including text that CAP cut from recent turns. |
| WINDOW | Keeps as many recent turns as fit. |
| SUMMARIZE | Adds a summary of older turns, if you supply one. |

You can turn each step on or off with `AssemblyOptions`. For a chat that keeps
growing, `MemoryStore` saves turns, pins and summaries in SQLite. The
[rolling summary example](https://github.com/Nandu1729/Context-Engine/blob/main/examples/rolling_summary.py) shows a full loop.

## What the engine guarantees

These are enforced in code and covered by about 1,400 tests:

- **Within budget, or a clear error.** The result never exceeds your input
  budget as counted by the local tokenizer. If the required parts (system
  prompt, question, pins) cannot fit, you get a typed error, not a silently
  cut prompt.
- **Provenance.** Every recent-turn and retrieved block carries source
  references: turn, message, revision, character range and a content hash.
  A summary records which turns it covers and their hashes, and is rejected if
  any of them changed. `result.diagnostics` lists which turns were kept,
  retrieved or dropped, and why.
- **No hidden model calls.** Assembly is local and deterministic. Summaries are
  made only when you call `update_summary()`, with a summarizer you choose.
- **History is data, not instructions.** Older turns, retrieved text and
  summaries are labelled as data blocks inside user content, never as system
  instructions.
- **Your originals are never changed.** CAP and retrieval work on copies.
  Retrieval can bring back the original text of a capped message.

## What is not proven yet

- **Answer quality.** Tests measure whether the needed facts *reach* the model's
  context, not whether the model then answers correctly. On the built-in
  benchmark, the default settings keep 31 of 31 planted facts at 900 and 3000
  tokens, and a live model run answered 31 of 31 correctly at 900 tokens. But
  that benchmark is one synthetic conversation written alongside the engine.
- **Reworded questions.** By default, retrieval is keyword-based (BM25). When we
  reword the 31 benchmark questions so they share no words with the stored facts,
  the default settings keep only 3 of 31 facts. With the optional embedder (see
  above) they keep 21 of 31 (retrieval alone: 24–25 of 31), with no loss on the
  original questions. Run it yourself:
  `context-engine strategy-eval --questions paraphrased --semantic`.
- **Real-world data.** There are no results yet on real user conversations.
- **Exact provider token counts.** Budgets use a local tokenizer estimate.
  Providers may count differently. On small requests, provider counts were up
  to 1.78× the local estimate in past tests, so leave headroom or calibrate.
- **Speed.** With all five steps on, assembly takes about 250–350 ms on the
  benchmark (about 17–35 ms without CAP). Faster CAP is on the roadmap.
- **Production use.** The local HTTP service is for development. It has not
  been load-tested or security-qualified for production.

## Try it

```sh
uv run context-engine demo-layers                         # the five steps on sample data
uv run --offline context-engine strategy-eval --budget 900   # compare strategies, no model calls
uv run --offline python examples/rolling_summary.py       # memory + rolling summaries
```

## Documentation

- [SDK and CLI guide](https://github.com/Nandu1729/Context-Engine/blob/main/docs/PIPELINE.md): inputs, options, diagnostics, summaries.
- [Benchmark report](https://github.com/Nandu1729/Context-Engine/blob/main/docs/BENCHMARK_REPORT.md): strategy comparison and its limits.
- [Security audit](https://github.com/Nandu1729/Context-Engine/blob/main/docs/SECURITY_AUDIT.md): trust boundaries and known gaps.
- [Architecture](https://github.com/Nandu1729/Context-Engine/blob/main/docs/ARCHITECTURE.md) and [current status](https://github.com/Nandu1729/Context-Engine/blob/main/docs/CURRENT_STATUS.md).
- [Changelog](https://github.com/Nandu1729/Context-Engine/blob/main/CHANGELOG.md).

## For contributors

```sh
uv sync --locked
uv run --locked --offline pytest -q
uv run ruff check src
```

The repository also holds frozen historical benchmarks under `archives/` and
`output/`, and a project log under `brain/` (start at `brain/INDEX.md`; check it
with `python3 scripts/brain.py check`). Historical experiments only run with their
archived wheels, on purpose. The [local quickstart](https://github.com/Nandu1729/Context-Engine/blob/main/docs/LOCAL_QUICKSTART.md)
and [checkpoints](https://github.com/Nandu1729/Context-Engine/blob/main/docs/CHECKPOINTS.md)
cover the full project history.

## License

[Apache-2.0](https://github.com/Nandu1729/Context-Engine/blob/main/LICENSE).
