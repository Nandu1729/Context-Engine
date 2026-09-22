# Context Engineering Layer for Long-Running AI Agents

> **Product Requirements Document (PRD) + Technical Specification**  
> **Version:** 1.0  
> **Status:** Build Specification  
> **Primary Language:** Python 3.12+  
> **Baseline Inference Provider:** Groq  
> **Baseline Models:** `openai/gpt-oss-120b`, `openai/gpt-oss-20b`  
> **Primary Retrieval Method:** BM25 (`rank-bm25`)  
> **Project Type:** AI Infrastructure / Agent Middleware + Evaluation Harness

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision](#2-product-vision)
3. [Problem Statement](#3-problem-statement)
4. [Goals](#4-goals)
5. [Non-Goals for V1](#5-non-goals-for-v1)
6. [Target Users](#6-target-users)
7. [Real-World Example](#7-real-world-example)
8. [High-Level Architecture](#8-high-level-architecture)
9. [Execution Order](#9-execution-order)
10. [Final Prompt Assembly Order](#10-final-prompt-assembly-order)
11. [Layer 1 — CAP](#11-layer-1--cap)
12. [Layer 2 — PIN](#12-layer-2--pin)
13. [Layer 3 — RETRIEVE](#13-layer-3--retrieve)
14. [Layer 4 — WINDOW](#14-layer-4--window)
15. [Layer 5 — SUMMARIZE](#15-layer-5--summarize)
16. [Context Blocks](#16-context-blocks)
17. [Turn Model](#17-turn-model)
18. [Original vs Working Representations](#18-original-vs-working-representations)
19. [Token Budgeting](#19-token-budgeting)
20. [Budget Formula](#20-budget-formula)
21. [Default Budget Configuration](#21-default-budget-configuration)
22. [Output Reservation](#22-output-reservation)
23. [Token Counting](#23-token-counting)
24. [Tokenizer Calibration](#24-tokenizer-calibration)
25. [Prompt Cache Strategy](#25-prompt-cache-strategy)
26. [LLM Inference](#26-llm-inference)
27. [Generation Configuration](#27-generation-configuration)
28. [Provider Rate Limits](#28-provider-rate-limits)
29. [Daily Ledger](#29-daily-ledger)
30. [Replay Cache](#30-replay-cache)
31. [Pricing Model](#31-pricing-model)
32. [Measurement Harness](#32-measurement-harness)
33. [Benchmark Scenario](#33-benchmark-scenario)
34. [Ground Truth](#34-ground-truth)
35. [Key Measurement — `fact_present`](#35-key-measurement--fact_present)
36. [Grading](#36-grading)
37. [Ablation Ladder](#37-ablation-ladder)
38. [Pre-Registered Success Criterion](#38-pre-registered-success-criterion)
39. [Validity Gates](#39-validity-gates)
40. [Frozen Summary and Leakage Gate](#40-frozen-summary-and-leakage-gate)
41. [Probe Execution](#41-probe-execution)
42. [Small-N Statistics](#42-small-n-statistics)
43. [Scorecard](#43-scorecard)
44. [Figures](#44-figures)
45. [Leaderboard](#45-leaderboard)
46. [Results](#46-results)
47. [Project File Structure](#47-project-file-structure)
48. [Configuration Architecture](#48-configuration-architecture)
49. [Configuration Dependency Rule](#49-configuration-dependency-rule)
50. [Environment Variables](#50-environment-variables)
51. [Security Requirements](#51-security-requirements)
52. [Runtime Reliability](#52-runtime-reliability)
53. [Cross-Platform Requirements](#53-cross-platform-requirements)
54. [Dependencies](#54-dependencies)
55. [Setup Validation](#55-setup-validation)
56. [API-Ready Output](#56-api-ready-output)
57. [Primary Pipeline Interface](#57-primary-pipeline-interface)
58. [Context Carrier](#58-context-carrier)
59. [Layer Contract](#59-layer-contract)
60. [CLI Requirements](#60-cli-requirements)
61. [Live Demo Requirement](#61-live-demo-requirement)
62. [Canonical End-to-End Benchmark Example](#62-canonical-end-to-end-benchmark-example)
63. [Performance Requirements](#63-performance-requirements)
64. [Cost Requirements](#64-cost-requirements)
65. [Observability](#65-observability)
66. [Error Handling](#66-error-handling)
67. [Build Gates](#67-build-gates)
68. [Reproducibility Requirements](#68-reproducibility-requirements)
69. [Acceptance Criteria](#69-acceptance-criteria)
70. [Future Enhancements](#70-future-enhancements)
71. [Product Differentiator](#71-product-differentiator)
72. [Final Product Definition](#72-final-product-definition)
73. [Glossary](#73-glossary)

---

## 1. Executive Summary

Long-running AI agents eventually accumulate far more conversation history, tool output, state, instructions, and metadata than should be sent to an LLM on every request.

Simply sending the complete history creates four major problems:

```text
Long Conversation
       ↓
Too many tokens
High API usage
Important facts buried in noise
Prompt cache instability
       ↓
Agent becomes expensive / unreliable / impossible to call
```

This product introduces a **Context Engineering Layer** between an agent's stored history and the LLM.

Its responsibility is:

> Given everything the application knows and a strict token budget, determine the smallest and most useful context that should be shown to the model for the current call.

The system uses five context-management stages:

```text
CAP
  ↓
PIN
  ↓
RETRIEVE
  ↓
WINDOW
  ↓
SUMMARIZE
```

The final LLM prompt is assembled in a deliberately cache-aware order:

```text
SYSTEM
PINNED FACTS
SUMMARY
RECENT WINDOW
RETRIEVED EVIDENCE
CURRENT QUESTION
```

The project also includes a **Measurement Harness** that proves whether the context layer actually works.

Therefore the full product consists of two tightly coupled systems:

```text
                    PRODUCT
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      Context Engine       Evaluation Harness
            │                     │
     Build the prompt       Prove it works
```

---

## 2. Product Vision

Build a reusable context-management layer that allows AI agents to operate reliably over long conversations while keeping every LLM request:

- within token constraints,
- focused on relevant information,
- capable of recovering old facts,
- aware of recent conversation,
- cost efficient,
- cache friendly,
- measurable,
- reproducible,
- portable into other agents.

The system should transform:

```text
Everything the application knows
```

into:

```text
Everything the LLM needs right now
```

---

## 3. Problem Statement

A production AI agent can accumulate:

- conversation messages,
- assistant responses,
- tool outputs,
- JSON payloads,
- incident logs,
- user decisions,
- persistent facts,
- application state,
- retrieved information.

A naive implementation repeatedly appends everything:

```text
SYSTEM
Turn 1
Turn 2
Turn 3
...
Turn 100
Question
```

This eventually breaks for three distinct reasons.

### 3.1 Failure 1 — Request becomes too large

The conversation may exceed:

- the model context window,
- provider token throughput constraints,
- application-defined token budgets,
- or available output headroom.

A model supporting a large context window does **not** imply the application can or should send that much context.

### 3.2 Failure 2 — Context rot

Even when a large request technically fits, the model can fail to use a specific fact buried inside a very large prompt.

Therefore:

```text
"It fits"
≠
"It works"
```

A successful context layer must satisfy both:

```text
FITS ✅
WORKS ✅
```

### 3.3 Failure 3 — Context optimization destroys caching

A naive sliding window changes the beginning of the prompt every turn:

```text
Call N:
T96 T97 T98 T99

Call N+1:
T97 T98 T99 T100
```

Because prompt caches generally rely on matching prefixes, excessive changes near the start of the prompt can reduce cache reuse.

Therefore context engineering must optimize:

```text
Token usage
+
Recall
+
Relevance
+
Cost
+
Cache stability
```

not merely shorten the prompt.

---

## 4. Goals

The product must:

1. Guarantee final prompts stay within an explicit token budget.
2. Preserve critical system instructions and durable facts.
3. Preserve conversational continuity using recent turns.
4. Retrieve relevant information from deep conversation history.
5. Compress broad historical context.
6. Prevent oversized tool responses from dominating context.
7. Preserve original uncapped messages outside normal prompt context.
8. Use query-dependent context near the end of the prompt for cache stability.
9. Count tokens before inference.
10. Reserve output tokens before filling input context.
11. Track provider rate-limit usage.
12. Measure context quality independently from model answer quality.
13. Benchmark multiple context configurations.
14. Produce reproducible results, statistics, plots, and a leaderboard.
15. Make the context layer portable into other AI agents.

---

## 5. Non-Goals for V1

The first version should **not** attempt to solve every memory problem.

V1 does not require:

- PIN itself to decide which facts are important.
- Automatic long-term fact extraction.
- Semantic vector retrieval as the primary retrieval method.
- Permanent knowledge storage inside the LLM.
- Replacing the LLM with search.
- A general reasoning benchmark.
- Sending all original history into every prompt.

Automatic memory extraction can be added later:

```text
New Turn
   ↓
Fact Extractor
   ↓
Important + durable?
   ↓
Pinned Fact Store
```

but this is an extension rather than part of the initial PIN contract.

---

## 6. Target Users

### Primary Users

AI/LLM engineers building:

- agentic systems,
- customer-support agents,
- coding assistants,
- incident-response agents,
- research assistants,
- tool-using assistants,
- long-running copilots.

### Secondary Users

Teams evaluating:

- LLM context strategies,
- model recall,
- prompt cost,
- model comparisons,
- context-window behavior.

---

## 7. Real-World Example

Consider a customer-support agent.

During a long conversation:

```text
Turn 3
Order ID = ORD-7821

Turn 8
Product = Black iPhone case

Turn 22
Courier API:
First delivery attempt was missed.

...

Turn 97
Customer:
Why is my package late?
```

Instead of sending all history, the context layer builds:

```text
[SYSTEM]
You are a customer-support assistant.

[PINNED]
Order = ORD-7821

[SUMMARY]
The customer has been discussing a delayed shipment.

[WINDOW]
Recent conversation...

[RETRIEVED]
Courier missed the first delivery attempt.

[QUESTION]
Why is my package late?
```

The LLM then generates the final answer.

Retrieval provides **evidence**.

The LLM provides:

- interpretation,
- synthesis,
- reasoning,
- formatting,
- natural-language generation.

For trivial deterministic lookups, a later optimization may bypass the LLM entirely.

---

## 8. High-Level Architecture

```text
                    FULL HISTORY STORE
                 (uncapped original turns)
                          │
                          │
Current user turn ────────┤
                          ▼
                 CONTEXT ENGINE
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
        Prompt Context          Searchable History
              │                       │
             CAP                    BM25
              │                       │
             PIN ◄──── Pinned Store   │
              │                       │
          RETRIEVE ◄──────────────────┘
              │
            WINDOW
              │
          SUMMARIZE
              │
              ▼
          ASSEMBLER
              │
              ▼
       Token Validation
              │
              ▼
             LLM
              │
              ▼
           RESPONSE
              │
              ▼
     Measurement Harness
```

---

## 9. Execution Order

The internal execution order shall be:

```text
CAP
 ↓
PIN
 ↓
RETRIEVE
 ↓
WINDOW
 ↓
SUMMARIZE
```

The execution order and final prompt order are intentionally different.

---

## 10. Final Prompt Assembly Order

The LLM-facing prompt shall be assembled as:

```text
[SYSTEM]

[PINNED FACTS]

[SUMMARY]

[WINDOW TURNS]

[RETRIEVED BLOCK]

[CURRENT QUESTION]
```

The design principle is:

```text
Stable information
        ↓
beginning of prompt

Query-dependent information
        ↓
end of prompt
```

This maximizes the length of the potentially cacheable prefix.

---

## 11. Layer 1 — CAP

### Purpose

Prevent individual oversized messages—especially tool responses—from consuming most of the context budget.

### Input

All conversation turns.

### Behavior

CAP shall:

- examine messages individually,
- leave short messages unchanged,
- truncate messages exceeding the configured threshold,
- preserve a head segment,
- preserve a tail segment,
- insert an explicit elision marker,
- never delete an entire turn.

Conceptually:

```text
ORIGINAL

HEAD
large middle section
possibly important content
large middle section
TAIL
```

becomes:

```text
CAPPED

HEAD
[... N tokens elided ...]
TAIL
```

### Critical Requirement

The full original message must remain accessible outside the normal prompt representation.

```text
Incoming Turn
     │
 ┌───┴──────────┐
 ▼              ▼
Original      Capped
Store          Copy
 │              │
RETRIEVE       WINDOW
```

CAP must therefore be treated as **prompt compression**, not source destruction.

### Prefix Stability

CAP should be deterministic:

```text
same message
→
same capped representation
```

Therefore CAP is prefix-stable.

### Baseline Guide Configuration

Example values shown in the benchmark:

```text
CAP threshold ≈ 35 tokens
Head ≈ 22 tokens
Tail ≈ 8 tokens
```

These must remain configurable.

---

## 12. Layer 2 — PIN

### Purpose

Guarantee critical information survives regardless of conversation length.

### Inputs

```text
System Prompt
+
Pinned Facts List
```

### Example

```text
Environment = production
Incident ID = INC-4281
Customer = PaySetu
Database = PostgreSQL
```

### Requirements

PIN shall:

- reserve token space before lower-priority layers,
- treat pinned information as non-evictable,
- produce a system block,
- produce a pinned-facts block.

Budget:

```text
Remaining Budget
=
B - system_tokens - pinned_tokens
```

### Important Behavior

PIN itself does **not** automatically discover important facts.

For V1:

```text
Application/developer
      ↓
defines/supplies facts
      ↓
PIN protects them
```

Potential future extension:

```text
Conversation
   ↓
Memory Extractor
   ↓
Pinned Facts Store
   ↓
PIN
```

### Fact Updates

Contradictory durable facts should be updated rather than duplicated.

Bad:

```text
DB = PostgreSQL
DB = MySQL
```

Good:

```text
DB = MySQL
```

### Prefix Stability

PIN is stable when its facts remain unchanged.

---

## 13. Layer 3 — RETRIEVE

### Purpose

Recover specific old information that WINDOW cannot preserve.

### Retrieval Engine

Baseline:

```text
rank-bm25
```

### Query

The current user question.

### Search Scope

Only turns expected to fall outside the recent WINDOW.

```text
WINDOW keeps:
95–100

RETRIEVE searches:
1–94
```

This prevents wasting retrieval budget on content that is already present.

### Lookahead

RETRIEVE must use the same budget splitting logic used by WINDOW to estimate:

```text
which turns WINDOW will keep
which turns WINDOW will lose
```

before WINDOW actually executes.

### Original-Content Requirement

Search/index should use original uncapped content wherever possible.

Otherwise:

```text
important middle content
        ↓
CAP removes it
        ↓
BM25 cannot see it
        ↓
retrieval failure
```

The strongest implementation should support chunking large original messages:

```text
Large original
      ↓
Chunks
      ↓
BM25 index
      ↓
Retrieve relevant chunk
```

rather than injecting an entire multi-thousand-token tool response.

### Retrieval Reserve

RETRIEVE must reserve space before WINDOW consumes remaining budget.

Example:

```text
Remaining after PIN = 680

Retrieve reserve = 280

WINDOW budget = 400
```

### Output

A query-dependent retrieved block.

### Cache Behavior

The block content varies by question, therefore it should be appended near the end of the final prompt.

---

## 14. Layer 4 — WINDOW

### Purpose

Maintain short-term conversational continuity.

WINDOW should:

- prefer most recent turns,
- walk backwards from the newest turn,
- stop when another turn would exceed its allocated token budget.

Example:

```text
History:
1 ... 100

Budget allows 4 turns

WINDOW:
97
98
99
100
```

### Role

```text
WINDOW
=
short-term / recency memory
```

### Limitation

WINDOW alone cannot reliably access old facts.

That responsibility belongs to RETRIEVE.

### Cache Behavior

WINDOW is not inherently prefix-stable because its starting turn changes as the conversation advances.

---

## 15. Layer 5 — SUMMARIZE

### Purpose

Maintain broad awareness of historical conversation that neither WINDOW nor RETRIEVE explicitly preserves.

### Input

Old conversation omitted by WINDOW.

### Output

One short summary block.

Example:

```text
Earlier discussion involved a production outage,
database saturation, and deployment debugging.
```

### Role

```text
RETRIEVE
= exact old evidence

SUMMARY
= broad old background
```

SUMMARY must not be relied upon for exact identifiers.

### Benchmark Requirement

The benchmark summary must not leak planted answers.

If the answer under test is:

```text
shard-19
```

the summary must not contain:

```text
shard-19
```

otherwise retrieval effectiveness cannot be measured honestly.

### Stability

Summary is not fully prefix-stable but may be amortized or periodically updated rather than regenerated from scratch every turn.

---

## 16. Context Blocks

The context system shall use logical blocks instead of treating everything as one flat history.

Required blocks:

```text
SYSTEM
PINNED
SUMMARY
WINDOW
RETRIEVED
QUESTION
```

A block is a labeled logical unit with:

- content,
- source,
- token count,
- ordering,
- stability characteristics.

This enables budget control, provenance, auditing, and cache-aware assembly.

---

## 17. Turn Model

A `Turn` shall represent a conversational exchange and may include:

```text
User message
Assistant reply
Tool output
```

Conceptual representation:

```python
@dataclass
class Turn:
    user: str
    assistant: str
    tool_output: str | None
```

The actual production model may contain additional metadata:

```text
turn_id
timestamp
tool_name
original messages
capped messages
token counts
```

---

## 18. Original vs Working Representations

The system must distinguish:

```text
Original Turn
```

from:

```text
Prompt/working Turn
```

Original history is used for:

- storage,
- retrieval,
- provenance,
- replay,
- debugging.

Capped versions are used for:

- normal context packing,
- recent WINDOW representation,
- lower prompt cost.

---

## 19. Token Budgeting

Token budgeting is a first-class product requirement.

The context layer must run **before every LLM call**, including internal agent calls after tool usage.

Example:

```text
User
 ↓
Context Engine
 ↓
LLM
 ↓
Tool
 ↓
Context Engine again
 ↓
LLM
```

The system shall not wait until the conversation becomes “long.”

At early conversation depth, the engine may simply determine that everything fits.

---

## 20. Budget Formula

The safe input allowance must consider:

```text
Model context capacity
Provider operational limits
Completion reservation
Application context budget
```

Conceptually:

```text
Provider input ceiling
=
provider token ceiling
-
MAX_COMPLETION_TOKENS
```

and:

```text
usable_context_budget
=
min(
    configured_context_budget,
    model_input_headroom,
    provider_input_headroom
)
```

The entire final prompt must satisfy:

```text
SYSTEM
+ PIN
+ SUMMARY
+ WINDOW
+ RETRIEVED
+ QUESTION
≤
B
```

---

## 21. Default Budget Configuration

Baseline:

```text
CONTEXT_BUDGET_TOKENS = 3000
```

Stress benchmark example:

```text
CONTEXT_BUDGET_TOKENS = 900
```

The budget must be configurable without editing the context algorithms.

---

## 22. Output Reservation

Baseline:

```text
MAX_COMPLETION_TOKENS = 256
```

This is primarily rate-limit/headroom arithmetic, not merely a stylistic answer-length choice.

The harness must measure truncation.

If truncation exceeds an allowed threshold:

```text
256 → 512
```

may be used, potentially with fewer probes to remain inside resource budgets.

---

## 23. Token Counting

Use:

```text
tiktoken
```

to count prompt tokens locally before sending requests.

The expected tokenizer in the baseline environment is:

```text
o200k_harmony
```

Setup must fail early if the required tokenizer is unavailable.

---

## 24. Tokenizer Calibration

Baseline:

```text
TOKENIZER_FUDGE = 1.07
```

Purpose:

```text
local token estimate
×
calibration factor
=
safer operational estimate
```

This value must be measured rather than treated as universal.

The application should intentionally budget conservatively where provider token accounting differs from local estimation.

---

## 25. Prompt Cache Strategy

Prompt cache compatibility is a core architectural objective.

Final ordering:

```text
SYSTEM
PIN
SUMMARY
WINDOW
────────────
RETRIEVED
QUESTION
```

Retrieved content must be a **suffix**, not chronologically injected into the middle.

Reason:

```text
Query A → retrieved Turn 82
Query B → retrieved Turn 43
```

If retrieval were inserted chronologically, prompts could diverge much earlier.

Suffix placement preserves more shared prefix.

---

## 26. LLM Inference

Baseline provider:

```text
Groq
```

Baseline primary model:

```text
openai/gpt-oss-120b
```

Comparison model:

```text
openai/gpt-oss-20b
```

Models must be overridable through configuration.

---

## 27. Generation Configuration

Baseline:

```text
TEMPERATURE = 0.0
REASONING_EFFORT = "low"
MAX_COMPLETION_TOKENS = 256
```

Reason:

The benchmark evaluates factual context retention, not creative generation.

Generation should therefore be:

- deterministic,
- short,
- repeatable,
- low variance.

---

## 28. Provider Rate Limits

Baseline guide configuration:

```text
TPM = 8,000
TPD = 200,000
RPM = 30
RPD = 1,000
```

These values must be configurable because provider policies can change.

Definitions:

```text
TPM = tokens per minute
TPD = tokens per day
RPM = requests per minute
RPD = requests per day
```

The system must respect both request-count and token-count constraints.

---

## 29. Daily Ledger

A local SQLite ledger shall track usage.

File:

```text
output/ledger.sqlite
```

Suggested records:

```text
timestamp
model
input tokens
cached tokens
output tokens
estimated cost
request status
```

Purpose:

- daily usage accounting,
- provider-limit protection,
- benchmark cost reporting.

---

## 30. Replay Cache

A local replay cache shall prevent unnecessary repeated inference calls.

File:

```text
output/cache.sqlite
```

Conceptually:

```text
request signature
      ↓
previous response exists?
      ├─ yes → replay
      └─ no  → call LLM and cache response
```

This allows developers to rerun:

- statistics,
- grading,
- leaderboard generation,
- plotting,

without repeatedly spending API credits.

---

## 31. Pricing Model

Baseline guide pricing configuration:

```text
openai/gpt-oss-120b
Input  = $0.15 / 1M
Output = $0.60 / 1M

openai/gpt-oss-20b
Input  = $0.075 / 1M
Output = $0.30 / 1M
```

Cached-input pricing shall be represented separately where applicable.

Pricing must remain configuration data, not embedded in core algorithms.

---

## 32. Measurement Harness

The second major component of the product is the evaluation system.

Its goal is not:

> “Did the code run?”

It is:

> “Did the context strategy preserve enough information for the agent to answer correctly?”

The harness must measure:

- prompt-fit success,
- factual preservation,
- answer correctness,
- cost,
- token usage,
- cache behavior,
- validity.

---

## 33. Benchmark Scenario

The primary benchmark shall contain:

```text
100 conversational turns
```

with:

```text
31 planted facts
```

distributed across different depths of the conversation.

Example:

```text
Turn 5  → merchant
Turn 17 → database
Turn 34 → region
Turn 61 → retry count
Turn 82 → shard
```

Later probe questions test whether those facts survive context engineering.

---

## 34. Ground Truth

Every planted fact must have:

```text
fact identifier
expected value
source turn
probe question
```

This allows deterministic grading without requiring an LLM judge.

---

## 35. Key Measurement — `fact_present`

The harness must separately record:

```text
fact_present
```

meaning:

> Was the expected fact actually present in the final assembled prompt?

This must be measured independently from:

```text
answer_correct
```

This creates four diagnostic states:

| Fact Present | Answer Correct | Interpretation |
|---|---|---|
| Yes | Yes | Context + model succeeded |
| Yes | No | Model failed to use available evidence |
| No | No | Context layer failed |
| No | Yes | Possible guess, leakage, or alternate evidence path |

This distinction is central to the benchmark.

---

## 36. Grading

The project should support **grading without an LLM judge** wherever ground-truth facts permit deterministic evaluation.

This avoids introducing another model's variability and cost into scoring.

Potential grading methods:

- normalized exact match,
- expected substring match,
- structured-value match,
- case-insensitive comparison,
- whitespace normalization.

---

## 37. Ablation Ladder

The harness shall run multiple context configurations—six in the planned benchmark—to determine which layers actually earn their place.

Examples conceptually include:

```text
Baseline / no layer
Recent-window strategies
Intermediate combinations
Full five-layer system
```

The exact six configurations must be declared centrally and remain fixed for comparable runs.

The benchmark should answer questions such as:

```text
What happens without RETRIEVE?
What happens without SUMMARY?
What does CAP contribute?
Does the full stack justify its complexity?
```

---

## 38. Pre-Registered Success Criterion

A success threshold must be declared **before** benchmark results are inspected.

Example:

```text
Required recall ≥ X%
```

The run passes or fails against that predefined threshold.

This prevents changing the definition of success after observing the results.

---

## 39. Validity Gates

The benchmark must contain five validity gates as planned in the guide.

A validity gate answers:

> Can the measurement itself be trusted?

not:

> Did the system score highly?

A run failing a validity gate should be marked:

```text
INVALID
```

rather than simply given a lower score.

Potential validity dimensions include:

- answer leakage,
- truncated generations,
- malformed benchmark data,
- invalid prompt sizing,
- inconsistent scenario/configuration.

---

## 40. Frozen Summary and Leakage Gate

The benchmark must use a controlled summary fixture:

```text
data/summary_fixture.json
```

Its purpose is to make summary behavior reproducible and prevent answer leakage.

A leakage gate must detect whether planted identifiers unintentionally appear in the frozen summary.

If they do:

```text
benchmark run = invalid
```

because the system could answer without RETRIEVE.

---

## 41. Probe Execution

The benchmark shall support running a single probe independently.

Purpose:

- debugging,
- inspecting assembled context,
- verifying retrieval,
- measuring token count,
- checking `fact_present`,
- inspecting model response.

A single-probe command should exist before the full benchmark is run.

---

## 42. Small-N Statistics

The project shall explicitly account for limited benchmark sample size.

Statistics must avoid overstating certainty when `n` is small.

The harness should report raw counts alongside percentages wherever possible.

Recommended reporting:

```text
Correct: 27 / 31
Recall: 87.1%
```

rather than reporting only:

```text
87.1%
```

---

## 43. Scorecard

A generated scorecard shall summarize:

```text
Configuration
Prompt fit rate
Fact-present rate
Answer accuracy / recall
Cost
Token usage
Validity state
```

Invalid runs must be clearly distinguished from merely low-performing runs.

---

## 44. Figures

Two reproducible plots shall be generated from committed result data without new LLM calls.

Planned outputs:

```text
output/context_cost.png
output/recall_by_zone.png
```

### Context Cost

Compare context/API cost across strategies.

### Recall by Zone

Show how well facts survive depending on their age/location in the long conversation.

---

## 45. Leaderboard

Generate:

```text
output/leaderboard.md
```

It should compare benchmark configurations and models in a GitHub-readable format.

The leaderboard should be generated from result files, not hand-edited.

---

## 46. Results

Model-specific results shall be stored independently:

```text
output/results-openai-gpt-oss-120b.json

output/results-openai-gpt-oss-20b.json
```

Result filenames shall sanitize model names:

```text
/
→
-
```

to avoid accidental directory creation.

---

## 47. Project File Structure

Recommended structure:

```text
context-engineering-layer/
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── context.py
│   ├── tokens.py
│   ├── pipeline.py
│   │
│   └── layers/
│       ├── __init__.py
│       ├── cap.py
│       ├── pin.py
│       ├── retrieve.py
│       ├── window.py
│       └── summarize.py
│
├── data/
│   ├── scenario.json
│   └── summary_fixture.json
│
└── output/
    ├── cache.sqlite
    ├── ledger.sqlite
    ├── run.log
    ├── results-*.json
    ├── leaderboard.md
    ├── context_cost.png
    └── recall_by_zone.png
```

---

## 48. Configuration Architecture

Central file:

```text
src/config.py
```

Every setting that can materially change a measured result should be auditable there or loaded through environment overrides.

Examples:

```text
models
budgets
CAP thresholds
retrieval limits
token calibration
rate limits
generation settings
pricing
benchmark thresholds
file paths
```

---

## 49. Configuration Dependency Rule

`config.py` must not import the reusable context layer.

Similarly, reusable context modules should avoid becoming tightly coupled to benchmark configuration.

Preferred architecture:

```text
Config
  ↓
Runner
  ↓
passes values
  ↓
Reusable Context Layer
```

rather than:

```text
Context Layer
  ↓
imports huge experiment config
```

This makes the layer portable into another agent.

---

## 50. Environment Variables

`.env` shall contain real local configuration/secrets.

Example:

```env
GROQ_API_KEY=gsk_xxx
TOKENIZER_FUDGE=1.07

CHAT_MODEL=openai/gpt-oss-120b
SWAP_MODEL=openai/gpt-oss-20b

CONTEXT_BUDGET_TOKENS=3000
MAX_COMPLETION_TOKENS=256
```

`.env.example` shall contain the same keys without secrets.

---

## 51. Security Requirements

The product must:

- never commit API keys,
- never print API keys,
- keep `.env` out of Git,
- avoid storing secrets in result JSON,
- avoid storing unnecessary sensitive content in logs.

`.gitignore` shall include:

```text
.env
.venv/
__pycache__/
*.pyc
output/cache.sqlite
output/ledger.sqlite
output/run.log
```

Benchmark result JSON, leaderboard, and plots should remain commit-safe.

---

## 52. Runtime Reliability

The project must handle Unicode model output safely.

The reference implementation reconfigures:

```text
stdout
stderr
```

to UTF-8 where supported.

This avoids Windows console failures caused by model output containing:

- curly quotes,
- em dashes,
- Unicode punctuation,
- non-breaking characters.

Encoding problems must not destroy long benchmark runs.

---

## 53. Cross-Platform Requirements

Target platforms:

```text
macOS
Linux
Windows
```

Paths should be generated using:

```python
pathlib.Path
```

rather than manual string concatenation.

Project paths should derive from `config.py`'s file location rather than current working directory.

---

## 54. Dependencies

Baseline dependencies:

```text
groq >= 1.7.0
tiktoken >= 0.14.0
rank-bm25 >= 0.2.2
numpy >= 2.5.2
python-dotenv >= 1.2.3
rich >= 15.0.0
matplotlib >= 3.11.1
```

Runtime:

```text
Python >= 3.12
```

Package/project management:

```text
uv
```

These are baseline project versions, not immutable product constraints.

---

## 55. Setup Validation

Before development/benchmarking, the project must verify the expected tokenizer exists.

Expected successful setup output:

```text
deps ok
```

Dependency failures should be detected before running expensive experiments.

---

## 56. API-Ready Output

The context pipeline ultimately returns a message structure suitable for chat inference.

Conceptually:

```python
[
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    ...
]
```

The LLM does not need to know that the context was constructed using CAP, PIN, BM25, WINDOW, or SUMMARY.

---

## 57. Primary Pipeline Interface

The context layer should be callable through **one primary function**.

Conceptually:

```python
assembled = assemble_context(
    history=history,
    question=question,
    pinned_facts=pinned_facts,
    budget=budget,
)
```

Output should include both:

```text
LLM-ready messages
+
diagnostic metadata
```

Recommended metadata:

```text
total tokens
tokens by block
kept turns
evicted turns
retrieved turn IDs
fact provenance
summary used
budget remaining
```

This makes debugging and evaluation substantially easier.

---

## 58. Context Carrier

The project should use an explicit internal context carrier rather than passing many unrelated variables between layers.

Conceptually:

```text
ContextCarrier
├── original turns
├── capped turns
├── pinned facts
├── current question
├── token budget
├── remaining budget
├── retrieved block
├── window block
├── summary
└── diagnostics
```

Suggested conceptual dataclass:

```python
@dataclass
class ContextCarrier:
    original_turns: list[Turn]
    capped_turns: list[Turn]
    pinned_facts: list[str]
    current_question: str
    total_budget: int
    remaining_budget: int
    summary: str | None
    retrieved_turn_ids: list[int]
    messages: list[dict]
    diagnostics: dict
```

---

## 59. Layer Contract

Every layer should obey a clear contract.

Each layer must:

```text
receive context state
perform one responsibility
respect budget
record what it changed
return updated context
```

A layer should not silently perform unrelated responsibilities.

Example:

```text
CAP
→ compress

RETRIEVE
→ rank and recover

WINDOW
→ select recent turns
```

Each layer should be independently unit-testable.

---

## 60. CLI Requirements

The project shall expose a command-line interface capable of:

```text
checking configuration
running a single probe
running the benchmark
running a model swap
generating leaderboard
generating figures
viewing final results
```

Suggested commands:

```bash
PYTHONPATH=. uv run python -m src.config
PYTHONPATH=. uv run python -m src.main probe ...
PYTHONPATH=. uv run python -m src.main benchmark
PYTHONPATH=. uv run python -m src.main leaderboard
PYTHONPATH=. uv run python -m src.main plots
```

The CLI should report errors clearly and avoid throwing raw provider exceptions whenever a controlled fallback/retry path exists.

---

## 61. Live Demo Requirement

The project shall include a live demonstration showing:

```text
Long conversation
        ↓
question about deep history
        ↓
context-engineered prompt
        ↓
retrieved evidence
        ↓
LLM answer
```

The demo should also show:

```text
No-layer baseline
→ oversized/failure

Full context layer
→ compact prompt + correct answer
```

---

## 62. Canonical End-to-End Benchmark Example

The flagship benchmark scenario is:

```text
Conversation ≈ 100 turns
≈ 17,700 raw tokens

Question:
"Which partition ended up carrying the blame?"

Correct fact:
shard-19

Source:
Turn 82
```

Stress-test budget:

```text
900 tokens
```

Flow:

```text
17,700 raw tokens
      ↓
CAP
      ↓
PIN consumes ~220
      ↓
680 remain
      ↓
RETRIEVE finds Turn 82
reserves ~280
      ↓
WINDOW gets ~400
keeps recent Turns 97–100
      ↓
SUMMARIZE dropped history
      ↓
FINAL ≈ 895 tokens
      ↓
LLM
      ↓
shard-19
```

Harness then records:

```text
fact_present = True
answer_correct = True
```

This should be maintained as the flagship demonstration.

---

## 63. Performance Requirements

The context engine should avoid unnecessary LLM calls.

CAP, PIN, WINDOW, token counting, and BM25 should execute locally.

The LLM should only receive the final engineered context.

Retrieval over stored history:

```text
does not consume LLM context tokens
```

although it still consumes normal CPU/RAM/storage resources.

Performance goals:

- no redundant retrieval over recent turns already in WINDOW,
- deterministic local transformations,
- pre-computed token counts where practical,
- replay-cache use for repeated identical inference calls,
- summary reuse/amortization where possible.

---

## 64. Cost Requirements

The system must measure:

```text
input tokens
cached input tokens
output tokens
estimated API cost
```

per call and per benchmark configuration.

Context strategies should be evaluated on both:

```text
quality
and
cost
```

A higher-recall strategy that is dramatically more expensive should be visible as such.

---

## 65. Observability

Every inference attempt should make it possible to inspect:

```text
configured budget
actual assembled tokens
per-block token counts
retrieved turns
window turns
summary
model
generation settings
fact_present
answer correctness
provider errors/retries
estimated cost
```

This is especially important when diagnosing:

```text
Context failure
vs
Model failure
```

Recommended structured diagnostic output:

```json
{
  "budget": 900,
  "final_tokens": 895,
  "blocks": {
    "system": 150,
    "pinned": 40,
    "summary": 80,
    "window": 280,
    "retrieved": 280,
    "question": 65
  },
  "retrieved_turn_ids": [82],
  "window_turn_ids": [97, 98, 99, 100],
  "fact_present": true,
  "answer_correct": true
}
```

---

## 66. Error Handling

The product must include controlled handling for:

- missing API key,
- missing tokenizer,
- prompt too large,
- provider rate limiting,
- network failure,
- Unicode output problems,
- truncated responses,
- invalid benchmark fixture,
- summary leakage,
- cache corruption,
- missing scenario data.

The provider wrapper should return structured results/errors rather than crashing benchmark runs unexpectedly.

Example result shape:

```python
@dataclass
class ModelResult:
    ok: bool
    content: str
    error_type: str | None
    error_message: str | None
    input_tokens: int
    output_tokens: int
```

---

## 67. Build Gates

Before a complete benchmark run, the project should require build gates such as:

```text
dependencies valid
scenario valid
summary fixture valid
token counting valid
configuration valid
output path writable
API configuration available when required
```

A failed build gate should stop the run before spending unnecessary API budget.

---

## 68. Reproducibility Requirements

A benchmark result must be traceable to:

```text
model
context budget
completion budget
tokenizer calibration
retrieval configuration
CAP configuration
generation settings
scenario version
summary fixture
code version
```

Result files should contain enough metadata to reproduce the run.

Suggested result metadata:

```json
{
  "model": "openai/gpt-oss-120b",
  "context_budget_tokens": 900,
  "max_completion_tokens": 256,
  "tokenizer_fudge": 1.07,
  "temperature": 0.0,
  "reasoning_effort": "low",
  "scenario": "scenario.json",
  "summary_fixture": "summary_fixture.json"
}
```

---

## 69. Acceptance Criteria

V1 should be considered complete when all of the following hold:

- [ ] Five layers implemented independently.
- [ ] One-call context assembly pipeline implemented.
- [ ] Final prompt always validated against token budget.
- [ ] Original uncapped history remains retrievable.
- [ ] BM25 retrieves from old history.
- [ ] Recent WINDOW operates within remaining budget.
- [ ] PIN protects predefined facts.
- [ ] SUMMARY covers deep history without benchmark leakage.
- [ ] Query-dependent retrieval appears near prompt suffix.
- [ ] Groq inference works through controlled wrapper.
- [ ] Replay cache works.
- [ ] Daily ledger works.
- [ ] Single probe works.
- [ ] 100-turn scenario runs.
- [ ] 31 planted facts are gradable.
- [ ] Six benchmark configurations run.
- [ ] `fact_present` and `answer_correct` are measured separately.
- [ ] Pre-registered success criterion exists.
- [ ] Five validity gates execute.
- [ ] Frozen-summary leakage gate works.
- [ ] Model swap works.
- [ ] Statistics are generated.
- [ ] Scorecard is generated.
- [ ] Leaderboard is generated.
- [ ] Two figures are generated without new API calls.
- [ ] CLI supports full run.
- [ ] Results are reproducible.

---

## 70. Future Enhancements

After V1, the strongest improvements would be:

- automatic fact extraction for PIN,
- dynamic pin eviction/update rules,
- structured JSON-aware CAP,
- chunk-level retrieval of huge tool outputs,
- hybrid BM25 + embeddings,
- semantic reranking,
- recency + relevance fusion,
- entity-aware memory,
- contradiction detection for pinned facts,
- dynamic budget allocation,
- LLM-bypass for deterministic retrieval answers,
- adaptive summary updates,
- persistent user memory,
- multi-agent context sharing,
- tool-result provenance,
- context quality scoring before inference.

A particularly valuable V2 architecture would be:

```text
New Turn
   ↓
Memory Classifier
   ├── durable fact → PIN store
   ├── searchable content → long-term index
   └── normal history → conversation store

Current request
   ↓
Context Planner
   ↓
CAP + PIN + hybrid retrieve + WINDOW + SUMMARY
   ↓
LLM
```

---

## 71. Product Differentiator

The strongest part of this project is **not merely that it compresses context**.

Many systems do that.

The differentiator is:

> It combines context management with an experimental framework capable of proving which parts actually improve long-conversation reliability.

That creates:

```text
THE FIX
+
THE RULER
```

The context layer is the fix.

The measurement harness is the ruler.

This makes the project stronger than a simple prompt-management demo because it provides:

- measurable factual retention,
- ablation testing,
- validity checks,
- cost accounting,
- reproducibility,
- model comparisons,
- cache-aware design.

---

## 72. Final Product Definition

The finished system should be describable in one sentence:

> **A reusable, cache-aware context-engineering middleware that dynamically compresses, protects, retrieves, windows, and summarizes long AI-agent histories into token-safe prompts, with a built-in benchmark harness that measures factual retention, model utilization, cost, and validity across multiple context strategies.**

Complete technical flow:

```text
                    NEW TURN
                       │
                       ▼
             Store full original
                       │
                       ▼
                      CAP
                       │
                       ▼
                      PIN
                       │
             reserve critical state
                       │
                       ▼
                   RETRIEVE
        search old uncapped information
                       │
                       ▼
                     WINDOW
              keep recent conversation
                       │
                       ▼
                   SUMMARIZE
             compress deep history
                       │
                       ▼
                    ASSEMBLE
                       │
        SYSTEM → PIN → SUMMARY → WINDOW
                 → RETRIEVED → QUESTION
                       │
                       ▼
                 COUNT TOKENS
                       │
                 within B?
                /        \
              no          yes
              │            │
           shrink          ▼
                         LLM
                          │
                          ▼
                       ANSWER
                          │
                          ▼
                MEASUREMENT HARNESS
                 │        │        │
                 ▼        ▼        ▼
           fact_present  correct   cost
                 │
                 ▼
          VALIDITY + STATISTICS
                 │
                 ▼
       RESULTS / LEADERBOARD / PLOTS
```

---

## 73. Glossary

| Term | Meaning |
|---|---|
| **Context Engineering** | Deciding what information should be shown to the model on each call. |
| **Prompt Engineering** | Designing instructions or wording used to guide the model. |
| **Turn** | A conversational exchange that may contain user, assistant, and tool messages. |
| **CAP** | Compress oversized messages while preserving head and tail. |
| **PIN** | Protect predefined critical facts and system instructions from eviction. |
| **RETRIEVE** | Search old history for information relevant to the current question. |
| **WINDOW** | Keep the most recent turns that fit the remaining budget. |
| **SUMMARIZE** | Compress dropped historical context into broad background. |
| **Block** | A labeled logical section of the final prompt. |
| **Token Budget** | Maximum tokens the context engine may allocate to the final LLM input. |
| **Context Window** | Maximum context capacity supported by the model. |
| **TPM** | Tokens Per Minute. |
| **TPD** | Tokens Per Day. |
| **RPM** | Requests Per Minute. |
| **RPD** | Requests Per Day. |
| **Prefix Cache** | Reuse of computation for an identical beginning of a prompt. |
| **Prefix-Stable** | A component whose output stays identical when its inputs do not change. |
| **Suffix** | Content deliberately placed near the end of the prompt. |
| **Context Rot** | Degradation in the model's ability to use a fact as the prompt becomes large/noisy. |
| **BM25** | Classical lexical relevance-ranking algorithm used for retrieval. |
| **Pinned Fact** | A critical durable fact guaranteed to remain in the prompt. |
| **Elision** | Intentional omission of part of a long message. |
| **Replay Cache** | Local cache that reuses previous model responses for identical requests. |
| **Daily Ledger** | Local accounting database for token usage and cost. |
| **Planted Fact** | Known benchmark fact intentionally inserted into a scenario. |
| **Ground Truth** | Known correct answer used for deterministic evaluation. |
| **`fact_present`** | Whether the expected fact exists in the final assembled prompt. |
| **Ablation** | Removing or adding components to measure their individual contribution. |
| **Validity Gate** | Test that determines whether benchmark results can be trusted. |
| **Frozen Summary** | Fixed benchmark summary used for reproducible evaluation. |
| **Leakage** | When a benchmark answer appears where it should not, invalidating evaluation. |
| **Truncation** | Model output being cut off by the completion-token limit. |
| **Context Carrier** | Internal state object passed through context-processing layers. |
| **Layer Contract** | Rules defining what each context stage may receive, change, and return. |

---

## Repository Summary

This repository should ultimately demonstrate three things clearly:

### 1. It can build a compact prompt

```text
Long history
→ token-safe context
```

### 2. It can recover old information

```text
Fact from deep history
→ BM25 retrieval
→ evidence appears in final prompt
```

### 3. It can prove its own effectiveness

```text
Context strategy
→ benchmark
→ fact_present
→ answer_correct
→ cost
→ validity
→ leaderboard
```

That combination is the defining value of the project.
