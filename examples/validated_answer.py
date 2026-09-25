"""Opt-in caller boundary for machine answers; no dispatch, retry or ledger mutation.

Keep the original ModelResult for usage/accounting. This integration example does
not alter the frozen provider adapter or turn syntactic validity into correctness.
"""

from context_engine.answers import AnswerContract
from context_engine.errors import ContractError
from context_engine.providers.contracts import ModelResult


class UnusableAnswer(ContractError):
    code = "unusable_answer"


def validate_answer(result: ModelResult, contract: AnswerContract) -> str:
    """Return a verbatim conforming value, or a content-free failure; never retry."""
    if not isinstance(result, ModelResult) or not isinstance(contract, AnswerContract):
        raise ContractError("Expected a provider result and answer contract")
    if result.status not in {"success", "replay"}:
        raise UnusableAnswer("Provider did not complete an answer", reason="provider_not_completed")
    completion = result.completion
    if completion is None or completion.finish_reason != "stop":
        raise UnusableAnswer("Missing completed answer", reason="missing_completed_answer")
    if not completion.content.strip():
        raise UnusableAnswer("Provider returned no answer text", reason="empty_answer")
    try:
        return contract.parse(completion.content)
    except ContractError:
        raise UnusableAnswer(
            "Answer does not conform to the contract", reason="invalid_answer"
        ) from None
