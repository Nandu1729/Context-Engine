"""Scoped transactional memory, resumable chunk indexes and deletion-aware local recovery."""

import os
import sqlite3
import stat
import time
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..config import RetrievalConfig
from ..errors import MemoryConflict, MemoryIntegrityError, StorageError
from ..layers.common import history_digest
from ..layers.retrieve import ChunkIndex, chunk_turns
from ..layers.summarize import FrozenSummaryPolicy, SummarySnapshot
from ..models import ChatRequest, KeyedPins, Pin, Scope, Turn, aware_time, integer_value, text_value
from ..pipeline import assemble_context
from .codec import decode, digest, encode, plain, unpack

MAX_TURNS, MAX_BYTES, MAX_CHUNKS = 10000, 8_000_000, 100000


def private_file(path, *, create=False, exclusive=False):
    try:
        path = Path(path).absolute()
        if create:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if create:
            flags |= os.O_CREAT
        if exclusive:
            flags |= os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and info.st_mode & 0o077):
                raise StorageError("Memory files must be private regular files")
        finally:
            os.close(descriptor)
        return path
    except (OSError, ValueError, TypeError):
        raise StorageError("Cannot open private memory file") from None


@dataclass(frozen=True)
class MemorySnapshot:
    scope: Scope
    revision: int
    snapshot_id: str
    history: tuple[Turn, ...]
    pins: KeyedPins
    summary: SummarySnapshot | None
    at: datetime

    def to_dict(self, *, include_content=False):
        if type(include_content) is not bool:
            raise MemoryIntegrityError("Explicit content export must be boolean")
        result = {
            "scope": plain(self.scope),
            "revision": self.revision,
            "snapshot_id": self.snapshot_id,
            "turns": len(self.history),
            "pins": len(self.pins.pins),
            "summary_available": self.summary is not None,
            "content_included": include_content,
        }
        if include_content:
            result.update(
                history=plain(self.history),
                pinned_facts=plain(self.pins),
                summary=plain(self.summary),
            )
        return result


