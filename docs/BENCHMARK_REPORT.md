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

## Live accuracy with thinking and a model judge (D119 stage B, mercury-3, 2026-11-01)

`scripts/longmemeval_accuracy_live_b.py`; public counts in
`output/longmemeval-accuracy-b-001/report.json`, answers and judge replies private.
Same 95 questions and seed as D118. Changes for cause (d): reasoning "low", 1024
output tokens, a system prompt that says the answer is usually in the memory, to
search it carefully, compute dates from the question date and answer "unknown" only
if it is truly missing. Judge: mercury-3, reasoning "instant", 64 tokens, the
published LongMemEval judge prompts verbatim
([evaluate_qa.py @ 9e0b455](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/evaluation/evaluate_qa.py),
MIT; correct when the judge reply contains "yes").

| Arm (n = 95, Wilson 95%) | strict-v1 | lenient-v2 | lenient-v3 | judge |
|---|---|---|---|---|
| `assemble_context` defaults, 3000 | 22 (16–33%) | 23 (17–34%) | 26 (19–37%) | 37 (30–49%) |
| ChatMemory defaults, 3000 | 26 (19–37%) | 27 (20–38%) | 38 (31–50%) | **56** (49–68%) |
| ChatMemory defaults, 8000 | 30 (23–42%) | 30 (23–42%) | **40** (33–52%) | 54 (47–66%) |

Same question, both arms: ChatMemory vs core at 3000 tokens, judge 23 vs 4 (sign
test p < 0.001), lenient-v3 17 vs 5 (p ≈ 0.02). ChatMemory 8000 vs 3000: judge 6 vs 8,
lenient-v3 10 vs 8 (no difference shown).

Paired against D118 (same questions; three things changed at once):

| Arm vs D118 | lenient-v3 improved / regressed | lenient-v2 | strict-v1 |
|---|---|---|---|
| core 3000 | 8 / 3 (p ≈ 0.23) | 7 / 2 | 8 / 3 |
| ChatMemory 3000 | 14 / 7 (p ≈ 0.19) | 9 / 8 | 10 / 5 |
| ChatMemory 8000 (vs D118 ChatMemory 3000) | 18 / 9 (p ≈ 0.12) | 12 / 8 | 16 / 7 |

By type, judge (core / ChatMemory 3000 / ChatMemory 8000): multi-session 6 / 17 / 19
of 24, knowledge-update 10 / 13 / 10 of 15, single-session-user 11 / 12 / 11 of 13,
single-session-assistant 5 / 5 / 5 of 11, temporal 4 / 6 / 7 of 26, preference
1 / 3 / 2 of 6.

**Error breakdown again** (lenient-v2 misses, stage A rules plus two new groups):

| Group | core D118 → B | ChatMemory 3000 D118 → B | ChatMemory 8000 |
|---|---|---|---|
| (a) format only | 8 → 9 | 11 → 21 | 18 |
| (b) rubric gold | 15 → 13 | 15 → 9 | 8 |
| (c) evidence missing | 37 → 31 | 10 → 11 | 4 |
| (d) model error, evidence present | 17 → **5** | 33 → **10** | 13 |
| out of tokens (thinking used all 1024, empty answer) | – → 11 | – → 16 | 16 |
| invalid response (no answer text) | – → 3 | – → 1 | 6 |

Group (d) shrank (ChatMemory 33 → 10; "unknown" replies 34 → 11), but 43 of 285
answers (33 of them temporal questions) ran out of tokens and 10 came back with no
text, so the net gain under exact-match grading is modest. More of the remaining
misses are format-only (11 → 21), which the judge accepts.

**Judge vs lenient-v3** on the 232 judged answers: agree on 187; the judge accepts 44
that v3 rejects and rejects 1 that v3 accepts. Ten private disagreement samples: all
judge-yes, v3-no — "UCLA" for "University of California, Los Angeles (UCLA)", "1 hour
30 minutes" for "an hour and a half", "12" for a sentence gold, "Trader Joe's lavender
scented shampoo" for "Trader Joe's", two preference answers that use the user's
details. They read as correct; none looked like a judge error.

**Provider behavior** (raw bodies saved privately for each new case): Inception
sometimes returns `content: null` with finish "stop" after thinking (10 answers, 1
judge reply). The client rejects that as `invalid_response`. By owner amendments these
were counted wrong (answers) or "no" (judge), never resent, each capped at 10.

