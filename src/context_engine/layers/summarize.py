"""Reuse caller-supplied summaries with exact source lineage; no implicit model calls."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..context import ContextCarrier, LayerDiagnostic
from ..errors import ContextEngineError, ContractError, SummaryPolicyError
from ..models import (
    BlockKind,
    ContextBlock,
    Scope,
    SourceRef,
    Turn,
    aware_time,
    freeze_sequence,
    text_value,
)
from ..tokens import TokenCounter
from .common import fits_block, history_digest, plan_window, set_block


@dataclass(frozen=True)
class SummarySnapshot:
    scope: Scope
    content: str
    history_fingerprint: str
    covered_turn_ids: tuple[str, ...]
    sources: tuple[SourceRef, ...]
    policy_version: str
    created_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ContractError("Summary requires a scope")
        text_value("content", self.content, nonempty=False)
        text_value("history_fingerprint", self.history_fingerprint)
        text_value("policy_version", self.policy_version)
        ids = freeze_sequence(self, "covered_turn_ids", str)
        sources = freeze_sequence(self, "sources", SourceRef)
        if len(set(ids)) != len(ids) or any(not value.strip() for value in ids):
            raise ContractError("Summary turn IDs must be unique and nonempty")
        if any(source.scope != self.scope or source.turn_id not in ids for source in sources):
            raise ContractError("Summary source scope or turn mismatch")
        aware_time("created_at", self.created_at)
        if self.expires_at is not None:
            aware_time("expires_at", self.expires_at)
            if self.expires_at <= self.created_at:
                raise ContractError("Summary expiry must follow creation")

    @classmethod
    def from_history(
        cls,
        *,
        scope: Scope,
        content: str,
        history: tuple[Turn, ...],
        policy_version: str,
        created_at: datetime,
        expires_at: datetime | None = None,
    ) -> "SummarySnapshot":
        if any(turn.scope != scope for turn in history):
            raise ContractError("Summary history scope mismatch")
        sources = tuple(
            SourceRef(scope, t.turn_id, m.message_id, t.revision, 0, len(m.content), m.content_hash)
            for t in history
            for m in t.messages
            if m.content
        )
        return cls(
            scope,
            content,
            history_digest(history),
            tuple(t.turn_id for t in history),
            sources,
            policy_version,
            created_at,
            expires_at,
        )

    def matches(self, history: tuple[Turn, ...], scope: Scope, at: datetime) -> bool:
        aware_time("at", at)
        if (
            self.scope != scope
            or self.created_at > at
            or (self.expires_at is not None and at >= self.expires_at)
        ):
            return False
        if self.history_fingerprint != history_digest(history) or self.covered_turn_ids != tuple(
            t.turn_id for t in history
        ):
            return False
        turns = {t.turn_id: t for t in history}
        try:
            for source in self.sources:
                source.extract(turns[source.turn_id])
        except (KeyError, ContractError):
            return False
        return True


class SummaryPolicy(Protocol):
    def get_summary(
        self, history: tuple[Turn, ...], scope: Scope, at: datetime
    ) -> SummarySnapshot | None: ...


@dataclass(frozen=True)
class FrozenSummaryPolicy:
    snapshot: SummarySnapshot

    def get_summary(
        self, history: tuple[Turn, ...], scope: Scope, at: datetime
    ) -> SummarySnapshot | None:
        return self.snapshot if self.snapshot.matches(history, scope, at) else None


@dataclass(frozen=True)
class SummaryLayer:
    counter: TokenCounter
    policy: SummaryPolicy | None
    at: datetime

    def __post_init__(self) -> None:
        aware_time("at", self.at)

    def apply(self, context: ContextCarrier) -> ContextCarrier:
        planned = plan_window(context, self.counter)
        old = tuple(
            t for t in planned.original_turns if t.turn_id not in planned.plan.window_turn_ids
        )
        reason = "summary_disabled"
        block = ContextBlock(BlockKind.SUMMARY, "", text_tokens=0)
        if not old:
            reason = "no_old_history"
        elif self.policy is not None and planned.plan.summary_tokens == 0:
            reason = "zero_reserve"
        elif self.policy is not None:
            try:
                snapshot = self.policy.get_summary(old, planned.scope, self.at)
            except ContextEngineError:
                raise
            except Exception:
                raise SummaryPolicyError("Supplied summary policy failed") from None
            if snapshot is not None and not isinstance(snapshot, SummarySnapshot):
                raise SummaryPolicyError("Supplied summary policy returned an invalid snapshot")
            if snapshot is None or not snapshot.matches(old, planned.scope, self.at):
                reason = "summary_unavailable_or_stale"
            elif not snapshot.content:
                reason = "empty_summary"
            else:
                candidate = ContextBlock(
                    BlockKind.SUMMARY,
                    snapshot.content,
                    snapshot.sources,
                    prefix_stable=True,
                    text_tokens=self.counter.count_text(snapshot.content),
                )
                if fits_block(planned, candidate, planned.plan.summary_tokens, self.counter):
                    block, reason = candidate, "summary_reused"
                else:
                    reason = "summary_over_budget"
        return set_block(
            planned,
            block,
            LayerDiagnostic(
                "SUMMARIZE",
                reason,
                output_text_tokens=block.text_tokens,
            ),
        )
