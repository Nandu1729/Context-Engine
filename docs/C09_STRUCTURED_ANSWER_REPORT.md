# C09 structured-answer mitigation — offline integration

2026-09-24. Added an opt-in repository integration on unchanged0.9.2. No API
calls,credential/real-ledger access,default changes or historical regrading.

## Design

Groq documents strict JSON-schema mode for GPT-OSS20b/120b,requiring closed objects
and all fields required;streaming/tool use are unsupported. Its documentation
distinguishes schema compliance from factual correctness. We retain local checks
and error handling rather than assuming requests cannot fail.
[Official structured-output documentation](https://console.groq.com/docs/structured-outputs).

[Structured client example](../examples/structured_answers.py) supplies immutable
generation configuration,a schema-aware serializer and a matched ProviderClient
subclass. It sends `response_format` with `json_schema`,strict=true,a required
string answer,and no extra properties. It rejects tool-use requests. No arbitrary
schema or transport-time payload injection is permitted by this example.

Use the same counter for assembly and final provider admission:the entire response
schema participates in token estimates,request fingerprints,quota reservations and
cache identity. Existing replay/accounting/transport remain in use. Mismatched
generation/counter settings and retry overrides fail before dispatch;one attempt
only. Original payloads and source history are not mutated.

The remote schema intentionally uses a small documented shape subset. It does
not enforce local length,identifier or control-character restrictions;we do not
assume support for undocumented string keywords. A schema-valid empty answer string
is still rejected by [local validation](ANSWER_CONTRACT.md). This is a candidate
mitigation for empty/non-JSON final content,not evidence the provider issue is fixed.

## Integration

Import these repository examples explicitly;they are not installed SDK defaults:

```python
from examples.structured_answers import StructuredGeneration, StructuredAnswerClient
from examples.validated_answer import validate_answer
from context_engine.answers import AnswerContract

generation = StructuredGeneration(
    model="openai/gpt-oss-20b", contract=AnswerContract("ascii_identifier")
)
# Supply your authorized existing store,quota,prices and key explicitly.
client = StructuredAnswerClient(
    generation=generation, store=store, quota=quota, prices=prices, api_key=key
)
# During assemble_context(...):
# system=policy + generation.contract.instructions(), token_counter=client.counter
# Then call client.complete(...) with matching completion reservation.
# Keep the original result even when validation rejects it.
answer = validate_answer(result, generation.contract)
```

Do not reuse a plain-chat prepared request's estimate/hash or frozen experiment
identity;schema accounting may change context selection under a tight input cap.
Any future paired comparison must disclose that effect.

## Verification / next step

12 new offline tests plus105existing caller/provider checks:117PASS in0.41s.
Coverage includes actual dispatched fake payloads,full-schema token admission,
pre-dispatch overflow,accounting,no request mutation,tool rejection,immutable
schema copies,configuration mismatch and distinct structured/plain request keys.
No full-suite rerun;package/frozen evidence unchanged.

Live schema acceptance and empty-answer mitigation remain NOT_EVALUATED. Next
proposal:at most2 separately accounted Groq20b smoke calls on the original free-tier
account,256output,no retries,to test this integration. This proposal is not approval;
do not repeat the32-case matrix or replace old failures. C09 remains ACTIVE.
