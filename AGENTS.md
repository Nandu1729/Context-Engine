# Context Engine working agreement

This folder is the project workspace. The owner is the product decision maker.

## Resume with bounded context

1. Read `brain/INDEX.md` and `brain/STATE.md` first.
2. Read only the current checkpoint in `docs/CHECKPOINTS.md` and documents routed by the index.
3. Inspect relevant code and evidence before assuming the recorded state is current.
4. Use `python3 scripts/brain.py search "topic"` for local discovery. Read the original section before acting.
5. Do not reload the whole PRD, archive, or repository on every task. Read more whenever correctness requires it.

## Authority and scope

- Current superseding decisions: D073 marks C06 complete at snapshot249 with limitations; no C06 rerun/settlement remains. D075 ends the Kimi handoff; this assistant owns C09 implementation/review, with owner acceptance still required. D037/D050 bullets below describe historical development order, not a command to restart C06. D076 adds local worker containment and TEST_ONLY scoring in0.9.1; C09 remains ACTIVE pending approved independent live-quality evidence.

- Follow the owner's current instructions, then recorded owner decisions, then the PRD and accepted amendments.
- The PRD is the preserved source. Proposals and engineering defaults are not owner approvals.
- Work autonomously on reversible implementation within the requested scope. Present completed checkpoint evidence for owner review; do not seek approval for every file or routine choice.
- Do not mark a checkpoint owner-accepted without explicit owner feedback.
- Ask about material product choices when needed, while progressing independent work.
- Do not deploy, purchase services, send messages, or use real customer data merely because they appear on the roadmap.
- Owner deferred C06 live validation to allow offline C07/C08 work (D037). Remind at both handoffs; before C09 real-world quality work, C11 measured model-cost work or C12 release, stop and return to the C06 live prerequisites if unresolved. This is not a background reminder or approval to spend.
- D050 reaffirms C08 offline after partial live C06 results. Preserve C06's archived 0.7.2 environment (`output/private/c06-frozen-env`), journal, shared ledger and unchanged protocol. Resume through the archived environment using C06_REPORT.md, never evolving workspace code; do not repeat resolved key/target/quota questions.

## Engineering invariants

Current live exception(D077): owner approved the separately frozen C09 smoke in
`docs/C09_LIVE_PROTOCOL.md`,original account/current .env,32 requests maximum,
20b/256 output,no retries or paid use. Shared ledger may append C09 usage while
preserving every historical record. This supersedes D076's offline-only restriction
for this experiment,not C06 reruns,owner acceptance or deployment.

D077 is now exhausted:32/32 calls complete. D078 authorizes offline0.9.2 repairs,
not new inference. Old live001 status/report must use its preserved
`output/private/c09-frozen-env/bin/python`;never rebase its guard or scores.
PRD WINDOW exclusion remains default;new recovery is explicit SDK opt-in only.

D079 prepares qualification002-r1 offline on unchanged0.9.2. Its fresh cases are
author-visible,not independently reviewed.32 proposed new calls are NOT authorized;
obtain owner review and a new bounded budget,then freeze/test a separate live runner.
Never reuse live001 claims or treat TEST_ONLY scores as model-quality evidence.

D080 supersedes D079's pending execution authorization only:owner approved max32
new Groq20b/256-output calls,original account/current.env,no retries or paid usage,
under C09_QUALIFICATION_LIVE_PROTOCOL. Cases/engine/targets unchanged;not independent
review,default adoption or owner acceptance. Separate live002 claims and full ledger.

D080 is exhausted:32/32 completed,PRIMARY14/16,strict target FAIL. Five empty answers
preserved;next offline diagnosis only. No further calls,retries,claim resets or
rebasing frozen scripts/cases/runtime. See C09_QUALIFICATION_LIVE_REPORT.

D082 permits only2 separately identified Groq response-shape diagnostics under
C09_RESPONSE_DIAGNOSTIC_PROTOCOL,original free-tier/current.env,no retries. Do not
replace benchmark failures or store raw bodies/reasoning. Stop after2 or on errors.

D082 exhausted:2diagnostics complete under002 identity (001preflight had0calls).
Raw provider empty content reproduced;original failures remain. No new inference.

D084 supersedes that inference restriction ONLY for the approved two-call
structured smoke in C09_STRUCTURED_SMOKE_PROTOCOL:original free-tier/current.env,
20b/256 output,no retries,new claims,unchanged baseline,never C09 acceptance.

D084 exhausted:2/2 calls complete,2valid JSON/1correct. Preserve smoke001;
next offline contradiction analysis,no further inference or qualification reruns.

D086 owner requests whole-project completion:independent offline C10/C11/C12
preparation is now authorized despite C09's open quality gate. Acceptance dependencies
remain;no new API budget,real customer data,deployment,gate waiver or release approval.
See C10/C11/C12_REPORT for local evidence and external/owner blockers.

D087 freezes offline policy003 resources/runtime,including policy/schema examples.
Never edit those under the same identity.32conditions are16unique payloads;the
separate16-call diagnostic amendment is only proposed,not authorized. No inference.

D088 supersedes only that dispatch restriction:owner “continue” approved the
explicit16-call original-account free-tier diagnostic,max256output,no retries,
under C09_POLICY_LIVE_PROTOCOL. Independent review and broader acceptance remain
pending. Separate claims/receipts and baseline-preserving ledger accounting only.

D088 exhausted:16/16 complete,5/8correct each arm,target FAIL,candidate not adopted.
Preserve policy-live003;no further inference or automatic prompt experiments.

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

- Manual-first owner preference (D089): offer concise manual setup, Docker, CI and long-test steps before executing them. Reserve Codex usage for implementation, debugging and review; avoid redundant full runs or monitoring. Record exact results, not assumed success. Explicit later execution requests override this default.
- After every completed checkpoint, give the owner a short report stating what was done, verification results, any material limitation, and the next checkpoint. Save it as `docs/Cxx_REPORT.md` and link it in the handoff. This is an explicit owner preference, not optional formatting.
- Update `brain/STATE.md` with actual progress, checks, unresolved issues, and the exact next action.
- Append a short evidence entry to `brain/JOURNAL.md`; use `brain/DECISIONS.md` for durable decisions.
- Update checkpoint status and requirement evidence only for completed work.
- Run `python3 scripts/brain.py index` then `python3 scripts/brain.py check`.
- Keep INDEX + STATE at most 900 whitespace-delimited words combined. This is a reading-size proxy, not model token accounting.
- At 150 journal lines, archive old entries to `brain/archive/` with an index link; preserve decisions and evidence.
- Record suggestions with expected benefit, cost, experiment, and owner decision. Do not expand scope silently.

Persistent memory lives in these files. Resumption depends on opening this workspace and reading them; it is not model-internal memory or a background process.