Calls 517 of 600 (285 answers, 232 judge; no judge for the 53 answers without text),
0 retries, 0 rate limits. Tokens: answers 901,674 in / 67,482 out (65,712 thinking);
judge 31,658 in / 907 out. List-price estimate 157,133 micro-USD (cap 300,000); the API
reports no billing.

Limitations: one model and one run; partly simulated chats; the judge is the same
model family as the answerer, with prompts written for GPT-4o, at temperature 0.5
(paper: 0); answers at temperature 0.5 (API minimum); the D118 comparison changes
reasoning, output limit and prompt together; D118 answers were not judged (call
limit); 1024 tokens was too few for "low" thinking on date questions.

## Why D118 answers were wrong (D119 stage A, offline, 2026-10-31)

No model calls. `scripts/longmemeval_error_breakdown.py` rebuilds all 190 D118
contexts (every request hash matches the live manifest) and reads the private
receipts. Public counts: `output/longmemeval-error-breakdown-001/report.json`;
replies, contexts and examples stay in `output/private/`.

**Lenient-v3 grader** (new in 0.17.0, owner-approved; beside v1/v2, not replacing
them): drops one leading "the/a/an", removes punctuation from both reply and gold,
reads number words 0–99 as digits, and accepts a bare number for a
"&lt;number&gt; &lt;unit&gt;" gold ("3" for "3 days"). It still fails a different unit, a
partial answer, prose around the answer, and "3" for "three times a week".

| Setting (n = 95) | strict-v1 | lenient-v2 | lenient-v3 |
|---|---|---|---|
| `assemble_context` defaults | 17 (11–27%) | 18 (12–28%) | 21 (15–31%) |
| ChatMemory defaults | 21 (15–31%) | 26 (19–37%) | **31** (24–43%) |

Paired on the same question (lenient-v3): only ChatMemory right 12, only core 2.
By type (v3, core → ChatMemory): multi-session 2 → 8, temporal 4 → 5,
knowledge-update 6 → 7, single-session-user 5 → 6, single-session-assistant 4 → 5,
preference 0 → 0.

**Wrong answers** (lenient-v2 false), first matching rule wins:

| Group | Rule | Core (77) | ChatMemory (69) |
|---|---|---|---|
| (a) format only | lenient-v3 accepts (a1), or the reply is the gold plus words (a2) | 8 | 11 |
| (b) rubric gold | gold lists an alternative ("acceptable", "(or "), is a preference description, or has 8+ words | 15 | 15 |
| (c) evidence missing | c1: a needed evidence turn is not in context (knowledge-update: the newest; others: all); c2: the turn is there but the gold words are not (cut off) | **37** (33 + 4) | 10 (7 + 3) |
| (d) model error | evidence present; "unknown" (d1) or wrong (d2) | 17 | **33** |

Model errors split into gold-words-in-context ("extractive") and computed answers:
ChatMemory d1 11 + 4, d2 7 + 11; core d1 7 + 2, d2 3 + 5. So ChatMemory's main
remaining problem is the model (it answers "unknown" or miscounts with the evidence
in front of it); core's is missing evidence. Examples (3 per rule) were reviewed
privately: a1 "3 times a week" vs "Three times a week."; c2 "$2,000" absent from the
retrieved chunk; d2 37 vs 38 coins.

Caveats: a2 can accept a hedged reply; (b) is counted whatever the reply says;
short numeric golds ("4") can match a number elsewhere in the context, so
"extractive" is an upper bound.

### Retrieval check for cause (c) (offline)

`scripts/retrieval_chunking_check.py`, all 470 eligible questions at 3000 tokens;
"answer text" = the gold's words appear in the context, for the 142 extractive
questions; "cut" = the gold-bearing turn is in context but the words are not.

| Variant | Setting | any / all / latest (of 470) | answer text (of 142) | cut |
|---|---|---|---|---|
| **360/80, all words (current)** | core | 371 / 217 / 312 | 108 | 7 |
| | ChatMemory | **442 / 371 / 411** | **125** | 9 |
| 360/80, NLTK stop words removed | core | 353 / 202 / 289 | 103 | 8 |
| | ChatMemory | 435 / 353 / 403 | 121 | 9 |
| 600/150 chunks | core | 365 / 215 / 302 | 111 | 3 |
| | ChatMemory | 430 / 356 / 401 | 125 | 3 |
| 600/150 + stop words | core | 348 / 208 / 291 | 111 | 3 |
| | ChatMemory | 427 / 346 / 397 | 123 | 4 |

