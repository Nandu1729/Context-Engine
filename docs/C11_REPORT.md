# C11 — measured local baseline, ACTIVE

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
