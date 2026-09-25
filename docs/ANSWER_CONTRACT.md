# Optional exact-answer contract

Added0.9.2. Import `AnswerContract` from `context_engine.answers`;no provider,
evaluation,network or credential dependency. This is opt-in validation,not an LLM
guarantee,truth checker,authorization mechanism or automatic retry policy.

```python
from context_engine.answers import AnswerContract

contract = AnswerContract("ascii_identifier")
instructions = contract.instructions()
schema = contract.json_schema()
value = contract.parse('{"answer":"node-27"}')  # exactly "node-27"
```

Kinds:`text` preserves Unicode values verbatim;`ascii_identifier` allows ASCII
letters/digits followed by letters/digits/`.`/`_`/`:`/`/`/`-`;`integer` accepts
canonical base-ten integer strings,not JSON numbers. All permit exact `UNKNOWN`.
No Unicode normalization,hyphen substitution,case folding,prose extraction or
silent whitespace trimming. `shard‑84` is not `shard-84` in identifier mode.

The JSON object must have exactly one string field:`answer`. Duplicate keys,extra
fields,Markdown fences,trailing explanations,empty values,surrounding value
whitespace,control codes/line separators,surrogates and malformed JSON reject with
a sanitized `ContractError`. Documents are bounded at16,384 UTF-8 bytes;values
default to512 characters with a configurable7–2048 limit. Schema describes shape,
length and kind pattern;the local parser adds stricter whitespace/control/Unicode
checks. It is not a promise that every provider supports this schema dialect.

Callers explicitly append `instructions` to their trusted system policy **before**
assembly,so its token cost is counted. The engine never silently rewrites system
text. `json_schema()` is available for separately configured provider schema modes;
the Groq client does not automatically inject it or parse answers. Validate the
returned raw text explicitly,handle failures,then perform task-specific evidence
checks. Do not infer permission to retry failed outputs or to act on parsed values.

The old live001 evaluator remains strict plain-text exact-match;its8/32 result is
unchanged. Live002 measured27/32 conforming responses,with five empty answers;
PRIMARY accuracy14/16 missed its target. See the [empty-answer diagnosis](C09_EMPTY_ANSWER_REPORT.md).

## Caller integration

The optional [structured-answer client](C09_STRUCTURED_ANSWER_REPORT.md) now prepares
strict provider JSON output with schema-aware accounting. It still requires the
local caller check below;provider success and schema shape are not factual accuracy.

The repository-only [validated-answer example](../examples/validated_answer.py)
separates provider protocol success from an application-usable answer:

```python
from examples.validated_answer import UnusableAnswer, validate_answer

# result is the original ModelResult returned by your existing provider call.
# Keep it for usage/accounting even when validation fails.
try:
    answer = validate_answer(result, contract)
except UnusableAnswer as error:
    # Content-free reason; stop, do not silently retry or substitute an answer.
    failure = error.to_dict()
```

This opt-in example does not change the SDK or service by default. Validate task
evidence separately;even well-formed UNKNOWN or an identifier may be incorrect.