Synthetic benchmark (evidence sentence in context, 31 facts): original questions
31/31 for every variant. Reworded questions at 3000 tokens, hybrid all-layers
(`combined_semantic`): 21 current, 20 stop words, 17 600-char chunks, 16 both;
keyword all-layers 3 → 0 with stop words.

Result: chunking cuts the answer off in only 9 of 142 extractive questions
(ChatMemory). Bigger chunks reduce cuts (9 → 3) but fit fewer chunks, so evidence
recall falls (442 → 430) and reworded synthetic retention falls (21 → 17). Removing
stop words is worse on every measure (BM25's IDF already discounts common words, and
removing them likely also drops words like "my" that anchor personal questions; not verified). **No default
changed.**

## Live answer accuracy on LongMemEval-S (D118, Inception mercury-3, 2026-10-31)

One bounded live run (`scripts/longmemeval_accuracy_live.py`, run
`longmemeval-accuracy-3000-002`; public rows in `output/longmemeval-accuracy-3000-002/`,
prompts and answers private). 95 LongMemEval-S questions (seed 118, stratified by type,
abstention skipped) x 2 settings at 3000 input tokens: **core** = `assemble_context`
defaults with hybrid retrieval (280-token reserve, top 4); **ChatMemory** = its
defaults (40% reserve = 1200 tokens, top 13, one chunk per turn). Model mercury-3,
temperature 0.5 (the API minimum), reasoning off (`instant`), 256 output tokens, no
retries. 190/190 answered, 0 rejections; 475,576 input / 992 output tokens; list-price
estimate 46,181 micro-USD ($0.046) on the owner's free tier. After the first 11 calls
the owner's usage dashboard matched the local ledger exactly (requests and tokens);
the API reports no billed cost, so charges can only be confirmed on the dashboard.

| Setting (n = 95) | Strict v1 | Lenient v2 | Reply contains gold* | Evidence in context | "unknown" replies |
|---|---|---|---|---|---|
| Core defaults | 17 (17.9%; 95% CI 11.5–26.8) | 18 (18.9%; 12.3–28.0) | 22 | 72 | 49 |
| **ChatMemory defaults** | **21 (22.1%; 14.9–31.4)** | **26 (27.4%; 19.4–37.1)** | **32** | **94** | **34** |

\*Diagnostic, not a grader: the gold text appears inside the reply.

Same questions, both settings (paired): lenient v2, ChatMemory-only correct 9 vs
core-only 1 (sign test p ≈ 0.02); reply-contains-gold 12 vs 2 (p ≈ 0.01); strict v1
8 vs 4 (not significant). Evidence in context but still wrong (lenient): core 56/72,
ChatMemory 68/94. Right without evidence in context: core 2, ChatMemory 0.

| Type (n) | Core strict / lenient | ChatMemory strict / lenient |
|---|---|---|
| single-session-user (13) | 5 / 5 | 6 / 6 |
| single-session-assistant (11) | 3 / 3 | 4 / 4 |
| single-session-preference (6) | 0 / 0 | 0 / 0 |
| multi-session (24) | 2 / 2 | 7 / 7 |
| knowledge-update (15) | 5 / 5 | 4 / 6 |
| temporal-reasoning (26) | 2 / 3 | 0 / 3 |

**What this shows.** With the same model and questions, ChatMemory's settings get
more answers right (lenient 18 → 26) and fewer "unknown" replies (49 → 34), consistent
with the evidence-recall gain. **Absolute accuracy is low and should not be compared
with published LongMemEval scores**, which use a model judge, stronger models and
reasoning. Reasons seen in the mismatch sample: (1) exact-value grading rejects
correct paraphrases ("The bike." vs "bike", "3 times a week" vs "Three times a
week.", "3" vs "3 days."; lenient v2 strips a trailing period from the reply but not
from the gold answer); (2) temporal golds are rubrics ("4 days. 5 days (including
the last day) is also acceptable.") and preference golds are descriptions, so exact
grading cannot pass them; (3) real model errors: "unknown" despite evidence, wrong
counts and date arithmetic, with reasoning off; (4) "evidence in context" is
turn-level, and a retrieved chunk of the right turn may miss the answer sentence.

