# Owner review — current release decisions

Updated2026-09-24:the initial foundation notes below are historical. C00–C08 are
READY for owner review,C09 quality remains open,C10/C11 offline preparation has
advanced,and C12 is blocked. See [release gate register](C12_REPORT.md).
Needed:release scope and deployment/data location,representative pilot workload,
operating owner/targets/observation period,and checkpoint acceptance. Further model
calls require a separate bounded approval;“finish quickly” does not waive failures.

## Initial foundation (historical)

The PRD describes two products that must advance together: a five-stage context assembly library and a reproducible harness proving retention, model utilization, validity, and cost. All 73 sections and 27 V1 acceptance items are routed in REQUIREMENTS. C00–C04 implementation is ready for review, including the frozen corpus and five validity gates. See the [short C04 report](C04_REPORT.md) and [proposed targets awaiting approval](PREREGISTRATION.md). C05 provider integration is next; no model accuracy or enterprise production readiness is claimed.

## Recommended product direction

Build the Python SDK and benchmark first, then a persistent, self-hosted service with enterprise controls. Keep inference optional so teams can use the engine with their existing agent provider. Validate on incident-response or customer-support histories before adding hybrid retrieval or automatic memory extraction.

"Enterprise" should mean demonstrated isolation, controlled access, deletion, recovery, compatibility, observability and supportability. It does not imply a certification, availability guarantee, or superiority over other products.

## Specification issues resolved by the architecture proposal

1. The 900-token example assigns all remaining space to retrieval/window without explicitly reserving summary and framing. The planner will account for every block before selection.
2. Pins can themselves exceed the budget. The system must reject this case with diagnostics, never quietly drop protected requirements.
3. A local tokenizer with a 1.07 multiplier gives an estimate, not certainty about the provider's serialized request. We need adapter accounting and measured calibration.
4. The six variants, five validity gates, and success threshold are not fully specified. EVALUATION proposes concrete definitions to freeze before runs.
5. Stable prefix placement can enable cache reuse but does not prove a cache hit or savings. Measure provider-reported cached tokens.
6. Original content preservation must coexist with authorized deletion and retention. Runtime storage needs source lineage and invalidation across derived data.

## Choices that shape later work

| Choice | Recommended working assumption | When it matters |
|---|---|---|
| Product shape | SDK + self-hosted service first | Before C08 service design |
| Initial workload | C04 uses synthetic incident-response history from the PRD; first real workload remains an owner choice | Before C09 held-out qualification / pilot |
| Quality targets | Approved unchanged on 2026-09-13, D047 | Before C06 inference runs; approval recorded |
| API spending cap | Free-plan-only testing, $0 paid spending, D047; actual account limits pending | Before live benchmark run; no paid upgrade authorized |
| Deployment region / data policy | Not supplied | Before C08 real deployment |
| Enterprise availability and recovery | Proposed targets in ENTERPRISE | Before production acceptance |

Owner feedback can approve, reject or amend individual proposals. Implementation can proceed on the shared core while these choices remain open. See CHECKPOINTS for demonstrations and evidence the owner will receive at every gate.
