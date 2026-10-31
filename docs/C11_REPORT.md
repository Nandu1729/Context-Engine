# C11 — measured local baseline, ACTIVE

2026-10-03:[semantic preflight](C11_SEMANTIC_PREFLIGHT.md) design complete. Pinned
English local BGE-small ONNX candidate and bounded hybrid-retrieval/evaluation plan;
public metadata and local environment checked. No installation,weight download,
embedding execution or core change. Next isolated setup approval;C11 stays ACTIVE.

2026-10-03,D106:[diversity candidate review](C11_DIVERSITY_REPORT.md) COMPLETE and
REJECTED. Synthetic paraphrase0→3/3 did not generalize:development full-message
coverage19→10/56 and18→10/56;17condition-level count regressions,52conditions lose
retrieved text. Keep core0.9.6 unchanged;no adoption or model-quality claim.
Next research requires semantic-relevance design,not retuning this failed identity.

2026-10-03:[synthetic regression baseline](C11_RETRIEVAL_PROBE_REPORT.md) implemented
and run offline:8conditions fit;single-fact/direct-event evidence retained,paraphrase
events0/3 at both budgets. Failures preserved;no model scoring or candidate adoption.
Next:separate relevance candidate against this fixed baseline and evidence-loss checks.

2026-10-03:[multi-event diagnosis](C11_MULTIEVENT_DIAGNOSTIC_REPORT.md) reproduces
two saved requests and their exact retrieval selections offline. Relevant events
rank5–543 and are excluded after the280-token retrieval allocation fills. No
WINDOW exclusion/overlap/finalizer failure explains these eight omissions. Next is
a separately specified relevance experiment,not another connection demo or model
call. Core/candidates and checkpoint status unchanged.

2026-10-02,D103:[isolated overlap-union experiment](C11_RETRIEVAL_UNION_REPORT.md)
complete:137focused tests PASS,70offline conditions within budget,complete marked
messages19→22/56 at900 and18→22/56 at3000. Known missing span restored;partial text
displaced in10conditions. Prototype not adopted,no model-quality/cost qualification.
C11 stays ACTIVE;previous local-profile evidence below remains unchanged.

2026-09-24,D086. Offline profiling only;C09 quality remains failed and C10 is not
accepted. No new inference,price assumptions,algorithm changes or default adoption.

[Local measurements](../output/c10-local-001/operations.json):initial indexing
processed100turns in17.26ms;unchanged indexing processed0turns in3.35ms while
preserving identical chunks. Twenty warm assemblies produced identical request
fingerprints,p50=27.31ms/p95=27.86ms. Total temporary drill storage1,167,360bytes
includes source,backup,two restored databases and deletion authority;not steady-state
production storage per conversation. Synthetic local replay hit confirmed and
old replay invalidated after restore. No provider cache discount was measured.

Decision:retain existing versioned index reuse. Do not add vector infrastructure,
memoization or summary-generation complexity without a measured bottleneck and a
no-regression comparison. Avoid tuning token estimates downward while historical
provider-input overruns remain unresolved. Keep the optional answer policy separate
from core defaults until independently qualified.

Limitations:one small author-created workload,not randomized paired before/after
optimization;no acceptable-quality production cost per useful answer. Free-tier
configured$0 is not proof of production savings. CPU timings are not CPU billing;
summary generation and provider latency/cost are absent. No C11 acceptance claimed.

Next:owner-selected representative workload,approved targets and quality baseline;
then paired cold/warm/index-update/replay profiles with CPU/storage/provider/summary
costs. Proposals may be rejected;completion does not require adopting every idea.
