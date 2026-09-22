"""Mandatory budget reservation and complete serialized-request admission."""

from dataclasses import dataclass

from .config import BudgetConfig
from .errors import ContractError, LayerAllocationError, PromptTooLarge, RequiredContextTooLarge
from .models import ChatRequest, freeze_sequence, integer_value
from .tokens import TokenCounter, TokenEstimate


@dataclass(frozen=True, slots=True)
class BudgetPlan:
    input_allowance: int
    required_estimate: TokenEstimate
    retrieval_tokens: int
    summary_tokens: int
    window_tokens: int
    window_turn_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        integer_value("input_allowance", self.input_allowance, minimum=1)
        if not isinstance(self.required_estimate, TokenEstimate):
            raise ContractError("Budget plan requires a token estimate")
        for name in ("retrieval_tokens", "summary_tokens", "window_tokens"):
            integer_value(name, getattr(self, name))
        ids = freeze_sequence(self, "window_turn_ids", str)
        if len(set(ids)) != len(ids) or any(not identifier.strip() for identifier in ids):
            raise ContractError("Window turn IDs must be unique and nonempty")
        allocated = (
            self.required_estimate.estimated_tokens
            + self.retrieval_tokens
            + self.summary_tokens
            + self.window_tokens
        )
        if allocated != self.input_allowance:
            raise ContractError("Budget allocations must equal the input allowance")

    def to_dict(self) -> dict:
        return {
            "input_allowance": self.input_allowance,
            "required": self.required_estimate.to_dict(),
            "retrieval_tokens": self.retrieval_tokens,
            "summary_tokens": self.summary_tokens,
            "window_tokens": self.window_tokens,
            "window_turn_ids": list(self.window_turn_ids),
        }


def plan_budget(
    *, required_request: ChatRequest, config: BudgetConfig, counter: TokenCounter
) -> BudgetPlan:
    """Reserve a caller-supplied mandatory request without dropping any content.

    The assembly layer must supply system, active pins, question and tool schemas.
    Layer allocations use calibrated token units and include incremental framing;
    they are not raw text-token limits. Assembly recounts the final whole request.
    """
    estimate = counter.count_request(required_request)
    allowance = config.input_allowance
    remaining = allowance - estimate.estimated_tokens
    if remaining < 0:
        raise RequiredContextTooLarge(
            "Required context exceeds the input allowance; "
            "reduce supplied content or raise the budget",
            required_tokens=estimate.estimated_tokens,
            input_allowance=allowance,
            overflow_tokens=-remaining,
        )
    reserve = config.retrieval_reserve + config.summary_reserve
    if reserve > remaining:
        raise LayerAllocationError(
            "Layer reserves exceed space remaining after required context",
            available_tokens=remaining,
            reserved_tokens=reserve,
        )
    return BudgetPlan(
        allowance, estimate, config.retrieval_reserve, config.summary_reserve, remaining - reserve
    )


def validate_request(
    *, request: ChatRequest, config: BudgetConfig, counter: TokenCounter
) -> TokenEstimate:
    """Recount an entire final request. Never infer safety from per-block sums."""
    estimate = counter.count_request(request)
    if estimate.estimated_tokens > config.input_allowance:
        raise PromptTooLarge(
            "Serialized request exceeds the estimated input allowance",
            estimated_tokens=estimate.estimated_tokens,
            input_allowance=config.input_allowance,
            overflow_tokens=estimate.estimated_tokens - config.input_allowance,
        )
    return estimate