class MemoryStore:
    def __init__(self, path, *, deletion_path=None, clock=None):
        self.clock = clock or (lambda: datetime.now(UTC))
        path = Path(path).absolute()
        deletion_path = (
            Path(deletion_path).absolute()
            if deletion_path
            else path.with_suffix(".deletions.sqlite")
        )
        if path == deletion_path:
            raise StorageError("Memory and deletion authority require distinct files")
        creating = not path.exists()
        if creating and deletion_path.exists():
            raise StorageError("Existing deletion authority requires explicit restore")
        self.path = private_file(path, create=creating, exclusive=creating)
        self.deletion_path = private_file(deletion_path, create=creating, exclusive=creating)
        with self._transaction() as db:
            version = db.execute("PRAGMA main.user_version").fetchone()[0]
            dv = db.execute("PRAGMA deletions.user_version").fetchone()[0]
            if creating:
                lineage = uuid.uuid4().hex
                db.execute(
                    "CREATE TABLE meta(lineage TEXT, epoch TEXT, applied INTEGER, last_clock REAL)"
                )
                db.execute("INSERT INTO meta VALUES(?,?,0,0)", (lineage, uuid.uuid4().hex))
                db.execute("CREATE TABLE deletions.authority(lineage TEXT)")
                db.execute("INSERT INTO deletions.authority VALUES(?)", (lineage,))
                db.execute(
                    "CREATE TABLE deletions.events(seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "scope TEXT, kind TEXT, key TEXT, UNIQUE(scope,kind,key))"
                )
                for sql in (
                    "CREATE TABLE scopes(scope TEXT PRIMARY KEY, revision INTEGER, "
                    "deleted INTEGER DEFAULT 0)",
                    "CREATE TABLE turns(scope TEXT, key TEXT, position INTEGER, revision INTEGER, "
                    "payload TEXT, digest TEXT, expires REAL, PRIMARY KEY(scope,key))",
                    "CREATE TABLE pins(scope TEXT, key TEXT, revision INTEGER, payload TEXT, "
                    "digest TEXT, expires REAL, PRIMARY KEY(scope,key))",
                    "CREATE TABLE summaries(scope TEXT PRIMARY KEY, payload TEXT, "
                    "digest TEXT, expires REAL)",
                    "CREATE TABLE operations(scope TEXT, key TEXT, digest TEXT, "
                    "result INTEGER, PRIMARY KEY(scope,key))",
                    "CREATE TABLE chunks(scope TEXT, profile TEXT, turn_id TEXT, key TEXT, "
                    "payload TEXT, PRIMARY KEY(scope,profile,key))",
                    "CREATE TABLE coverage(scope TEXT, profile TEXT, turn_id TEXT, "
                    "source_hash TEXT, chunks_hash TEXT, PRIMARY KEY(scope,profile,turn_id))",
                    "CREATE TABLE replay(scope TEXT, key TEXT, snapshot TEXT, payload TEXT, "
                    "digest TEXT, expires REAL, PRIMARY KEY(scope,key))",
                ):
                    db.execute(sql)
                db.execute("PRAGMA main.user_version=1")
                db.execute("PRAGMA deletions.user_version=1")
            elif (version, dv) != (1, 1):
                raise StorageError("Unsupported memory/deletion schema; migration required")
            self._maintain(db)

    @contextmanager
    def _transaction(self):
        db = None
        try:
            private_file(self.path)
            private_file(self.deletion_path)
            db = sqlite3.connect(self.path, timeout=0.5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("ATTACH DATABASE ? AS deletions", (str(self.deletion_path),))
            for schema in ("main", "deletions"):
                mode = db.execute(f"PRAGMA {schema}.journal_mode").fetchone()[0]
                if mode != "delete":
                    raise StorageError(
                        "Atomic memory/deletion transactions require DELETE journal mode"
                    )
                db.execute(f"PRAGMA {schema}.synchronous=FULL")
                db.execute(f"PRAGMA {schema}.secure_delete=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except sqlite3.Error:
            if db is not None and db.in_transaction:
                db.rollback()
            raise StorageError("Memory database unavailable or corrupt") from None
        except BaseException:
            if db is not None and db.in_transaction:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _scope(scope):
        if not isinstance(scope, Scope):
            raise MemoryIntegrityError("Every memory operation requires an explicit Scope")
        return encode(scope)

    def _maintain(self, db):
        now = self.clock()
        aware_time("clock", now)
        stamp = now.timestamp()
        meta = db.execute("SELECT * FROM meta").fetchall()
        authority = db.execute("SELECT * FROM deletions.authority").fetchall()
        if len(meta) != 1 or len(authority) != 1 or meta[0]["lineage"] != authority[0]["lineage"]:
            raise MemoryIntegrityError("Deletion authority does not match this memory store")
        meta = meta[0]
        if stamp < meta["last_clock"]:
            raise MemoryConflict("Memory clock moved backwards")
        maximum, count = db.execute(
            "SELECT coalesce(max(seq),0),count(*) FROM deletions.events"
        ).fetchone()
        if maximum != count or maximum < meta["applied"]:
            raise MemoryIntegrityError("Deletion authority is incomplete or rolled back")
        for event in db.execute(
            "SELECT * FROM deletions.events WHERE seq>? ORDER BY seq", (meta["applied"],)
        ).fetchall():
            self._erase(db, event["scope"], event["kind"], event["key"])
        db.execute(
            "UPDATE meta SET applied=(SELECT coalesce(max(seq),0) FROM deletions.events),"
            "last_clock=?",
            (stamp,),
        )
        for table, kind in (("turns", "turn"), ("pins", "pin")):
            expired = db.execute(
                f"SELECT scope,key FROM {table} WHERE expires IS NOT NULL AND expires<=?", (stamp,)
            ).fetchall()
            for row in expired:
                self._delete(db, row["scope"], kind, row["key"])
        for row in db.execute(
            "SELECT scope FROM summaries WHERE expires IS NOT NULL AND expires<=?", (stamp,)
        ).fetchall():
            self._changed(db, row["scope"])
        db.execute("DELETE FROM replay WHERE expires<=?", (stamp,))
        return now

    def _active(self, db, scope, expected=None):
        row = db.execute("SELECT * FROM scopes WHERE scope=?", (scope,)).fetchone()
        if row is None:
            raise MemoryConflict("Memory scope does not exist")
        if row["deleted"]:
            raise MemoryConflict("Memory scope is permanently deleted")
        if expected is not None:
            integer_value("expected_revision", expected)
            if row["revision"] != expected:
                raise MemoryConflict("Memory scope revision changed")
        return row["revision"]

    def _changed(self, db, scope, turn_id=None):
        db.execute("UPDATE scopes SET revision=revision+1 WHERE scope=?", (scope,))
        db.execute("DELETE FROM summaries WHERE scope=?", (scope,))
        db.execute("DELETE FROM replay WHERE scope=?", (scope,))
        if turn_id is not None:
            db.execute("DELETE FROM chunks WHERE scope=? AND turn_id=?", (scope, turn_id))
            db.execute("DELETE FROM coverage WHERE scope=? AND turn_id=?", (scope, turn_id))
            for row in db.execute(
                "SELECT key,payload FROM pins WHERE scope=?", (scope,)
            ).fetchall():
                pin = unpack("pin", row["payload"])
                if pin.source and pin.source.turn_id == turn_id:
                    # Tombstone derived pins as well, so an older backup cannot revive them.
                    self._delete(db, scope, "pin", row["key"])

    def _erase(self, db, scope, kind, key):
        if kind not in ("scope", "turn", "pin"):
            raise MemoryIntegrityError("Unknown deletion record")
        if kind == "scope":
            db.execute("INSERT OR IGNORE INTO scopes VALUES(?,0,1)", (scope,))
            for table in (
                "turns",
                "pins",
                "summaries",
                "chunks",
                "coverage",
                "replay",
                "operations",
            ):
                db.execute(f"DELETE FROM {table} WHERE scope=?", (scope,))
            db.execute("UPDATE scopes SET deleted=1,revision=revision+1 WHERE scope=?", (scope,))
        else:
            table = "turns" if kind == "turn" else "pins"
            db.execute(f"DELETE FROM {table} WHERE scope=? AND key=?", (scope, key))
            self._changed(db, scope, key if kind == "turn" else None)

    def _delete(self, db, scope, kind, key):
        db.execute(
            "INSERT INTO deletions.events(scope,kind,key) SELECT ?,?,? WHERE NOT EXISTS"
            "(SELECT 1 FROM deletions.events WHERE scope=? AND kind=? AND key=?)",
            (scope, kind, key, scope, kind, key),
        )
        self._erase(db, scope, kind, key)
        db.execute("UPDATE meta SET applied=(SELECT coalesce(max(seq),0) FROM deletions.events)")

    @staticmethod
    def _not_deleted(db, scope, kind, key):
        if db.execute(
            "SELECT 1 FROM deletions.events WHERE scope=? AND kind=? AND key=?", (scope, kind, key)
        ).fetchone():
            raise MemoryConflict("Deleted identifiers cannot be reused")

    def create_scope(self, scope):
        scope = self._scope(scope)
        with self._transaction() as db:
            self._maintain(db)
            self._not_deleted(db, scope, "scope", "")
            db.execute("INSERT OR IGNORE INTO scopes VALUES(?,0,0)", (scope,))
            return self._active(db, scope)

    def put_turn(self, turn, *, operation_id, expected_revision, expires_at=None):
        if not isinstance(turn, Turn):
            raise MemoryIntegrityError("Ingestion requires a validated Turn")
        ChatRequest(turn.messages)  # Complete tool-call pairs must be ingested atomically.
        text_value("operation_id", operation_id)
        integer_value("expected_revision", expected_revision)
        if expires_at is not None:
            aware_time("expires_at", expires_at)
        payload = encode(turn)
        if len(payload.encode()) > 1_000_000:
            raise MemoryIntegrityError("Turn exceeds persistent payload limit")
        scope = self._scope(turn.scope)
        operation_hash = digest([plain(turn), expires_at])
        with self._transaction() as db:
            now = self._maintain(db)
            self._active(db, scope)
            old_op = db.execute(
                "SELECT * FROM operations WHERE scope=? AND key=?", (scope, operation_id)
            ).fetchone()
            if old_op:
                if old_op["digest"] != operation_hash:
                    raise MemoryConflict("Idempotency key reused with different input")
                return old_op["result"]
            self._active(db, scope, expected_revision)
            self._not_deleted(db, scope, "turn", turn.turn_id)
            if expires_at is not None and expires_at <= now:
                raise MemoryIntegrityError("Cannot ingest already expired content")
            old = db.execute(
                "SELECT * FROM turns WHERE scope=? AND key=?", (scope, turn.turn_id)
            ).fetchone()
            if turn.revision != (old["revision"] + 1 if old else 1):
                raise MemoryConflict("Turn revision must advance exactly once")
            count, size = db.execute(
                "SELECT count(*),coalesce(sum(length(CAST(payload AS BLOB))),0) "
                "FROM turns WHERE scope=?",
                (scope,),
            ).fetchone()
            if (
                count + (old is None) > MAX_TURNS
                or size + len(payload.encode()) - (len(old["payload"].encode()) if old else 0)
                > MAX_BYTES
            ):
                raise MemoryIntegrityError("Memory scope exceeds retention capacity")
            position = (
                old["position"]
                if old
                else db.execute(
                    "SELECT coalesce(max(position),0)+1 FROM turns WHERE scope=?", (scope,)
                ).fetchone()[0]
            )
            db.execute(
                "INSERT INTO turns VALUES(?,?,?,?,?,?,?) ON CONFLICT(scope,key) DO UPDATE SET "
                "revision=excluded.revision,payload=excluded.payload,digest=excluded.digest,"
                "expires=excluded.expires",
                (
                    scope,
                    turn.turn_id,
                    position,
                    turn.revision,
                    payload,
                    digest(turn),
                    expires_at.timestamp() if expires_at else None,
                ),
            )
            self._changed(db, scope, turn.turn_id)
            revision = self._active(db, scope)
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (scope, operation_id, operation_hash, revision),
            )
            return revision

    def put_pin(self, pin, *, expected_revision):
        integer_value("expected_revision", expected_revision)
        if not isinstance(pin, Pin) or len(encode(pin).encode()) > 65536:
            raise MemoryIntegrityError("Invalid or oversized persistent pin")
        scope = self._scope(pin.scope)
        with self._transaction() as db:
            now = self._maintain(db)
            self._active(db, scope, expected_revision)
            self._not_deleted(db, scope, "pin", pin.key)
            if pin.expires_at and pin.expires_at <= now:
                raise MemoryIntegrityError("Cannot persist expired pin")
            old = db.execute(
                "SELECT revision FROM pins WHERE scope=? AND key=?", (scope, pin.key)
            ).fetchone()
            if pin.revision != (old[0] + 1 if old else 1):
                raise MemoryConflict("Pin revision conflict")
            if (
                old is None
                and db.execute("SELECT count(*) FROM pins WHERE scope=?", (scope,)).fetchone()[0]
                >= 256
            ):
                raise MemoryIntegrityError("Pin limit exceeded")
            if pin.source:
                source_row = db.execute(
                    "SELECT * FROM turns WHERE scope=? AND key=?", (scope, pin.source.turn_id)
                ).fetchone()
                if source_row is None:
                    raise MemoryConflict("Pin source no longer exists")
                pin.source.extract(self._read("turn", source_row))
            db.execute(
                "INSERT INTO pins VALUES(?,?,?,?,?,?) ON CONFLICT(scope,key) DO UPDATE SET "
                "revision=excluded.revision,payload=excluded.payload,digest=excluded.digest,"
                "expires=excluded.expires",
                (
                    scope,
                    pin.key,
                    pin.revision,
                    encode(pin),
                    digest(pin),
                    pin.expires_at.timestamp() if pin.expires_at else None,
                ),
            )
            self._changed(db, scope)
            return self._active(db, scope)

    @staticmethod
    def _read(kind, row):
        value = unpack(kind, row["payload"])
        if digest(value) != row["digest"]:
            raise MemoryIntegrityError("Memory payload digest mismatch")
        if "scope" in row.keys() and encode(value.scope) != row["scope"]:
            raise MemoryIntegrityError("Persisted memory scope mismatch")
        if kind in ("turn", "pin") and (
            (value.turn_id if kind == "turn" else value.key) != row["key"]
            or value.revision != row["revision"]
        ):
            raise MemoryIntegrityError("Persisted memory identity mismatch")
        return value

    def _snapshot(self, db, scope, now):
        encoded = self._scope(scope)
        revision = self._active(db, encoded)
        turns = tuple(
            self._read("turn", r)
            for r in db.execute("SELECT * FROM turns WHERE scope=? ORDER BY position", (encoded,))
        )
        pins = KeyedPins(
            scope,
            tuple(
                p
                for r in db.execute("SELECT * FROM pins WHERE scope=? ORDER BY key", (encoded,))
                if (p := self._read("pin", r)).is_active(now)
            ),
        )
        row = db.execute("SELECT * FROM summaries WHERE scope=?", (encoded,)).fetchone()
        summary = self._read("summary", row) if row else None
        if summary and not summary.matches(
            tuple(t for t in turns if t.turn_id in summary.covered_turn_ids), scope, now
        ):
            raise MemoryIntegrityError("Persisted summary lineage mismatch")
        epoch = db.execute("SELECT epoch FROM meta").fetchone()[0]
        identifier = digest(
            [epoch, encoded, revision, [t.content_hash for t in turns], pins, summary]
        )
        return MemorySnapshot(scope, revision, identifier, turns, pins, summary, now)

    def snapshot(self, scope):
        with self._transaction() as db:
            now = self._maintain(db)
            return self._snapshot(db, scope, now)

    def _current(self, db, snapshot, now):
        if not isinstance(snapshot, MemorySnapshot):
            raise MemoryIntegrityError("Expected a memory snapshot")
        current = self._snapshot(db, snapshot.scope, now)
        if current != snapshot and current.snapshot_id != snapshot.snapshot_id:
            raise MemoryConflict("Memory snapshot is stale")
        return current

    def assert_current(self, snapshot):
        with self._transaction() as db:
            return self._current(db, snapshot, self._maintain(db))

    def delete(self, scope, *, kind, key="", expected_revision):
        integer_value("expected_revision", expected_revision)
        if kind not in ("scope", "turn", "pin") or (kind == "scope" and key):
            raise MemoryIntegrityError("Invalid deletion target")
        if kind != "scope":
            text_value("key", key)
        encoded = self._scope(scope)
        with self._transaction() as db:
            self._maintain(db)
            self._active(db, encoded, expected_revision)
            self._delete(db, encoded, kind, key)

    def put_summary(self, snapshot, summary):
        if not isinstance(summary, SummarySnapshot) or len(encode(summary).encode()) > 256000:
            raise MemoryIntegrityError("Invalid or oversized summary")
        with self._transaction() as db:
            current = self._current(db, snapshot, self._maintain(db))
            history = tuple(t for t in current.history if t.turn_id in summary.covered_turn_ids)
            if not summary.matches(history, current.scope, current.at):
                raise MemoryConflict("Summary lineage or expiry does not match source")
            encoded = self._scope(current.scope)
            self._changed(db, encoded)
            db.execute(
                "INSERT INTO summaries VALUES(?,?,?,?)",
                (
                    encoded,
                    encode(summary),
                    digest(summary),
                    summary.expires_at.timestamp() if summary.expires_at else None,
                ),
            )

    def index_batch(self, snapshot, config=None, *, batch_size=32):
        config = RetrievalConfig() if config is None else config
        integer_value("batch_size", batch_size, minimum=1)
        if batch_size > 256 or not isinstance(config, RetrievalConfig):
            raise MemoryIntegrityError("Invalid bounded indexing configuration")
        profile = digest(config)
        with self._transaction() as db:
            current = self._current(db, snapshot, self._maintain(db))
            scope = self._scope(current.scope)
            # Keep one active profile per scope, rather than accumulating unbounded caches.
            for table in ("coverage", "chunks"):
                db.execute(f"DELETE FROM {table} WHERE scope=? AND profile<>?", (scope, profile))
            completed = {
                r["turn_id"]: r["source_hash"]
                for r in db.execute(
                    "SELECT * FROM coverage WHERE scope=? AND profile=?", (scope, profile)
                )
            }
            pending = [t for t in current.history if completed.get(t.turn_id) != t.content_hash]
            changed = pending[:batch_size]
            for turn in changed:
                maximum = sum(
                    (len(m.content) + config.chunk_characters - config.overlap_characters - 1)
                    // (config.chunk_characters - config.overlap_characters)
                    for m in turn.messages
                )
                count = db.execute(
                    "SELECT count(*) FROM chunks WHERE scope=?", (scope,)
                ).fetchone()[0]
                if count + maximum > MAX_CHUNKS:
                    raise MemoryIntegrityError("Persistent chunk index exceeds bound")
                chunks = chunk_turns((turn,), config)
                db.execute("DELETE FROM chunks WHERE scope=? AND turn_id=?", (scope, turn.turn_id))
                db.executemany(
                    "INSERT INTO chunks VALUES(?,?,?,?,?)",
                    [(scope, profile, turn.turn_id, c.chunk_id, encode(c)) for c in chunks],
                )
                db.execute(
                    "INSERT INTO coverage VALUES(?,?,?,?,?) ON CONFLICT(scope,profile,turn_id) "
                    "DO UPDATE SET source_hash=excluded.source_hash,"
                    "chunks_hash=excluded.chunks_hash",
                    (
                        scope,
                        profile,
                        turn.turn_id,
                        turn.content_hash,
                        digest(sorted((c.chunk_id, digest(c)) for c in chunks)),
                    ),
                )
            return {
                "status": "READY" if len(pending) <= batch_size else "BUILDING",
                "processed": len(changed),
                "remaining": max(0, len(pending) - batch_size),
                "profile": profile,
            }

    def chunk_index(self, snapshot, config=None):
        config = RetrievalConfig() if config is None else config
        if not isinstance(config, RetrievalConfig):
            raise MemoryIntegrityError("Invalid indexing configuration")
        profile = digest(config)
        with self._transaction() as db:
            current = self._current(db, snapshot, self._maintain(db))
            scope = self._scope(current.scope)
            chunks = []
            for turn in current.history:
                coverage = db.execute(
                    "SELECT * FROM coverage WHERE scope=? AND profile=? AND turn_id=?",
                    (scope, profile, turn.turn_id),
                ).fetchone()
                if coverage is None or coverage["source_hash"] != turn.content_hash:
                    raise MemoryConflict("Chunk index is not ready for this snapshot")
                values = tuple(
                    unpack("chunk", r[0])
                    for r in db.execute(
                        "SELECT payload FROM chunks WHERE scope=? AND profile=? "
                        "AND turn_id=? ORDER BY key",
                        (scope, profile, turn.turn_id),
                    )
                )
                if (
                    digest(sorted((c.chunk_id, digest(c)) for c in values))
                    != coverage["chunks_hash"]
                ):
                    raise MemoryIntegrityError("Persistent chunk index is incomplete or corrupt")
                for chunk in values:
                    chunk.validate_source(turn)
                chunks.extend(values)
            return ChunkIndex(history_digest(current.history), digest(config), tuple(chunks))

    def cache_put(self, snapshot, key, payload, *, ttl_seconds=3600):
        text_value("cache_key", key)
        integer_value("ttl_seconds", ttl_seconds, minimum=1)
        if (
            ttl_seconds > 86400
            or len(encode(payload).encode()) > 1_000_000
            or not isinstance(payload, dict)
        ):
            raise MemoryIntegrityError("Invalid bounded replay payload")
        with self._transaction() as db:
            current = self._current(db, snapshot, self._maintain(db))
            scope = self._scope(current.scope)
            if (
                db.execute("SELECT count(*) FROM replay WHERE scope=?", (scope,)).fetchone()[0]
                >= 100
            ):
                raise MemoryIntegrityError("Replay cache entry limit reached")
            db.execute(
                "INSERT INTO replay VALUES(?,?,?,?,?,?) ON CONFLICT(scope,key) DO UPDATE SET "
                "snapshot=excluded.snapshot,payload=excluded.payload,digest=excluded.digest,"
                "expires=excluded.expires",
                (
                    scope,
                    key,
                    current.snapshot_id,
                    encode(payload),
                    digest(payload),
                    current.at.timestamp() + ttl_seconds,
                ),
            )

    def cache_get(self, snapshot, key):
        text_value("cache_key", key)
        with self._transaction() as db:
            current = self._current(db, snapshot, self._maintain(db))
            row = db.execute(
                "SELECT * FROM replay WHERE scope=? AND key=? AND snapshot=?",
                (self._scope(current.scope), key, current.snapshot_id),
            ).fetchone()
            if row is None:
                return None
            value = decode(row["payload"])
            if digest(value) != row["digest"]:
                raise MemoryIntegrityError("Replay payload is corrupt")
            return value

    def assemble(self, scope, question, budget, *, system, retrieval_config=None, **options):
        retrieval_config = RetrievalConfig() if retrieval_config is None else retrieval_config
        snapshot = self.snapshot(scope)
        while self.index_batch(snapshot, retrieval_config)["status"] != "READY":
            pass
        result = assemble_context(
            snapshot.history,
            question,
            snapshot.pins,
            budget,
            system=system,
            at=snapshot.at,
            retrieval_config=retrieval_config,
            chunk_index=self.chunk_index(snapshot, retrieval_config),
            summary_policy=FrozenSummaryPolicy(snapshot.summary) if snapshot.summary else None,
            **options,
        )
        self.assert_current(snapshot)
        return snapshot, result

    def deletion_watermark(self):
        with self._transaction() as db:
            self._maintain(db)
            row = db.execute("SELECT lineage,applied FROM meta").fetchone()
            return {"lineage": row["lineage"], "minimum_deletion_seq": row["applied"]}

    def prune(self):
        """Commit pending expiry/deletion cleanup even when no context is requested."""
        return self.deletion_watermark()

    @staticmethod
    def _copy(source, destination):
        destination = private_file(destination, create=True, exclusive=True)
        start = time.monotonic()

        def progress(*_):
            if time.monotonic() - start > 10:
                raise StorageError("Backup deadline exceeded; partial destination is not usable")

        try:
            with closing(
                sqlite3.connect(Path(source).absolute().as_uri() + "?mode=ro", uri=True)
            ) as src:
                with closing(sqlite3.connect(destination)) as dst:
                    src.backup(dst, pages=128, progress=progress, sleep=0.01)
        except sqlite3.Error:
            raise StorageError("Cannot copy validated memory database") from None
        return destination

    def backup(self, destination):
        self.deletion_watermark()
        return self._copy(self.path, destination)

    @classmethod
    def restore(cls, backup, destination, *, deletion_path, minimum_deletion_seq, clock=None):
        integer_value("minimum_deletion_seq", minimum_deletion_seq)
        private_file(backup)
        private_file(deletion_path)
        try:
            with closing(
                sqlite3.connect(Path(backup).absolute().as_uri() + "?mode=ro", uri=True)
            ) as source:
                if source.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise MemoryIntegrityError("Unsupported backup schema")
                records = source.execute("SELECT lineage,applied FROM meta").fetchall()
                if len(records) != 1:
                    raise MemoryIntegrityError("Invalid backup metadata")
                lineage, applied = records[0]
            with closing(
                sqlite3.connect(Path(deletion_path).absolute().as_uri() + "?mode=ro", uri=True)
            ) as authority:
                known = authority.execute("SELECT lineage FROM authority").fetchall()
                maximum, count = authority.execute(
                    "SELECT coalesce(max(seq),0),count(*) FROM events"
                ).fetchone()
                if (
                    known != [(lineage,)]
                    or maximum != count
                    or maximum < max(applied, minimum_deletion_seq)
                ):
                    raise MemoryIntegrityError("Deletion authority is missing, mismatched or stale")
        except (sqlite3.Error, ValueError, TypeError):
            raise MemoryIntegrityError("Cannot validate recovery authority") from None
        destination = cls._copy(backup, destination)
        # Constructor refuses absent/wrong/degraded deletion authority before any public read.
        restored = cls(destination, deletion_path=deletion_path, clock=clock)
        if restored.deletion_watermark()["minimum_deletion_seq"] < minimum_deletion_seq:
            raise MemoryIntegrityError(
                "Deletion authority is older than the required recovery watermark"
            )
        with restored._transaction() as db:
            db.execute("UPDATE meta SET epoch=?", (uuid.uuid4().hex,))
            for table in ("chunks", "coverage", "summaries", "replay"):
                db.execute(f"DELETE FROM {table}")
            db.execute("UPDATE scopes SET revision=revision+1")
        return restored
