"""0.17's retrieval defaults, for tests that compare historical scripts relying on them."""

import functools
from dataclasses import replace

from context_engine.config import RetrievalConfig

RESERVE, TOP_K = 280, 4


def with_0_17_defaults(assemble):
    """Wrap `assemble_context`: automatic reserve -> 280, automatic top_k -> 4, and turn
    diversity off unless given. Explicit values pass through unchanged."""

    @functools.wraps(assemble)
    def wrapped(history, question, pins, budget, **kwargs):
        if budget.retrieval_reserve is None:
            budget = replace(budget, retrieval_reserve=RESERVE)
        config = kwargs.get("retrieval_config") or RetrievalConfig()
        if config.top_k is None:
            config = replace(config, top_k=TOP_K)
        kwargs["retrieval_config"] = config
        kwargs.setdefault("diverse_turns", False)
        return assemble(history, question, pins, budget, **kwargs)

    return wrapped
