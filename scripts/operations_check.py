"""Bounded synthetic recovery/profile drill; never opens project stores or providers."""

import argparse
import hashlib
import json
import math
import os
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from context_engine.config import BudgetConfig
from context_engine.evaluation.protocol import runtime_identity
from context_engine.memory import MemoryStore
from context_engine.models import Message, Role, Scope, Turn


def timed(call):
    start = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - start) * 1000


def drill(*, turns=100, samples=20):
    if type(turns) is not int or not 2 <= turns <= 1000:
        raise ValueError("turns must be2..1000")
    if type(samples) is not int or not 2 <= samples <= 100:
        raise ValueError("samples must be2..100")
    at = datetime.now(UTC)
    scope = Scope("synthetic-operations", "recovery")
    with TemporaryDirectory(prefix="context-operations-") as directory:
        root = Path(directory)
        store = MemoryStore(root / "memory.sqlite", clock=lambda: at)
        store.create_scope(scope)
        for i in range(turns):
            fact = "Retired marker DELETE-ME." if i == 0 else f"Routine record {i}."
            turn = Turn(f"t{i}", scope, (Message(f"m{i}", Role.USER, fact),), timestamp=at)
            store.put_turn(turn, operation_id=f"op{i}", expected_revision=i)
        before = store.snapshot(scope)

        def build(memory, snapshot):
            total = 0
            while True:
                batch = memory.index_batch(snapshot, batch_size=32)
                total += batch["processed"]
                if batch["remaining"] == 0:
                    return total

        cold, cold_ms = timed(lambda: build(store, before))
        chunks = store.chunk_index(before)
        reused, reuse_ms = timed(lambda: store.index_batch(before))
        index_equal = store.chunk_index(before) == chunks
        store.cache_put(before, "synthetic-answer", {"value": "DELETE-ME"})
        cache_hit = store.cache_get(before, "synthetic-answer") == {"value": "DELETE-ME"}
        budget = BudgetConfig(input_cap=900)

        def assemble():
            return store.assemble(
                scope, "What is the retired marker?", budget, system="Use evidence."
            )

        _, warmup_ms = timed(assemble)
        durations = []
        fingerprints = []
        for _ in range(samples):
            (_, result), duration = timed(assemble)
            durations.append(duration)
            fingerprints.append(result.diagnostics.estimate.request_fingerprint)
        backup, backup_ms = timed(lambda: store.backup(root / "backup.sqlite"))
        store.delete(scope, kind="turn", key="t0", expected_revision=before.revision)
        live = store.snapshot(scope)
        watermark = store.deletion_watermark()["minimum_deletion_seq"]

        def restore(name):
            recovered = MemoryStore.restore(
                backup, root / name, deletion_path=store.deletion_path,
                minimum_deletion_seq=watermark, clock=lambda: at,
            )
            snap = recovered.snapshot(scope)
            rebuilt = build(recovered, snap)
            clean, context = recovered.assemble(
                scope, "What is the retired marker?", budget, system="Use evidence."
            )
            return recovered, clean, context, rebuilt

        (restored, clean, context, rebuilt), restore_ms = timed(lambda: restore("restore.sqlite"))
        # Same-version second isolated restore; NOT an application deployment rollback.
        (_, rollback, _, _), rehearsal_ms = timed(lambda: restore("rehearsal.sqlite"))
        checks = {
            "all_turns_indexed": cold == turns,
            "unchanged_index_reused": reused["processed"] == 0 and index_equal,
            "synthetic_cache_hit": cache_hit,
            "stable_assembly": len(set(fingerprints)) == 1,
            "surviving_history_preserved": clean.history == live.history,
            "deleted_turn_absent": all(t.turn_id != "t0" for t in clean.history),
            "deleted_marker_absent": "DELETE-ME" not in json.dumps(context.request.to_wire()),
            "old_replay_invalidated": restored.cache_get(clean, "synthetic-answer") is None,
            "restore_epoch_rotated": clean.snapshot_id != before.snapshot_id,
            "index_rebuilt": rebuilt == turns - 1,
            "repeat_restore_preserves_history": rollback.history == clean.history,
        }
        if not all(checks.values()):
            raise RuntimeError("Synthetic operations drill failed")
        ordered = sorted(durations)
        return {
            "status": "LOCAL_SYNTHETIC_PASS", "production_qualified": False,
            "inference_calls": 0, "content_included": False, "runtime": runtime_identity(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "host": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "logical_cpus": os.cpu_count()},
            "workload": {"turns": turns, "samples": samples, "concurrency": 1,
                         "input_cap": 900, "summary_generation": False},
            "checks": checks,
            "milliseconds": {
                "index_cold": cold_ms, "index_unchanged": reuse_ms, "warmup": warmup_ms,
                "assembly_samples": durations, "assembly_p50": ordered[(samples - 1) // 2],
                "assembly_p95": ordered[math.ceil(samples * .95) - 1],
                "backup": backup_ms, "restore_reindex_assemble": restore_ms,
                "second_restore_rehearsal": rehearsal_ms,
            },
            "index_work": {"cold_processed": cold, "unchanged_processed": reused["processed"],
                           "restored_processed": rebuilt},
            "storage_bytes": sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
            "caveats": ["Single local process,not sustained service load or an approved SLO.",
                        "Existing index reuse measured;no before/after code optimization.",
                        "No provider,summary-generation or production cost savings measured.",
                        "Latest same-host deletion authority,not offsite disaster recovery.",
                        "No cross-version migration or deployment rollback proven."],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turns", type=int, default=100)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    # Refuse existing outputs before spending time; exclusive create also closes race.
    if args.output.exists() or args.output.is_symlink():
        parser.error("Output must not already exist")
    report = drill(turns=args.turns, samples=args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]),
                      "inference_calls": 0}))


if __name__ == "__main__":
    main()
