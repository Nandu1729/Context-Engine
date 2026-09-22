# Gemini diagnostic 001 — small progress report

Completed: 2026-09-14. Separate provider diagnostic, **not C06 completion or enterprise acceptance**.

## What was done

Recorded the owner's exact Free Tier limits and selected stable Gemini 3.5 Flash Lite before collecting answers: 15 requests/minute, 250,000 tokens/minute, 500 requests/day. Implemented an isolated native text-only experiment runner with full-request token preflight, fixed lifetime call limits, private durable dispatch/receipt records, strict usage validation and zero-resend recovery. Core 0.8.0, archived Groq 0.7.2, dependencies and credentials were not changed.

The frozen experiment compared WINDOW-only A1 with all-layer A5 on the same known synthetic flagship question. Settings and limitations were declared in [Gemini setup](GEMINI_SETUP.md) before live dispatch; no answer-driven retuning occurred.

## Live result

| Variant | Evidence retained | Answer | Correct | Estimated input | Gemini count / actual input | Output / thoughts |
|---|---|---|---|---:|---:|---:|
| A1 — WINDOW only | No | UNKNOWN | No | 798 | 705 / 705 | 1 / 0 |
| A5 — all five layers | Yes | shard-19 | Yes | 804 | 714 / 714 | 4 / 0 |

Both responses ended with STOP and valid usage within the 900-token input limit. Two token-count requests plus two generation calls; **1,424 provider-reported generation tokens** total (1,419 input + 5 output, zero thought tokens). Free Tier configuration was used; no billing account change or paid upgrade was performed. This is usage evidence, not an independent billing audit.

Evidence: `output/gemini-comparison-001.json`; immutable private plan and four intent/receipt pairs in `output/private/gemini-comparison-001/`. Plan SHA-256: `374e697390422ca974d1815c15a8e41bfe59042a385c6a8c8d3f92091d89393f`. Provider-reported model version: `gemini-3.5-flash-lite` for both answers.

## Verification

- **598 tests passed**, including 46 new comparison cases and 26 Gemini preflight cases. Two existing service test-client deprecation warnings remain.
- Scoped lint/format passed. Tests cover role/data preservation, exact count/generate payloads, lifetime resume, pre-dispatch intent, quota/error stops, missing/inconsistent usage, thought-token accounting, truncation, secret reflection/redaction, response bounds, private-file checks, lock exclusion and offline defaults.
- Actual completed-run replay with socket creation blocked returned identical results with zero requests; all private records stayed byte-identical. The first diagnostic attempt blocked asyncio's own local socketpair during event-loop creation, so the successful check initializes the loop before disabling socket creation. No provider call occurred in either replay check.
- Both package source hashes still match their original freezes. Groq snapshot061 and its account/matrix SQLite files have identical SHA-256 values before and after this work.

## Limitations and next step

One already-known question is a smoke comparison, not a 31-fact accuracy result, representative workload, production adapter or enterprise qualification. The 512-output/MINIMAL Gemini settings differ from Groq's settings. The narrow runner has no multi-run account scheduler and intentionally cannot create another run, reset quota or retry an uncertain request. Larger Gemini evaluation needs a new predeclared scope and shared provider accounting that carries this usage forward; no additional calls are queued.

Groq **C06 remains incomplete**: 236 live responses + 62 non-fits, 446 slots pending. Its daily guard remains at 198,729/200,000 tokens. Recheck after **2026-09-15 05:30 IST** and resume062 using [C06 report](C06_REPORT.md), the same archived runtime and ledger. C09/C11/C12 evidence gates remain in force; no background reminder or inference task is scheduled.
