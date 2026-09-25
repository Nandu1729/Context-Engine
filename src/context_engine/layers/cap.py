"""Deterministic code-point-safe head/tail compression of working messages."""

from dataclasses import dataclass, replace

from ..config import CapConfig
from ..context import ContextCarrier, LayerDiagnostic
from ..errors import CapBudgetError, LayerStateError
from ..tokens import TokenCounter
from ..work import Cancellation, raise_if_cancelled


def bounded_piece(
    text: str,
    allowance: int,
    counter: TokenCounter,
    *,
    tail: bool = False,
    cancellation: Cancellation | None = None,
) -> str:
    """Find a fitting prefix/suffix; never assume BPE counts are strictly monotone."""
    low, high = 0, len(text)
    best = ""
    while low <= high:
        raise_if_cancelled(cancellation)
        middle = (low + high) // 2
        candidate = text[len(text) - middle :] if tail else text[:middle]
        if counter.count_text(candidate) <= allowance:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best


@dataclass(frozen=True)
class CapLayer:
    counter: TokenCounter
    config: CapConfig = CapConfig()

    def cap_text(self, text: str, *, cancellation: Cancellation | None = None) -> str:
        raise_if_cancelled(cancellation)
        if self.counter.count_text(text) <= self.config.max_tokens:
            return text
        head = bounded_piece(text, self.config.head_tokens, self.counter, cancellation=cancellation)
        tail = bounded_piece(
            text, self.config.tail_tokens, self.counter, tail=True, cancellation=cancellation
        )
        # At least one original code point at both ends is required for a capped message.
        head, tail = head or text[:1], tail or text[-1:]
        while head and tail:
            raise_if_cancelled(cancellation)
            end = len(text) - len(tail)
            omitted = text[len(head) : end]
            marker = f"\n[... {self.counter.count_text(omitted)} tokens elided ...]\n"
            candidate = head + marker + tail
            if omitted and self.counter.count_text(candidate) <= self.config.max_tokens:
                return candidate
            if len(head) >= len(tail) and len(head) > 1:
                head = head[:-1]
            elif len(tail) > 1:
                tail = tail[1:]
            else:
                break
        raise CapBudgetError(
            "CAP allocation cannot fit a head, elision marker and tail",
            max_tokens=self.config.max_tokens,
        )

    def apply(self, context: ContextCarrier) -> ContextCarrier:
        if context.plan is not None:
            raise LayerStateError("CAP must run before budget planning")
        turns, changed = [], []
        before = after = 0
        for turn in context.original_turns:
            raise_if_cancelled(context.cancellation)
            messages = []
            for message in turn.messages:
                content = self.cap_text(message.content, cancellation=context.cancellation)
                before += self.counter.count_text(message.content)
                after += self.counter.count_text(content)
                messages.append(replace(message, content=content))
            working = replace(turn, messages=tuple(messages))
            turns.append(working)
            if working != turn:
                changed.append(turn.turn_id)
        return replace(
            context,
            working_turns=tuple(turns),
            diagnostics=context.diagnostics
            + (
                LayerDiagnostic(
                    "CAP",
                    "messages_capped" if changed else "unchanged",
                    tuple(changed),
                    before,
                    after,
                ),
            ),
        )
