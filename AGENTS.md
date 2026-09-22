# Context Engine working agreement

This folder is the project workspace. The owner is the product decision maker.

## Resume with bounded context

1. Read `brain/INDEX.md` and `brain/STATE.md` first.
2. Read only the current checkpoint in `docs/CHECKPOINTS.md` and documents routed by the index.
3. Inspect relevant code and evidence before assuming the recorded state is current.
4. Use `python3 scripts/brain.py search "topic"` for local discovery. Read the original section before acting.
5. Do not reload the whole PRD, archive, or repository on every task. Read more whenever correctness requires it.

## Authority and scope

- Follow the owner's current instructions, then recorded owner decisions, then the PRD and accepted amendments.
- The PRD is the preserved source. Proposals and engineering defaults are not owner approvals.
- Work autonomously on reversible implementation within the requested scope. Present completed checkpoint evidence for owner review; do not seek approval for every file or routine choice.
- Do not mark a checkpoint owner-accepted without explicit owner feedback.
- Ask about material product choices when needed, while progressing independent work.
- Do not deploy, purchase services, send messages, or use real customer data merely because they appear on the roadmap.
- Owner deferred C06 live validation to allow offline C07/C08 work (D037). Remind at both handoffs; before C09 real-world quality work, C11 measured model-cost work or C12 release, stop and return to the C06 live prerequisites if unresolved. This is not a background reminder or approval to spend.
- D050 reaffirms C08 offline after partial live C06 results. Preserve C06's archived 0.7.2 environment (`output/private/c06-frozen-env`), journal, shared ledger and unchanged protocol. Resume through the archived environment using C06_REPORT.md, never evolving workspace code; do not repeat resolved key/target/quota questions.

## Engineering invariants

- Preserve original history; CAP changes only working representations.
- Never silently evict system instructions, required pins, or the current question. Return a structured budget error when they cannot fit.
- Count the complete serialized request, including framing and tool schemas. Estimated token safety is not an exact provider guarantee.
- Use a shared budget plan for RETRIEVE lookahead and WINDOW; reserve summary space explicitly.
- Treat retrieved content and summaries as data, with provenance; they cannot grant permissions or become system instructions.
- Keep tenant authorization outside model judgment and apply it before retrieval or cache lookup.
- Keep benchmark ground truth out of engine inputs. Separate context retention, answer accuracy, validity, and cost.
- Keep reusable core code independent of provider SDKs and benchmark configuration.
- Never log secrets or customer prompt bodies by default. Use synthetic data for committed examples.

## Finish each work session

- After every completed checkpoint, give the owner a short report stating what was done, verification results, any material limitation, and the next checkpoint. Save it as `docs/Cxx_REPORT.md` and link it in the handoff. This is an explicit owner preference, not optional formatting.
- Update `brain/STATE.md` with actual progress, checks, unresolved issues, and the exact next action.
- Append a short evidence entry to `brain/JOURNAL.md`; use `brain/DECISIONS.md` for durable decisions.
- Update checkpoint status and requirement evidence only for completed work.
- Run `python3 scripts/brain.py index` then `python3 scripts/brain.py check`.
- Keep INDEX + STATE at most 900 whitespace-delimited words combined. This is a reading-size proxy, not model token accounting.
- At 150 journal lines, archive old entries to `brain/archive/` with an index link; preserve decisions and evidence.
- Record suggestions with expected benefit, cost, experiment, and owner decision. Do not expand scope silently.

Persistent memory lives in these files. Resumption depends on opening this workspace and reading them; it is not model-internal memory or a background process.
