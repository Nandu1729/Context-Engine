"""Opt-in Groq structured-answer integration; frozen0.9.2 package stays unchanged.

Use client.counter for assembly, then validate_answer(result, generation.contract).
This module never loads credentials, dispatches on import, retries or alters schemas
after accounting. Provider enforcement is unqualified until approved live testing.
"""

from dataclasses import dataclass

from context_engine.answers import AnswerContract
from context_engine.errors import ContractError
from context_engine.models import ChatRequest, canonical_json
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import GenerationConfig, RetryConfig
from context_engine.tokens import TiktokenCounter


@dataclass(frozen=True)
class StructuredGeneration(GenerationConfig):
    contract: AnswerContract = AnswerContract()

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.contract, AnswerContract) or self.tool_choice != "none":
            raise ContractError("Structured answers require a contract and no tool selection")

    def response_format(self):
        # Documented portable shape subset. Identifier/length/control restrictions
        # remain mandatory in the local contract; do not assume remote support.
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "context_answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            },
        }

    def to_wire(self, request):
        if (
            not isinstance(request, ChatRequest)
            or request.tools
            or any(m.tool_calls or m.role.value == "tool" for m in request.messages)
        ):
            raise ContractError("Structured answers do not support tool-use requests")
        payload = super().to_wire(request)
        payload.pop("contract")  # Local dataclass metadata is not a provider parameter.
        payload["response_format"] = self.response_format()
        return payload


@dataclass(frozen=True)
class StructuredSerializer:
    generation: StructuredGeneration
    name: str = "groq-structured-answer-json-v1"

    def serialize(self, request):
        return canonical_json(
            {**request.to_wire(), "response_format": self.generation.response_format()}
        )


class StructuredAnswerClient(ProviderClient):
    """Existing accounting/replay client with a matched schema-counting serializer."""

    def __init__(self, *, generation, **kwargs):
        if not isinstance(generation, StructuredGeneration):
            raise ContractError("Structured generation configuration required")
        if "counter" in kwargs or "retries" in kwargs:
            raise ContractError(
                "Structured example fixes schema counting and single-attempt policy"
            )
        super().__init__(
            generation=generation,
            counter=TiktokenCounter(serializer=StructuredSerializer(generation)),
            retries=RetryConfig(max_attempts=1),
            **kwargs,
        )

    async def complete(self, request, budget, **kwargs):
        if (
            not isinstance(self.generation, StructuredGeneration)
            or not isinstance(self.counter, TiktokenCounter)
            or not isinstance(self.counter.serializer, StructuredSerializer)
            or self.counter.serializer.generation != self.generation
            or self.retries.max_attempts != 1
        ):
            raise ContractError("Structured counting/generation/retry settings disagree")
        return await super().complete(request, budget, **kwargs)
