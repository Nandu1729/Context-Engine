"""Cooperative cancellation for bounded local work; not a preemptive deadline."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .errors import ContractError, WorkCancelled


@runtime_checkable
class Cancellation(Protocol):
    """Checked inside bounded engine loops; raises WorkCancelled to stop work."""

    def check(self) -> None: ...


def validate_cancellation(token: Cancellation | None) -> None:
    if token is not None and (
        not isinstance(token, Cancellation) or not callable(getattr(token, "check", None))
    ):
        raise ContractError("Expected a cooperative cancellation token")


def raise_if_cancelled(token: Cancellation | None) -> None:
    if token is not None:
        token.check()


@dataclass(frozen=True, slots=True)
class DeadlineCancellation:
    """Monotonic wall-clock cooperative deadline with an injectable clock."""

    deadline: float
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if type(self.deadline) not in (int, float) or not math.isfinite(self.deadline):
            raise ContractError("Deadline must be a finite number")
        if not callable(self.clock):
            raise ContractError("Deadline clock must be callable")

    def check(self) -> None:
        if self.clock() >= self.deadline:
            raise WorkCancelled("Work exceeded its cooperative deadline")
