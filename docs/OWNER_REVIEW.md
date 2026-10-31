# Owner review — current release decisions

2026-10-02,D104:local demo/SDK chosen and prepared. Start with the
[simple walkthrough](LOCAL_QUICKSTART.md):open the page,find `checkout-v41`,then
tell us whether it makes sense. No unfamiliar dataset grading or API key needed.
This is scope selection,not acceptance of all checkpoints. Earlier intake notes
below are historical;production choices remain for a later phase.

2026-10-02,D103:[completion audit](PROJECT_COMPLETION_STATUS.md). Immediate owner
choice is local demo/SDK versus production preparation. Manual answer ratings are
not blocking offline engineering;new70condition prototype completed without them.
No approval or ratings attributed to owner. Production needs environment/workload,
operating targets/owner/pilot duration and separately approved evaluation budget.

2026-09-29,D102:[assistant recheck](C10_LONGMEMEVAL_RECHECK_REPORT.md) complete.
Owner worksheet is still blank;assistant assessment saved separately,not attributed
to owner. To reduce effort,first check preference row156 and user-fact row49 in
`output/private/longmemeval-live-report-001/manual-review.md`;rate both responses
and briefly note agreement/disagreement. Remaining ratings can follow later.
D100 exhausted14/14;no API reruns or70held-out use. No acceptance inferred.

Updated2026-09-28:the initial foundation notes below are historical. C00–C08 are
READY for owner review,C09 quality remains open,C10/C11 offline preparation has
advanced,and C12 is blocked. See [release gate register](C12_REPORT.md).
Needed:release scope and deployment/data location,representative pilot workload,
operating owner/targets/observation period,and checkpoint acceptance. Further model
calls require a separate bounded approval;“finish quickly” does not waive failures.

## Pilot intake after cross-platform CI

D097:owner chooses a sample-data demo now,Hugging Face data later. The
[local demo](INCIDENT_DEMO.md) is ready to inspect. Dataset URL/split/fields and
data-use approval remain future inputs,not blockers to trying the synthetic demo.

Linux/macOS/Windows offline CI has passed on3e3e0e4. No repeated diagnostic is
needed. [Quality/authority review](C09_QUALITY_REVIEW_REPORT.md) separates the
remaining semantic failures from platform correctness;it is not independent
review or permission to change the product's scope.

Owner delegated workload selection on2026-09-28. Selected incident-response
histories for synthetic offline preparation (D096),matching the benchmark domain.
[Preflight](C10_INCIDENT_PILOT_REPORT.md) passes32assembly/10lifecycle checks.
This is not approval for real-world data,deployment or a trusted-fact contract.

For the selected workload,record these before real-data or live execution:

| Input | Current status / why needed |
|---|---|
| Task and representative history | Synthetic incident-response selected;real questions,history size/languages/tools,updates and failure consequences pending |
| Source authority | Pending:who may assert a fact,how updates supersede it,and whether trusted structured records exist |
| Independent reviewer | Pending:domain reviewer for authority/truth;do not self-certify author-visible fixtures |
| Data and environment | Pending:synthetic first;real-data authorization,retention/location and deployment approval separately |
| Load and operating targets | Pending:host,concurrency,request rate,storage,latency/error targets;ENTERPRISE numbers remain proposals |
| Recovery and ownership | Pending:backup scope,RPO/RTO,operating/incident owner and observation period |
| Quality/cost execution | Pending:new reviewed protocol and separately bounded call/token/spend approval;old failures unchanged |

Offline pilot preparation may use synthetic data without customer material,
credentials or network inference. It must measure context retention,answer
validity,semantic accuracy and total cost separately. Any synthetic drill is
TEST_ONLY,not a pilot result or release approval. No new implementation should
assume trusted structured facts until the owner confirms that input contract.

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