**Run history.** Run -001 (reasoning "low") was paused by design after 10 staged
calls: 5 answers were empty because thinking used the whole 256-token output. The
owner chose reasoning off for run -002; the 200-call limit covered both runs (10 +
190). A post-run bug in the runner's `report` command (the pre-run cap check also ran
at report time) was fixed; the regenerated report is byte-identical.

**Limitations.** 95 questions; histories partly simulated by the dataset authors; one
model, one run, temperature 0.5; exact-match grading without a model judge; a
different model from the earlier Groq runs, so compare the two settings with each
other, not with past numbers.

## Real data: LongMemEval-S evidence recall (0.16.0, offline, 2026-10-31)

[LongMemEval](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
(MIT; `longmemeval_s_cleaned.json` at revision `98d7416c`, SHA256 `d6f21ea9…`) is a
public benchmark of long user-assistant chat histories: 500 questions, each with
its own ~50-session haystack (median 491 turns, ~490k characters, roughly 115k
tokens), and labels on the turns that contain the answer. 479 questions have such
labels (the 21 others are skipped). **This measures whether the evidence reaches
the assembled context, not whether a model answers correctly**, and no model is
called. The histories are not real users' chats: they mix public chat logs
(ShareGPT, UltraChat) with simulated sessions generated by the dataset authors.

- **any**: at least one evidence turn is in the context (kept in the recent window
  or retrieved). **all**: every evidence turn is. **newest**: the latest evidence
  turn is (for updated facts, the current value).
- Budget 3000 tokens. "Core default" is `assemble_context` defaults (280-token
  retrieval reserve, top 4 chunks). "ChatMemory" gives retrieval 40% of the budget
  (1200 tokens, top 13 chunks).

| Configuration | any | all | newest | recent turns kept (mean) |
|---|---|---|---|---|
| Recent window only (core default) | 16.5% | — | — | 42.3 |
| Core default, keyword-only | 74.3% | 43.2% | 61.6% | 42.3 |
| Core default, hybrid | 78.5% | 45.9% | 66.0% | 42.3 |
| ChatMemory, keyword-only | 88.5% | 70.6% | 80.4% | 27.0 |
| ChatMemory, hybrid, `diverse_turns=False` | 93.5% | 77.7% | 86.2% | 27.0 |
| **ChatMemory default (hybrid, `diverse_turns=True`)** | **94.2%** | **79.3%** | **87.7%** | 27.0 |

By question type (any / all), core hybrid → ChatMemory hybrid → + diverse turns:

| Type (n) | Core hybrid | ChatMemory | + diverse |
|---|---|---|---|
| single-session-user (64) | 89.1 / 89.1 | 96.9 / 96.9 | 98.4 / 98.4 |
| single-session-assistant (56) | 80.4 / 80.4 | 92.9 / 92.9 | 92.9 / 92.9 |
| single-session-preference (30) | 43.3 / 30.0 | 66.7 / 53.3 | 66.7 / 50.0 |
| multi-session (125) | 76.8 / 19.2 | 96.8 / 58.4 | 96.8 / 61.6 |
| knowledge-update (72) | 90.3 / 45.8 | 100 / 91.7 | 100 / 94.4 |
| temporal-reasoning (132) | 75.8 / 39.4 | 91.7 / 78.0 | 93.2 / 79.5 |

**Trade-off: recent window vs retrieval.** Retrieval share sweep (hybrid, 3000
tokens): 9% (280) any 78.5 / all 45.9, 42 recent turns; 25% (750) 91.0 / 70.6, 34
turns; **40% (1200) 93.5 / 77.7, 27 turns**; 50% (1500) 94.2 / 79.1. Past 40%
the gain is small while recent turns keep shrinking; LongMemEval's evidence is
rarely recent (the window alone finds 16.5%), so it favors retrieval more than
chats with many follow-ups would. At 8000 tokens with 40%: 97.1 / 88.9, 77 recent
turns (core default at 8000: 88.1 / 54.5). Core `assemble_context` defaults are
unchanged; ChatMemory's `retrieval_share` is configurable.

**Measured and not adopted** (ChatMemory settings, then the synthetic benchmark's
reworded questions at 900 tokens, hybrid 21/31 baseline): per-sentence meaning
scores (real +0.8 pt any; synthetic 21 → 19), recency bonus 0.1 (newest +1.5 pt,
multi-session any −0.8 pt; synthetic 21 → 18), recency bonus only for
"now/current/latest" questions (slightly worse), a date-window boost for "N days
ago"/"last week" questions (matched 28 questions; +1 question), and rule-based
auto-pinning of "my name is / I prefer / I'm allergic to ..." (139 suggestions over
479 haystacks, none from an evidence turn; recall unchanged). `diverse_turns`
left the synthetic results unchanged (31/31 original, 21/31 reworded); it is the
ChatMemory default and opt-in for `assemble_context` (D117).

Speed: one assembly over a 491-turn haystack takes about 0.5–0.6 s (hybrid,
single process, first call per history; includes embedding every chunk).

Reproduce (download the file into `output/private/datasets/longmemeval-98d7416c/`):

```sh
uv run python scripts/longmemeval_retrieval.py --mode hybrid --reserve 1200 --top-k 13 --diverse --out report.json
```

## Default hybrid retrieval and fusion weight (0.15.0, offline, 2026-10-31)

0.15.0 bundles potion-base-8M as 8-bit vectors (cosine >= 0.9999 to the float32
model; identical recall) with a pure-Python tokenizer, and makes hybrid retrieval
the default. Adding a "needle in filler" check (each fact sentence buried in 120
"routine telemetry" sentences; the memory demo's shape) showed that the 0.7 meaning
weight lost exact keyword matches. Recall@4 of the fact's turn (raw output:
`output/embedding-bakeoff-001/weights.txt`):

| Meaning weight | Original | Reworded | Needle | Needle, reworded |
|---|---|---|---|---|
| 0.7 (0.14.0) | 31 | 23 | **22** | 9 |
| **0.5 (0.15.0 default)** | 31 | 23 | **31** | **12** |
| 0.3 | 31 | 21 | 31 | 10 |
| keyword only | 31 | 5 | 31 | 4 |

A "keep the best keyword match" guard changed nothing at 0.5 and was not added.
Full-engine retention with 0.5 is unchanged from 0.14.0 (original 31/31; reworded
21/31 combined, 24/25 retrieval-only). Averaged embeddings dilute a fact in long
filler, so reworded questions about such facts stay hard (12/31). Hybrid has no
word-overlap gate, so it fills retrieval space up to `top_k` within the budget.

## Live check: reworded questions, keyword vs hybrid (D114, 2026-10-31)

One approved free-tier Groq run (`scripts/semantic_accuracy_live.py`, run
`semantic-accuracy-900-001`) on the published 0.14.0 wheel: gpt-oss-20b, 900 tokens,
256 completion tokens, no retries, 31 reworded questions per strategy. 62/62 calls
answered, 0 rejections, 46,454 input / 2,815 output tokens, $0. Public report
without answer content: `output/semantic-accuracy-900-001/report.json`.

| Strategy | Strict grading (C06 protocol) | Lenient grading | Offline retention |
|---|---|---|---|
| combined, keyword (default) | 3/31 (Wilson 3–25%) | 3/31 | 3/31 |
| **combined_semantic (hybrid, weight 0.7)** | **18/31** (41–74%) | **21/31** | 21/31 |

Hybrid answered 16 facts that keyword missed; keyword answered 1 that hybrid
missed. Every answer without the evidence in context was wrong (no lucky guesses).
The 3 strict-grading misses with evidence present were correct values with
formatting differences: a trailing period (`PostgreSQL.`) and a Unicode
non-breaking hyphen (U+2011) instead of `-` (`cert‑marigold`, `batch‑6721`).
"Lenient" only strips trailing `.!?` and maps Unicode dashes to `-`; the frozen
strict grader is unchanged. Re-grading the earlier original-question run leniently
changes nothing (`output/*/grading.json`, `scripts/regrade_live.py`). This run used the
0.14.0 weight 0.7; 0.15.0 uses 0.5 (same offline retention). Limits: one synthetic
scenario, author-written rewordings, one model.

## Semantic retrieval: model bake-off and engine results (0.14.0, offline, 2026-10-31)

**Bake-off** (retrieval only, the engine's 360-character chunks, 400 chunks; fact's
source turn in the top 4; reworded questions; raw output and scripts in
`output/embedding-bakeoff-001/`):

| Model (license) | Found / 31 | MRR | Index per chunk | Query | Model download |
|---|---|---|---|---|---|
| BM25 keyword (current default) | 5 | 0.14 | — | — | — |
| BAAI/bge-small-en-v1.5 (MIT, ONNX) | **27** | 0.69 | 8.4 ms | 1.4 ms | ~67 MB |
| **minishlab/potion-base-8M (MIT, static)** | 24 | 0.55 | **0.09 ms** | **0.03 ms** | **~30 MB** |
| nomic-embed-text-v1.5-Q (Apache-2.0) | 24 | 0.62 | 15 ms | 2.3 ms | ~130 MB |
| granite-embedding-small-english-r2 (Apache-2.0) | 23 | 0.68 | 5.2 ms | 0.8 ms | ~180 MB |
| potion-retrieval-32M (MIT, static) | 21 | 0.55 | 0.12 ms | 0.02 ms | ~130 MB |
| snowflake-arctic-embed-xs (Apache-2.0) | 16 | 0.48 | 2.4 ms | 0.4 ms | ~90 MB |

All keep 31/31 on the original questions. Not tested as defaults: EmbeddingGemma
(1.24 GB in fastembed, Gemma license) and Qwen3-Embedding-0.6B (~1.1 GB).

**Fusion** (reworded, found/31): reciprocal-rank fusion hurt (potion 14, bge 16,
because keyword ranks are noise without shared words); per-query min-max score
fusion 0.7 x meaning + 0.3 x keyword kept quality (potion 23 with better MRR 0.59,
bge 27) and 31/31 on originals. **Chosen default:** potion-base-8M + score fusion.
bge-small is 3 facts more accurate here but ~90x slower to index (a 100-turn
history from scratch: ~3.4 s vs ~40 ms), which breaks the < 100 ms target; it is
offered as `FastEmbedEmbedder`.

**Full engine** (`strategy-eval --semantic`, Model2VecEmbedder, found/31):

| Strategy | Original 900 / 3000 | Reworded 900 / 3000 | Median latency 900 / 3000 |
|---|---|---|---|
| retrieval_window (keyword) | 31 / 31 | 6 / 7 | 8 / 11 ms |
| **retrieval_semantic** | 31 / 31 | **24 / 25** | 8 / 11 ms |
| combined (keyword, defaults) | 31 / 31 | 3 / 3 | 66 / 81 ms |
| **combined_semantic** | 31 / 31 | **21 / 21** | 68 / 75 ms |

`combined_semantic` trails `retrieval_semantic` because the summary reserve leaves
retrieval less room. Limits: one synthetic scenario; reworded questions written by
the engine author; no live answer-accuracy run with semantic retrieval yet.

## Reworded-question stress test (0.13.0, offline, 2026-10-31)

The frozen questions reuse their evidence sentence's words ("Which merchant was
involved?" vs "The merchant involved was merchant-aurora."), which favors BM25.
`strategy-eval --questions paraphrased` asks 31 reworded questions that share no
content word, and no 4-letter start of a 5+ letter word, with the evidence sentence
or answer (rule enforced in code; questions written by the engine author, not
independently reviewed). Scoring is unchanged. Saved evidence:
`output/strategy-eval-0130-paraphrased.json`.

| Strategy | 900 original | 900 reworded | 3000 original | 3000 reworded | Turn recall (reworded, 900/3000) |
|---|---|---|---|---|---|
| recent_window | 1/31 | 1/31 | 4/31 | 4/31 | — |
| summary_window | 1/31 | 1/31 | 3/31 | 3/31 | — |
| retrieval_window | 31/31 | **6/31** | 31/31 | **7/31** | 0.16 / 0.13 |
| combined (defaults) | 31/31 | **3/31** | 31/31 | **3/31** | 0.10 / 0.10 |
| combined_no_recover | 29/31 | 4/31 | 19/31 | 3/31 | 0.13 / 0.10 |

**What this shows.** Lexical retrieval finds the source turn for only 10–16% of
reworded questions; the facts still kept are mostly in recent turns. The headline
31/31 depends on word overlap between question and evidence. This is a deliberately
harsh worst case (zero shared words); real questions usually share some words, so
real-world retention lies between these results. It is the evidence for semantic or
hybrid retrieval (T6). Live answer accuracy on reworded questions was not run.

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
| Real-world retention | LongMemEval-S evidence recall (offline) and one live answer-accuracy run (D118, 95 questions, exact-match grading) measured above. |
| Provider-billed tokens / cost | Local estimates only; historical overruns up to 1.78× on small requests. |
| Model summarization quality/cost | `PromptSummarizer` exists; not run against a model. |
