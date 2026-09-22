"""C07 synthetic persistence, isolation, lifecycle and recovery qualification."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_providers import FakeTransport, client

from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.errors import ContractError, MemoryConflict, MemoryIntegrityError, StorageError
from context_engine.layers.common import history_digest
from context_engine.layers.retrieve import ChunkIndex
from context_engine.layers.summarize import SummarySnapshot
from context_engine.memory import MemoryStore
from context_engine.memory.codec import decode, digest
from context_engine.models import KeyedPins, Message, Pin, Role, Scope, SourceRef, Turn
from context_engine.pipeline import assemble_context
from context_engine.providers.contracts import ReplayPolicy
from context_engine.providers.memory import MemoryProvider
from context_engine.providers.store import RuntimeStore
from context_engine.tokens import TiktokenCounter

AT = datetime(2026, 9, 8, tzinfo=UTC)
SCOPE = Scope("synthetic-tenant", "session")
OTHER = Scope("other-tenant", "session")


@pytest.fixture
def memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    store.create_scope(SCOPE)
    return store


def turn(key="t1", *, content="PRIVATE_FACT shard-19", revision=1, scope=SCOPE):
    return Turn(key, scope, (Message("m-" + key, Role.USER, content),), revision, AT)


def put(memory, value=None, **options):
    value = value or turn()
    defaults = dict(
        operation_id=f"{value.turn_id}:{value.revision}",
        expected_revision=memory.snapshot(value.scope).revision,
    )
    defaults.update(options)
    return memory.put_turn(value, **defaults)


def derived(memory):
    current = memory.snapshot(SCOPE)
    original = current.history[0]
    msg = original.messages[0]
    source = SourceRef(
        SCOPE, original.turn_id, msg.message_id, 1, 0, len(msg.content), msg.content_hash
    )
    pin = Pin(SCOPE, "fact", "PRIVATE_FACT", "synthetic", source=source, effective_at=AT)
    memory.put_pin(pin, expected_revision=current.revision)
    snap = memory.snapshot(SCOPE)
    memory.put_summary(
        snap,
        SummarySnapshot.from_history(
            scope=SCOPE,
            content="PRIVATE_SUMMARY",
            history=snap.history,
            policy_version="synthetic-v1",
            created_at=AT,
        ),
    )
    snap = memory.snapshot(SCOPE)
    memory.index_batch(snap)
    memory.cache_put(snap, "answer", {"text": "PRIVATE_ANSWER"})
    return snap


def sql(path, statement, parameters=()):
    with closing(sqlite3.connect(path)) as db:
        result = db.execute(statement, parameters).fetchall()
        db.commit()
        return result


def test_restart_idempotency_and_explicit_export(memory):
    original = turn()
    assert put(memory, original) == 1
    assert put(memory, original, expected_revision=0) == 1
    reopened = MemoryStore(memory.path, clock=lambda: AT)
    snap = reopened.snapshot(SCOPE)
    assert snap.history == (original,) and snap.revision == 1
    assert "PRIVATE_FACT" not in str(snap.to_dict())
    assert "PRIVATE_FACT" in str(snap.to_dict(include_content=True))
    with pytest.raises(MemoryIntegrityError):
        snap.to_dict(include_content="yes")
    with pytest.raises(MemoryConflict):
        put(memory, turn(content="different"))


def test_turn_update_order_and_revision_guards(memory):
    put(memory)
    put(memory, turn("t2"))
    with pytest.raises(MemoryConflict):
        put(memory, turn(revision=3))
    with pytest.raises(MemoryConflict):
        put(memory, turn(revision=2), expected_revision=0)
    put(memory, turn(revision=2, content="revised"))
    assert [t.turn_id for t in memory.snapshot(SCOPE).history] == ["t1", "t2"]
    assert memory.snapshot(SCOPE).history[0].messages[0].content == "revised"


def test_scope_isolation(memory):
    memory.create_scope(OTHER)
    put(memory)
    put(memory, turn(scope=OTHER, content="OTHER_FACT"))
    a, b = memory.snapshot(SCOPE), memory.snapshot(OTHER)
    memory.cache_put(a, "same", {"text": "A"})
    memory.cache_put(b, "same", {"text": "B"})
    assert memory.cache_get(a, "same")["text"] == "A"
    memory.delete(SCOPE, kind="scope", expected_revision=a.revision)
    assert memory.cache_get(b, "same")["text"] == "B"
    assert memory.snapshot(OTHER).history[0].messages[0].content == "OTHER_FACT"
    with pytest.raises(MemoryConflict):
        memory.create_scope(SCOPE)
    with pytest.raises(MemoryIntegrityError):
        memory.snapshot("tenant")


def test_competing_pin_updates_have_exactly_one_winner(memory):
    pin = Pin(SCOPE, "db", "initial", "synthetic", effective_at=AT)
    memory.put_pin(pin, expected_revision=0)

    def update(value):
        try:
            return memory.put_pin(replace(pin, value=value, revision=2), expected_revision=1)
        except MemoryConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ("first", "second")))
    assert sorted(map(str, results)) == ["2", "conflict"]


@pytest.mark.parametrize("change", ["update", "delete", "expire"])
def test_source_changes_invalidate_all_derived_data(memory, change):
    put(memory, expires_at=AT + timedelta(seconds=10) if change == "expire" else None)
    old = derived(memory)
    if change == "update":
        put(memory, turn(revision=2, content="NEW_FACT"))
    elif change == "delete":
        memory.delete(SCOPE, kind="turn", key="t1", expected_revision=old.revision)
    else:
        memory.clock = lambda: AT + timedelta(seconds=10)
        memory.prune()
    current = memory.snapshot(SCOPE)
    assert not current.pins.pins and current.summary is None
    assert memory.cache_get(current, "answer") is None
    assert sql(memory.path, "SELECT count(*) FROM chunks")[0][0] == 0
    with pytest.raises(MemoryConflict):
        memory.assert_current(old)
    with pytest.raises(MemoryConflict):
        memory.put_pin(old.pins.pins[0], expected_revision=current.revision)
    if change != "update":
        with pytest.raises(MemoryConflict):
            put(memory, operation_id="new-operation")


def test_summary_restart_reuse_and_wrong_lineage(memory):
    put(memory)
    snap = derived(memory)
    assert MemoryStore(memory.path, clock=lambda: AT).snapshot(SCOPE) == snap
    with pytest.raises(MemoryConflict):
        memory.put_summary(snap, replace(snap.summary, history_fingerprint="wrong"))
    memory.clock = lambda: AT + timedelta(seconds=1)
    summary = replace(snap.summary, expires_at=AT + timedelta(seconds=2))
    memory.put_summary(snap, summary)
    memory.clock = lambda: AT + timedelta(seconds=2)
    assert memory.snapshot(SCOPE).summary is None


def test_pin_activation_and_expiry_change_snapshot(memory):
    pin = Pin(
        SCOPE,
        "future",
        "value",
        "synthetic",
        effective_at=AT + timedelta(seconds=1),
        expires_at=AT + timedelta(seconds=2),
    )
    memory.put_pin(pin, expected_revision=0)
    old = memory.snapshot(SCOPE)
    assert not old.pins.pins
    memory.clock = lambda: AT + timedelta(seconds=1)
    active = memory.snapshot(SCOPE)
    assert active.pins.pins and active.snapshot_id != old.snapshot_id
    memory.clock = lambda: AT + timedelta(seconds=2)
    assert not memory.snapshot(SCOPE).pins.pins


def test_index_resume_and_incremental_reuse(memory, monkeypatch):
    for i in range(3):
        put(memory, turn(str(i)))
    snap = memory.snapshot(SCOPE)
    assert memory.index_batch(snap, batch_size=1)["remaining"] == 2
    memory = MemoryStore(memory.path, clock=lambda: AT)
    with pytest.raises(MemoryConflict):
        memory.chunk_index(snap)
    assert memory.index_batch(snap, batch_size=1)["remaining"] == 1
    assert memory.index_batch(snap)["status"] == "READY"
    before = memory.chunk_index(snap)
    import context_engine.memory.store as module

    original = module.chunk_turns
    calls = []

    def counted(turns, config):
        calls.extend(t.turn_id for t in turns)
        return original(turns, config)

    monkeypatch.setattr(module, "chunk_turns", counted)
    assert memory.index_batch(snap)["processed"] == 0
    put(memory, turn("1", revision=2, content="changed"))
    snap = memory.snapshot(SCOPE)
    assert memory.index_batch(snap)["processed"] == 1 and calls == ["1"]
    after = memory.chunk_index(snap)
    assert before.chunks[0] == after.chunks[0]
    config = RetrievalConfig(chunk_characters=400, overlap_characters=40)
    assert memory.index_batch(snap, config)["processed"] == 3
    with pytest.raises(MemoryConflict):
        memory.chunk_index(snap)
    memory.chunk_index(snap, config).validate(snap.history, config)


def test_persisted_assembly_matches_core(memory):
    for i in range(8):
        put(memory, turn(str(i), content=("shard-19 incident " if i == 0 else "routine ") * 80))
    snap = memory.snapshot(SCOPE)
    budget = BudgetConfig(input_cap=900)
    normal = assemble_context(
        snap.history, "Which shard?", KeyedPins(SCOPE), budget, system="Use evidence.", at=AT
    )
    _, persisted = memory.assemble(SCOPE, "Which shard?", budget, system="Use evidence.")
    assert persisted.request == normal.request
    assert persisted.diagnostics.estimate == normal.diagnostics.estimate


@pytest.mark.parametrize("table", ["turns", "pins", "summaries", "replay", "chunks"])
def test_corrupt_payloads_fail_closed(memory, table):
    put(memory)
    snap = derived(memory)
    sql(memory.path, f"UPDATE {table} SET payload='{{}}'")
    with pytest.raises(MemoryIntegrityError):
        if table == "replay":
            memory.cache_get(snap, "answer")
        elif table == "chunks":
            memory.chunk_index(snap)
        else:
            memory.snapshot(SCOPE)


def test_index_missing_chunk_and_malformed_direct_index(memory):
    put(memory)
    snap = memory.snapshot(SCOPE)
    memory.index_batch(snap)
    sql(memory.path, "DELETE FROM chunks")
    with pytest.raises(MemoryIntegrityError):
        memory.chunk_index(snap)
    bad = ChunkIndex(history_digest(snap.history), digest(RetrievalConfig()), (None,))
    with pytest.raises(MemoryIntegrityError):
        bad.validate(snap.history, RetrievalConfig())


def test_replay_expiry_and_clock_rollback(memory):
    snap = memory.snapshot(SCOPE)
    memory.cache_put(snap, "key", {"text": "answer"}, ttl_seconds=1)
    memory.clock = lambda: AT + timedelta(seconds=1)
    assert memory.cache_get(snap, "key") is None
    memory.clock = lambda: AT
    with pytest.raises(MemoryConflict, match="backwards"):
        memory.snapshot(SCOPE)


@pytest.mark.parametrize("kind", ["turn", "scope"])
def test_old_backup_restore_never_revives_deleted_data(memory, tmp_path, kind):
    put(memory)
    old = derived(memory)
    backup = memory.backup(tmp_path / "old.sqlite")
    memory.delete(
        SCOPE, kind=kind, key="t1" if kind == "turn" else "", expected_revision=old.revision
    )
    watermark = memory.deletion_watermark()["minimum_deletion_seq"]
    restored = MemoryStore.restore(
        backup,
        tmp_path / "restored.sqlite",
        deletion_path=memory.deletion_path,
        minimum_deletion_seq=watermark,
        clock=lambda: AT,
    )
    for table in ("turns", "pins", "summaries", "chunks", "replay"):
        assert sql(restored.path, f"SELECT count(*) FROM {table}")[0][0] == 0
    if kind == "turn":
        assert not restored.snapshot(SCOPE).history
    else:
        with pytest.raises(MemoryConflict):
            restored.snapshot(SCOPE)
    assert "PRIVATE_FACT" not in str(sql(memory.deletion_path, "SELECT * FROM events"))
    with pytest.raises(MemoryConflict):
        restored.assert_current(old)


def test_restore_rotates_epoch_and_preserves_originals(memory, tmp_path):
    put(memory)
    old = derived(memory)
    backup = memory.backup(tmp_path / "backup ?#.sqlite")
    restored = MemoryStore.restore(
        backup,
        tmp_path / "restored.sqlite",
        deletion_path=memory.deletion_path,
        minimum_deletion_seq=0,
        clock=lambda: AT,
    )
    new = restored.snapshot(SCOPE)
    assert new.history == old.history and new.pins == old.pins
    assert new.snapshot_id != old.snapshot_id and new.summary is None
    assert restored.cache_get(new, "answer") is None


@pytest.mark.parametrize("problem", ["missing", "wrong", "stale", "holes", "metadata"])
def test_restore_rejects_bad_authority_before_copy(memory, tmp_path, problem):
    put(memory)
    backup = memory.backup(tmp_path / "backup.sqlite")
    authority = memory.deletion_path
    minimum = 0
    if problem == "missing":
        authority = tmp_path / "absent.sqlite"
    elif problem == "wrong":
        authority = MemoryStore(tmp_path / "other.sqlite", clock=lambda: AT).deletion_path
    elif problem == "stale":
        minimum = 1
    elif problem == "holes":
        sql(authority, "INSERT INTO events VALUES(2,'s','turn','t')")
    else:
        sql(backup, "DELETE FROM meta")
    dest = tmp_path / "restored.sqlite"
    with pytest.raises((MemoryIntegrityError, StorageError)):
        MemoryStore.restore(
            backup, dest, deletion_path=authority, minimum_deletion_seq=minimum, clock=lambda: AT
        )
    assert not dest.exists()


def test_delete_atomic_rollback_and_duplicate_watermark(memory, monkeypatch):
    put(memory)
    original = memory._erase

    def failed(*args):
        original(*args)
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(memory, "_erase", failed)
    with pytest.raises(RuntimeError):
        memory.delete(SCOPE, kind="turn", key="t1", expected_revision=1)
    assert memory.snapshot(SCOPE).history
    assert memory.deletion_watermark()["minimum_deletion_seq"] == 0
    monkeypatch.setattr(memory, "_erase", original)
    memory.delete(SCOPE, kind="turn", key="t1", expected_revision=1)
    memory.delete(SCOPE, kind="turn", key="t1", expected_revision=2)
    assert memory.deletion_watermark()["minimum_deletion_seq"] == 1


def test_existing_store_detects_rolled_back_authority(memory):
    put(memory)
    memory.delete(SCOPE, kind="turn", key="t1", expected_revision=1)
    sql(memory.deletion_path, "DELETE FROM events")
    with pytest.raises(MemoryIntegrityError):
        memory.snapshot(SCOPE)


@pytest.mark.parametrize("problem", ["public", "symlink", "schema", "wal", "absent_ledger"])
def test_private_schema_and_journal_boundaries(memory, tmp_path, problem):
    path = memory.path
    if problem == "public":
        path.chmod(0o644)
    elif problem == "symlink":
        path = tmp_path / "link.sqlite"
        path.symlink_to(memory.path)
    elif problem == "schema":
        sql(path, "PRAGMA user_version=999")
    elif problem == "wal":
        sql(path, "PRAGMA journal_mode=WAL")
    else:
        memory.deletion_path.rename(tmp_path / "retained-ledger.sqlite")
    with pytest.raises(StorageError):
        MemoryStore(path, clock=lambda: AT)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', "[]", '"x"', "{"])
def test_bounded_strict_codec(raw):
    with pytest.raises(MemoryIntegrityError):
        decode(raw)


@pytest.mark.parametrize("batch", [0, -1, 257, True])
def test_index_batch_bounds(memory, batch):
    with pytest.raises((ContractError, MemoryIntegrityError)):
        memory.index_batch(memory.snapshot(SCOPE), batch_size=batch)


def test_payload_and_revision_bounds(memory):
    with pytest.raises(MemoryIntegrityError):
        put(memory, turn(content="x" * 1_000_001))
    with pytest.raises(ContractError):
        put(memory, expected_revision=-1)
    with pytest.raises(MemoryIntegrityError):
        memory.cache_put(memory.snapshot(SCOPE), "key", {"x": "x"}, ttl_seconds=86401)


def test_memory_provider_replay_and_invalidation(memory, tmp_path):
    provider = client(RuntimeStore(tmp_path / "provider.sqlite"), TiktokenCounter())
    bridge = MemoryProvider(memory, provider, replay=True)

    def run():
        return asyncio.run(
            bridge.complete(
                SCOPE,
                "Which shard?",
                BudgetConfig(input_cap=900),
                system="Use evidence.",
                security_scope="principal",
            )
        )

    put(memory)
    first, replay = run(), run()
    assert first.status == "success" and replay.status == "replay"
    assert replay.new_cost_microusd == 0 and len(provider.transport.calls) == 1
    assert (
        sql(provider.store.path, "SELECT count(*) FROM events WHERE kind='memory_replay'")[0][0]
        == 1
    )
    memory.delete(SCOPE, kind="turn", key="t1", expected_revision=1)
    assert run().status == "success" and len(provider.transport.calls) == 2
    assert "PRIVATE_FACT" not in str(provider.transport.calls[-1])
    assert "PRIVATE_ANSWER" not in str(sql(provider.store.path, "SELECT * FROM attempts"))


def test_memory_provider_discards_inflight_deleted_response(memory, tmp_path):
    put(memory)
    transport = FakeTransport()
    completion = transport.actions[0]

    async def deletion_during_call():
        memory.delete(SCOPE, kind="scope", expected_revision=1)
        return completion

    transport.actions = [deletion_during_call]
    provider = client(
        RuntimeStore(tmp_path / "provider.sqlite"), TiktokenCounter(), transport=transport
    )
    result = asyncio.run(
        MemoryProvider(memory, provider, replay=True).complete(
            SCOPE,
            "Which shard?",
            BudgetConfig(input_cap=900),
            system="Use evidence.",
            security_scope="principal",
        )
    )
    assert result.error_code == "memory_revision_conflict" and result.completion is None
    assert result.new_cost_microusd > 0
    assert sql(memory.path, "SELECT count(*) FROM replay")[0][0] == 0


def test_memory_provider_rejects_unmanaged_body_cache(memory, tmp_path):
    provider = client(
        RuntimeStore(tmp_path / "provider.sqlite"),
        TiktokenCounter(),
        replay=ReplayPolicy(enabled=True),
    )
    with pytest.raises(ContractError):
        MemoryProvider(memory, provider)


def test_memory_demo_cli_no_content_or_overwrite(tmp_path, capsys):
    import json

    from context_engine.cli import main

    path = tmp_path / "result.json"
    assert main(["memory-demo", "--output", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PASS" and all(result["checks"].values())
    assert result["inference_calls"] == 0
    before = path.read_bytes()
    assert main(["memory-demo", "--output", str(path)]) == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("table,assignment", [("turns", "key='wrong'"), ("pins", "revision=99")])
def test_persisted_identity_tampering_is_rejected(memory, table, assignment):
    put(memory)
    derived(memory)
    sql(memory.path, f"UPDATE {table} SET {assignment}")
    with pytest.raises(MemoryIntegrityError):
        memory.snapshot(SCOPE)


def test_deleted_ingestion_receipt_does_not_resurrect_original(memory):
    put(memory)
    memory.delete(SCOPE, kind="turn", key="t1", expected_revision=1)
    assert put(memory, expected_revision=0) == 1  # Original successful receipt, not a new write.
    assert memory.snapshot(SCOPE).history == ()


def test_expired_source_cannot_return_through_old_backup(memory, tmp_path):
    put(memory, expires_at=AT + timedelta(seconds=1))
    derived(memory)
    backup = memory.backup(tmp_path / "backup.sqlite")
    memory.clock = lambda: AT + timedelta(seconds=1)
    watermark = memory.prune()["minimum_deletion_seq"]
    restored = MemoryStore.restore(
        backup,
        tmp_path / "restored.sqlite",
        deletion_path=memory.deletion_path,
        minimum_deletion_seq=watermark,
        clock=memory.clock,
    )
    snap = restored.snapshot(SCOPE)
    assert snap.history == () and not snap.pins.pins and snap.summary is None
    assert restored.cache_get(snap, "answer") is None


def test_backup_and_restore_refuse_overwrite(memory, tmp_path):
    backup = memory.backup(tmp_path / "backup.sqlite")
    before = backup.read_bytes()
    with pytest.raises(StorageError):
        memory.backup(backup)
    with pytest.raises(StorageError):
        MemoryStore.restore(
            backup,
            backup,
            deletion_path=memory.deletion_path,
            minimum_deletion_seq=0,
            clock=lambda: AT,
        )
    assert backup.read_bytes() == before
