# Incident-response pilot preflight — TEST_ONLY

2026-09-28,D097:owner requests a sample-data demo before later Hugging Face data.
Added a local static HTML generator and twelve-turn incident sample;see
[demo instructions](INCIDENT_DEMO.md). Current output is
`output/incident-demo-002/index.html`:838estimated tokens/900allowance,with real
WINDOW/retrieval selection. No answers,inference,downloads or core changes.
Sample-only80token CAP preserves the rollback version;the default35token CAP
can omit that middle fact despite keeping its turn ID. Both behaviors tested.
Custom data export requires explicit `--show-content`;HTML escaped and passive.
Final scoped verification:64tests PASS2.40s;ruff and brain/diff checks PASS.
Next:owner tries the local demo,then selects a dataset and mapping separately.

2026-09-28,D096. Owner delegated workload selection with "go for best and
continue". Selected incident-response histories because they match the existing
benchmark domain. This selects synthetic offline preparation,not customer data,
deployment,authenticated fact authority,new inference or release acceptance.

## Built

[incident_preflight.py](../scripts/incident_preflight.py) assembles eight fresh,
author-visible incident scenarios:conflict,reversed conflict,duplicate conflict,
explicit update,reversed update,entity separation,missing fact and hostile tool.
Each runs at900/3000 with default recovery off and explicit recovery on:32conditions.
No expected answers or truth fields enter assembly. No new policy is proposed:
the system text is the existing development-test evidence/data instruction.

Checks inspect actual emitted WINDOW/RETRIEVED text,including duplicate counts,
not just source IDs or diagnostic blocks. They verify block/wire consistency,
one unchanged system message,the current question,immutable originals and a full
canonical-request token recount. Errors remain in the planned denominator;
exception payloads are not included in report rows. Unexpected failures propagate.

A separate temporary SQLite drill verifies ten lifecycle properties:seeded cache,
pre-deletion evidence presence,surviving history,deleted turn/content absence,
current content retention,other-scope separation/preservation,cache invalidation,
and changed restore epoch. Restore uses the latest same-host deletion watermark.
Storage creates private child directories;no operator databases/ACLs are touched.

The script accepts only a new report output path,no input/customer/key files and
no provider configuration. Python socket connections/DNS are blocked during
checks;the tokenizer must already be cached. This is not an OS sandbox for native
or subprocess networking. Outputs contain hashes,counts and booleans,not histories
or generated answers;exclusive create prevents overwriting earlier evidence.
Failed preflight returns exit1. Even success remains TEST_ONLY with
answer_quality=NOT_EVALUATED and production_qualified=false.

## Verified locally

-32/32assembly conditions PASS;10/10lifecycle checks PASS;zero inference calls.
-Input estimates91–185tokens. These small histories fit both budgets easily;
  this does NOT exercise budget pressure,long-history retrieval or load capacity.
  Repeated budgets/modes are overlapping checks,not independent quality samples.
-13new tests plus existing operations/memory/recovery regressions:130PASS1.36s.
  Covers repeatability,truth-free input shape,content-free reports,missing actual
  wire evidence,duplicate loss,inconsistent blocks,lifecycle failure,error
  denominators,unexpected exceptions,network guard/restoration,CLI exit status,
  existing-output refusal and a concurrent-writer overwrite race.
-Final combined run including eight brain-integrity tests:138PASS1.93s. Extended
  the brain test's copied-artifact fixture for the new links and kept hot memory
  below its limit;brain index/check and diff whitespace checks pass.
-Scoped ruff PASS. No production source,archived runtime,frozen cases or historical
  report changes. The0.9.6 sourcefreeze remains unchanged. These new script/tests
  were verified locally,not retroactively included in the earlier three-OS CI run.

Saved [report](../output/incident-preflight-001/report.json),SHA256:
`8dc917cd39e315a552c1b035bc789f5098e9229d9d1635bc7d5d583898d8bc7f`.
The report binds the actual runtime,runner and synthetic input hashes. It is a
development preflight artifact,not a frozen live qualification protocol.

Manual reproduction,only when needed,use a fresh output path:

```sh
uv run --locked --offline python scripts/incident_preflight.py --output output/incident-preflight-002/report.json
uv run --locked --offline python -m pytest -q tests/test_incident_preflight.py
```

## What remains

This verifies that relevant short records reach context and deletion survives a
local restore. It neither resolves conflicting claims nor proves model resistance
to hostile instructions. Source authority remains untrusted prose;no verified-fact
resolver has been added. Scope separation here is SDK storage behavior,not a new
HTTP authorization test. No model latency/cost,SLO,offsite recovery or real pilot
observation was measured. Prior failed C09 scores remain unchanged.

Next external input:an owner-designated incident-domain reviewer and a description
of which sources/updates are authoritative in the intended workload. Use the
[review packet](C09_QUALITY_REVIEW_REPORT.md) and [intake](OWNER_REVIEW.md#pilot-intake-after-cross-platform-ci).
Only then design workload-specific heldout cases and targets;new inference still
requires separate bounded approval. No need to rerun the old Windows diagnostic.
