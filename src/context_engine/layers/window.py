"""Select the contiguous recent suffix from the exact shared lookahead plan."""

from dataclasses import dataclass

from ..context import ContextCarrier, LayerDiagnostic
from ..errors import LayerStateError
from ..tokens import TokenCounter
from .common import fits_block, plan_window, set_block, window_block


@dataclass(frozen=True)
class WindowLayer:
    counter: TokenCounter

    def apply(self, context: ContextCarrier) -> ContextCarrier:
        planned = plan_window(context, self.counter)
        block = window_block(planned, planned.plan.window_turn_ids, self.counter)
        if not fits_block(planned, block, planned.plan.window_tokens, self.counter):
            raise LayerStateError("Planned WINDOW no longer fits; rebuild context")
        return set_block(
            planned,
            block,
            LayerDiagnostic(
                "WINDOW",
                "recent_suffix_selected" if block.content else "empty_window",
                planned.plan.window_turn_ids,
                output_text_tokens=block.text_tokens,
            ),
        )
