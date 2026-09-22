"""Synthetic lifecycle demonstration; temporary private stores, zero inference."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ..config import BudgetConfig
from ..errors import MemoryIntegrityError
from ..models import Message, Pin, Role, Scope, SourceRef, Turn
from .store import MemoryStore


def memory_demo():
    at = datetime(2026, 9, 8, tzinfo=UTC)
    scope = Scope("synthetic-demo", "incident")
    with TemporaryDirectory(prefix="context-memory-demo-") as directory:
        root = Path(directory)
        memory = MemoryStore(root / "memory.sqlite", clock=lambda: at)
        memory.create_scope(scope)
        for i in range(12):
            content = (
                "routine telemetry. " * 60
                + "The partition carrying the blame was shard-19. "
                + "routine telemetry. " * 60
                if i == 0
                else f"Recent update {i}. " + "routine checks continue. " * 40
            )
            turn = Turn(f"t{i}", scope, (Message(f"m{i}", Role.USER, content),), timestamp=at)
            memory.put_turn(turn, operation_id=f"ingest-{i}", expected_revision=i)
        original = memory.snapshot(scope)
        started = memory.index_batch(original, batch_size=3)
        memory = MemoryStore(memory.path, clock=lambda: at)
        restarted = memory.snapshot(scope)
        resumed = memory.index_batch(restarted)
        unchanged = memory.index_batch(restarted)
        budget = BudgetConfig(input_cap=900, retrieval_reserve=280, summary_reserve=80)
        _, context = memory.assemble(
            scope, "Which partition carried the blame?", budget, system="Use the evidence."
        )
        first = original.history[0]
        msg = first.messages[0]
        source = SourceRef(
            scope, first.turn_id, msg.message_id, 1, 0, len(msg.content), msg.content_hash
        )
        pin = Pin(scope, "partition", "shard-19", "synthetic", source=source, effective_at=at)
        memory.put_pin(pin, expected_revision=restarted.revision)
        revised = memory.put_pin(
            replace(pin, revision=2), expected_revision=memory.snapshot(scope).revision
        )
        snap = memory.snapshot(scope)
        memory.cache_put(snap, "answer", {"text": "shard-19"})
        backup = memory.backup(root / "backup.sqlite")
        memory.delete(scope, kind="turn", key=first.turn_id, expected_revision=revised)
        watermark = memory.deletion_watermark()["minimum_deletion_seq"]
        restored = MemoryStore.restore(
            backup,
            root / "restored.sqlite",
            deletion_path=memory.deletion_path,
            minimum_deletion_seq=watermark,
            clock=lambda: at,
        )
        clean, after = restored.assemble(
            scope, "Which partition carried the blame?", budget, system="Use the evidence."
        )
        checks = {
            "restart_preserves_originals": original == restarted,
            "interrupted_index_resumes": started["remaining"] == 9 and resumed["processed"] == 9,
            "unchanged_chunks_reused": unchanged["processed"] == 0,
            "original_fact_retrieved": "t0" in context.diagnostics.retrieved_turn_ids,
            "pin_revision_applied": snap.pins.pins[0].revision == 2,
            "deleted_turn_not_restored": "t0" not in [t.turn_id for t in clean.history],
            "derived_pin_not_restored": not clean.pins.pins,
            "replay_not_restored": restored.cache_get(clean, "answer") is None,
            "deleted_fact_absent_from_context": "shard-19" not in str(after.request.to_wire()),
        }
        if not all(checks.values()):
            raise MemoryIntegrityError("Synthetic memory lifecycle check failed")
        return {
            "status": "PASS",
            "synthetic": True,
            "inference_calls": 0,
            "schema_version": 1,
            "ingested_turns": len(original.history),
            "remaining_turns_after_restore": len(clean.history),
            "estimated_request_tokens": context.diagnostics.estimate.estimated_tokens,
            "checks": checks,
            "content_included": False,
        }
