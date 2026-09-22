"""Ground truth belongs in fixture validation, never inside the reusable layer inputs."""

import unicodedata

from ..errors import ContractError, SummaryLeakageError
from ..layers.summarize import FrozenSummaryPolicy, SummarySnapshot
from ..models import text_value


def validate_frozen_summary(
    snapshot: SummarySnapshot, forbidden_answers: tuple[str, ...]
) -> FrozenSummaryPolicy:
    """Conservative identifier/alias gate, including case/spacing/punctuation variants.

    Short aliases can cause false positives; fix the fixture rather than silently
    exempting answers. This does not detect semantic paraphrases of an answer.
    """

    def normalized(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())

    if not forbidden_answers:
        raise ContractError("Benchmark summary validation requires declared answer aliases")
    summary = normalized(snapshot.content)
    for answer in forbidden_answers:
        text_value("answer_alias", answer)
        value = normalized(answer)
        if not value:
            raise ContractError("Answer alias must contain letters or numbers")
        if value in summary:
            raise SummaryLeakageError("Frozen summary contains a declared answer alias")
    return FrozenSummaryPolicy(snapshot)
