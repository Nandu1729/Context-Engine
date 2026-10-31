# Benchmark report

Updated 2026-10-31. Every number here is labeled with how it was produced.
"Retention" means the planted fact's evidence reached the assembled context at its
declared source. It is **not** answer accuracy.

## Reproduce

```sh
uv run --locked --offline context-engine strategy-eval            # 900 and 3000 tokens
uv run --locked --offline context-engine strategy-eval --budget 900 --probes
uv run --locked --offline context-engine benchmark-check          # frozen integrity gates
```

No API key, no network, no model calls. Runtime ~45 s per budget on Apple-silicon.
Corpus: frozen synthetic `incident-100-v1`, 100 turns, 31 planted facts
(10 early / 11 middle / 10 late), frozen protocol hashes in `freeze.json`.

## Offline strategy comparison (0.11.0, measured 2026-10-31)

Token reduction is against the raw 16,608-token estimated request. Latency is
local wall time per probe (includes summary generation where used).

| Budget | Strategy | Fit | Evidence retained | Median input tokens | Median reduction | Chunk precision | Turn recall | Median latency |
|---|---|---|---|---|---|---|---|---|
| 900 | full_history | 0/31 | 0/31 (non-fit) | — | — | — | — | — |
| 900 | recent_window | 31 | 1/31 | 797 | 95.2% | — | — | ~11 ms |
| 900 | summary_window | 31 | 1/31 | 767 | 95.4% | — | — | ~22 ms |
| 900 | retrieval_window | 31 | **31/31** | 774 | 95.3% | 0.34 | 0.97 | ~16 ms |
| 900 | combined (0.11.0 defaults) | 31 | **31/31** | 839 | 95.0% | 0.42 | 1.00 | ~245 ms |
| 900 | combined_no_recover (0.10.0 defaults) | 31 | 29/31 | 838 | 95.0% | 0.40 | 0.94 | ~235 ms |
| 3000 | full_history | 0/31 | 0/31 (non-fit) | — | — | — | — | — |
| 3000 | recent_window | 31 | 4/31 | 2975 | 82.1% | — | — | ~32 ms |
| 3000 | summary_window | 31 | 3/31 | 2943 | 82.3% | — | — | ~59 ms |
| 3000 | retrieval_window | 31 | **31/31** | 2950 | 82.2% | 0.32 | 0.90 | ~36 ms |
| 3000 | combined (0.11.0 defaults) | 31 | **31/31** | 2949 | 82.2% | 0.42 | 1.00 | ~340 ms |
| 3000 | combined_no_recover (0.10.0 defaults) | 31 | **19/31** (late 0/10) | 2952 | 82.2% | 0.28 | 0.61 | ~300 ms |

Retention counts are deterministic and pinned in `tests/test_strategies.py`.
Saved evidence with per-fact results: `output/strategy-eval-0110.json` (0.11.0) and
`output/strategy-eval-0100.json` (0.10.0, where `combined` meant recovery off).
Latencies are from one unloaded run and vary by machine.

### What this shows

1. **The historical results reproduce offline.** `combined_no_recover` (the
   pre-0.11.0 defaults and the frozen-protocol setting) at 900 = 29/31 matches the
   C06 A5 retention (live: 29/31 correct); at 3000 = 19/31 matches the recorded S11
   regression.
2. **Root cause of S11:** CAP trims long WINDOW turns, removing mid-message facts;
   RETRIEVE excluded WINDOW turns, so nothing restored them. Since 0.11.0 (D109)
   `recover_capped_window=True` is the default and combined retains 31/31 at both
   budgets, for ~5–15% more latency.
3. **Retrieval does the work on this corpus.** WINDOW-only keeps almost nothing
   (all facts sit in long messages early in history).
4. **Extractive summaries add no retention here** because facts are mid-message
   and the summarizer keeps first sentences. Model-written summaries were not
   evaluated (needs inference).
5. Token reduction is a function of the budget you choose, not of strategy: every
   assembled strategy fills its allowance. Savings claims must be paired with
   retention/accuracy at that budget.

## Assembly latency (0.12.1, measured 2026-10-31)

All layers (`combined`, including the extractive-summary second pass) on the
100-turn benchmark, macOS arm64, local wall time, tokenizer already loaded:

| Budget | 0.11.0 median | 0.12.0 median | **0.12.1 median** (same history, new question) | 0.12.1 first call |
|---|---|---|---|---|
| 900 | 247 ms | 95 ms | **67 ms** | ~53 ms |
| 3000 | 481 ms | 208 ms | **80 ms** | ~66 ms |

0.12.0 added a bounded token-count cache. 0.12.1 removed repeated work in fit checks
(only the estimated total is computed), reuses per-turn JSON and memoizes the
WINDOW plan and history digests. Outputs are unchanged: all 310 strategy-benchmark
assemblies match 0.12.0 byte-for-byte, and V1–V5 gates are unchanged.

## Live answer accuracy, 900 tokens (D109/D110, 2026-10-31): COMPLETE

One approved free-tier Groq run (`scripts/strategy_accuracy_live.py`, run
`strategy-accuracy-900-001`): gpt-oss-20b, temperature 0, 256 completion tokens,
no retries, frozen system prompt and strict exact-value grading as in C06. 155
planned slots: 153 answered, 2 zero-token `provider_rejected` HTTP 4xx (both
`summary_window`; cause unknown, same pattern as C06 D067–D069). After the first
rejection the owner approved continuing (D110, `amendment-001`); rejected slots
were never retried. Public report without answer content:
`output/strategy-accuracy-900-001/report.json`.

| Strategy | Correct / answered | Wilson 95% | Correct / planned | Offline retention |
|---|---|---|---|---|
| combined (0.11.0 defaults) | **31/31** | 0.89–1.00 | 31/31 | 31/31 |
| retrieval_window | **31/31** | 0.89–1.00 | 31/31 | 31/31 |
| combined_no_recover (0.10.0 defaults) | 29/31 | 0.79–0.98 | 29/31 | 29/31 |
| summary_window | 1/29 | 0.01–0.17 | 1/31 (2 rejected) | 1/31 |
| recent_window | 1/31 | 0.01–0.16 | 1/31 | 1/31 |

Tokens: 114,569 provider input (local estimate 120,581), 6,053 output (4,245
reasoning); cost $0. On this corpus, accuracy equals retention for every strategy:
when the evidence reached the context, the model answered correctly. The
`combined_no_recover` 29/31 matches the historical C06 A5 29/31 correct.

Limits: one synthetic scenario written alongside the engine, one model, one run;
not real-world accuracy. 3000 tokens and paid models were not run (not approved).

## Historical live results (preserved, not re-run)

From [C06_REPORT](C06_REPORT.md), archived 0.7.2 runtime, Groq gpt-oss models:
744 slots, 613 live responses; A5 at 900 tokens: 31 fit / 29 retained / **29
correct** / 95.18% median estimated reduction / 0 truncation. These are model
answers graded against ground truth on one synthetic scenario authored with the
engine. C09 qualification on fresh cases **failed** its strict target (PRIMARY
14/16). See [C09_QUALIFICATION_LIVE_REPORT](C09_QUALIFICATION_LIVE_REPORT.md).

## Not measured (and why)

| Metric | Status |
|---|---|
| Answer correctness per strategy | 900 tokens: measured (above). 3000 tokens and faithfulness: not measured; not approved. |
| Real-world retention | No real conversation dataset; single synthetic scenario. |
| Provider-billed tokens / cost | Local estimates only; historical overruns up to 1.78× on small requests. |
| Model summarization quality/cost | `PromptSummarizer` exists; not run against a model. |
