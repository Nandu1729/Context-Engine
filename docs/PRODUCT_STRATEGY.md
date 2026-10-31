# Product strategy

Updated 2026-10-31. These are hypotheses to test with developers, not validated
market facts. No customer interviews, waitlist or usage data exist yet.

## The problem worth paying for

Developers building long-running agents and chat apps hit three concrete problems:

1. **Context overflow errors and silent truncation**: requests fail or lose the
   start of the conversation when history grows.
2. **Forgotten facts**: the model "forgets" an ID, decision or instruction from
   earlier turns because naive windowing dropped it.
3. **Cost and latency of sending full history**: every turn re-sends everything.

The engine's evidence today addresses (1) and (2) at the context level: every
assembled request fits its budget or fails with a typed error, and on the frozen
corpus retrieval keeps 31/31 planted facts at a fraction of the raw size. Whether
that turns into better *answers* on real conversations is not yet measured. That
is the claim customers would pay for, so it must be proven first.

## Offerings evaluated

| Offering | Dependencies | Build cost | Time to first revenue | Recommendation |
|---|---|---|---|---|
| A. Open-source Python SDK | Exists (0.10.0); needs PyPI publish, docs site, license choice | Low | None directly; drives adoption | **Do first** |
| B. Hosted Context API | Multi-tenant storage, signup, API keys, rate limits, billing, ops on-call | High | 2–4 months after SDK traction | Later |
| C. MCP server | Thin wrapper over SDK/memory (tools: add_turn, get_context, pin) | Low–medium | Indirect | **Second**: cheap distribution into coding agents |
| D. SaaS dashboard | B first | High | After B | Later |
| E. Enterprise / private deployment | Self-hosted service exists; needs qualification (C10/C12), support, security review | Medium–high per customer | Possibly fastest *large* revenue, but long sales cycle | Opportunistic, after references |

## Smallest product that could get first paying customers

1. **Publish the SDK** (free, open source) with an honest README: what it
   guarantees (budget safety, provenance, no hidden calls) and what it does not
   (answer quality claims).
2. **Ship an MCP server** so Claude Code / Cursor-style agents can use durable
   memory and budgeted context with no code.
3. **Offer paid "integration + evaluation" services** to 3–5 small AI startups:
   integrate the SDK into their agent and run `strategy-eval`-style measurements
   on *their* conversations. This produces real-data evidence, case studies and
   revenue without building hosted infrastructure.
4. Only once several teams use it weekly, build the hosted API (B) for teams who
   do not want to run storage themselves.

## Target customers, in order

1. Individual developers and small startups building agents (adoption, feedback).
2. Coding-agent builders (long sessions, large tool outputs: CAP + retrieval fit well).
3. Companies with compliance needs (provenance, deletion, self-hosting): enterprise later.

## Differentiation to validate

- Hard budget guarantee with a full-request token estimate and typed overflow errors.
- Exact provenance for every retrieved span; deletion-aware memory.
- No hidden model calls; deterministic, inspectable assembly.
- A built-in evaluation harness that measures retention separately from accuracy.

Competing approaches exist (framework memory modules, hosted memory services,
long-context models). Check their current features and pricing before positioning;
this document does not assume them.

## Kill / continue criteria (proposed)

Continue toward hosted API only if, within ~8 weeks of SDK publication: at least
3 external teams integrate it, at least 1 pays for integration/evaluation work, and
a real-data evaluation shows retention or accuracy gains at equal or lower cost.
