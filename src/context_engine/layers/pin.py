"""Reserve supplied instructions, active keyed facts, the question and tool schemas."""

from dataclasses import dataclass, replace
from datetime import datetime

from ..budget import plan_budget
from ..config import BudgetConfig
from ..context import ContextCarrier, LayerDiagnostic
from ..models import BlockKind, ContextBlock, ToolDefinition, aware_time, canonical_json, text_value
from ..tokens import TokenCounter
from .common import input_digest, render_request


@dataclass(frozen=True)
class PinLayer:
    counter: TokenCounter
    budget: BudgetConfig
    system: str
    at: datetime
    tools: tuple[ToolDefinition, ...] = ()

    def __post_init__(self) -> None:
        text_value("system", self.system)
        aware_time("at", self.at)
        object.__setattr__(self, "tools", tuple(self.tools))

    def apply(self, context: ContextCarrier) -> ContextCarrier:
        active = tuple(pin for pin in context.pins.pins if pin.is_active(self.at))
        content = (
            canonical_json([{"key": pin.key, "value": pin.value} for pin in active])
            if active
            else ""
        )
        blocks = (
            ContextBlock(
                BlockKind.SYSTEM,
                self.system,
                prefix_stable=True,
                text_tokens=self.counter.count_text(self.system),
            ),
            ContextBlock(
                BlockKind.PINNED,
                content,
                sources=tuple(pin.source for pin in active if pin.source is not None),
                prefix_stable=True,
                text_tokens=self.counter.count_text(content),
            ),
        )
        request = render_request(blocks, context.question, self.tools)
        plan = plan_budget(required_request=request, config=self.budget, counter=self.counter)
        # Re-running PIN deliberately invalidates all query-dependent layer outputs.
        return replace(
            context,
            plan=plan,
            blocks=blocks,
            required_request=request,
            prepared_fingerprint=input_digest(context),
            window_planned=False,
            retrieved_chunks=(),
            diagnostics=context.diagnostics
            + (
                LayerDiagnostic(
                    "PIN",
                    "required_context_reserved",
                    output_text_tokens=sum(b.text_tokens for b in blocks),
                ),
            ),
        )
