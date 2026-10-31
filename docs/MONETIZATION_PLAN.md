# Monetization plan

Updated 2026-10-31. Figures marked **measured** come from this repository. Figures
marked **assumption** are placeholders that must be replaced with current quotes
before any pricing decision. No price here has been tested with customers.

## Model

Hybrid: free open-source core (SDK + self-hosted service) → paid services first →
paid hosted API later → enterprise licensing/support last. Do not charge for
"token savings" until savings and answer quality are shown on the customer's data.

## Unit economics of the engine itself

The engine is CPU-only unless the caller enables a model summarizer.

| Cost item | Basis | Value |
|---|---|---|
| Assembly CPU time | **measured**, 100-turn / 16.6k-token history, Apple-silicon, single process | ~17 ms (retrieval+window), ~250–350 ms (all layers incl. CAP + summary) |
| Requests per vCPU-month at 30% utilization | 2.6M s × 0.3 ÷ 0.3 s | ~2.6M (all layers) to ~45M (retrieval+window) |
| Hosting | **assumption**: $40/month for 2 vCPU / 4 GB | $0.000008 per all-layer request |
| Storage | **measured** message text 109 KB for the 100-turn corpus; chunks/index roughly 2–3× more (**assumption**) | ~300 KB per conversation; 1 GB ≈ 3,000 conversations |
| Retrieval | in-process BM25, included in CPU time above | ~0 marginal |
| Summarization (optional) | caller's model: reads newly omitted turns every refresh; `summary_source_tokens_total` reports the volume | model price × tokens (customer pays if BYO key) |
| Payment processing | **assumption**: card processor ~3% + fixed fee per charge (verify Stripe/Razorpay current rates) | ~3–4% of revenue at $20+ invoices |

Conclusion: engine compute is negligible next to the customer's LLM bill. Pricing
should follow value (reliability, retained facts, saved LLM tokens, saved
engineering time), with costs dominated by support, storage and operations, not CPU.

## Gross margin (hosted API, illustrative)

With BYO-model-key (customer pays their own LLM and summarizer calls), hosting +
storage + processing stays well under 20% of a $29–$99 subscription at moderate
usage, so gross margin above 80% is plausible. **If the hosted API pays for LLM
summarization itself, margin depends entirely on model prices**: pass it through
at cost plus margin, or require BYO key.

## Proposed tiers (hypotheses)

| Tier | For | Includes | Price idea |
|---|---|---|---|
| Open source | Everyone | SDK, self-hosted service, evaluation harness | Free |
| Integration sprint | Startups | 1–2 week integration + evaluation report on their data | Fixed fee (e.g. $1.5–5k, **assumption**) |
| Hosted Developer (later) | Individuals | ~50k assemblies/month, 1 project, community support | Free tier, then ~$29/month |
| Hosted Team (later) | Startups | Higher limits, several projects, usage analytics, email support | ~$99–299/month + usage |
| Enterprise (later) | Regulated teams | Private deployment, audit logs, retention controls, SSO, SLA | Annual license, quote |

Free-tier limit should be set from measured hosting cost per assembly and storage
per conversation, keeping the free tier under ~$1/user/month in cost.

## What customers would pay for (to validate)

- Fewer context-overflow failures and "the agent forgot X" bugs in production.
- Lower LLM spend at equal answer quality, **shown on their own traffic**.
- Compliance features: provenance, deletion guarantees, self-hosting.
- Saved engineering time versus building memory/retrieval in-house.

## Next steps

1. Publish the SDK; collect integration interest.
2. Sell 2–3 integration sprints; record each customer's measured before/after.
3. Use those numbers (not the synthetic benchmark) to set hosted prices.
