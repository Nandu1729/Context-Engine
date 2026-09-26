"""Local shared-worker admission and content-free audit intents, separate from inference."""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from ..memory.store import private_file
from .auth import AccessError


def opaque(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ControlStore:
    def __init__(self, path, *, rpm=60, max_sessions=100, migrate_v1=False):
        if type(migrate_v1) is not bool:
            raise ValueError("Migration requires an explicit boolean")
        if any(type(v) is not int or not 1 <= v <= 10000 for v in (rpm, max_sessions)):
            raise ValueError("Invalid service quotas")
        self.path = private_file(path, create=True)
        self.rpm, self.max_sessions = rpm, max_sessions
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise ValueError("Unsupported service control schema")
            if version == 1 and not migrate_v1:
                raise ValueError("Control schema v1 requires explicit migrate_v1=True after backup")
            db.execute("CREATE TABLE IF NOT EXISTS policy (value TEXT NOT NULL)")
            policy = json.dumps([rpm, max_sessions])
            old = db.execute("SELECT value FROM policy").fetchone()
            if old and old[0] != policy:
                raise ValueError("Service quota policy changed; reviewed migration required")
            if not old:
                db.execute("INSERT INTO policy VALUES(?)", (policy,))
            if version == 1:
                # Reviewed, opt-in, single-transaction migration. Preserve every
                # timestamp/tenant, including expired rows (pruning stays in begin).
                db.execute(
                    "CREATE TABLE admissions_v2 "
                    "(id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, at REAL NOT NULL)"
                )
                db.execute("INSERT INTO admissions_v2(tenant,at) SELECT tenant,at FROM admissions")
                db.execute("DROP TABLE admissions")
                db.execute("ALTER TABLE admissions_v2 RENAME TO admissions")
            db.execute(
                "CREATE TABLE IF NOT EXISTS admissions "
                "(id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, at REAL NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS admissions_tenant_at ON admissions(tenant,at)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions "
                "(tenant TEXT, session TEXT, PRIMARY KEY(tenant,session))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS audit "
                "(seq INTEGER PRIMARY KEY, request_id TEXT UNIQUE, at REAL, "
                "tenant TEXT, actor TEXT, session TEXT, action TEXT, "
                "outcome TEXT, revision INTEGER)"
            )
            db.execute("PRAGMA user_version=2")

    @contextmanager
    def transaction(self):
        private_file(self.path)
        db = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def begin(self, principal, request_id, session, action):
        now, tenant = time.time(), opaque(principal.tenant)
        with self.transaction() as db:
            db.execute("DELETE FROM admissions WHERE at <= ?", (now - 60,))
            count = db.execute("SELECT count(*) FROM admissions WHERE tenant=?", (tenant,))
            denied = count.fetchone()[0] >= self.rpm
            if not denied:
                db.execute("INSERT INTO admissions(tenant,at) VALUES(?,?)", (tenant, now))
            db.execute(
                "INSERT INTO audit VALUES(NULL,?,?,?,?,?,?,?,NULL)",
                (
                    request_id,
                    now,
                    tenant,
                    opaque(principal.subject),
                    opaque(session or ""),
                    action,
                    "quota_exhausted" if denied else "started",
                ),
            )
        if denied:
            raise AccessError(429, "quota_exhausted")

    def finish(self, request_id, outcome, revision=None):
        with self.transaction() as db:
            db.execute(
                "UPDATE audit SET outcome=?, revision=? WHERE request_id=?",
                (outcome, revision, request_id),
            )

    def reserve_session(self, tenant, session):
        # Cumulative slots intentionally remain after delete/failure: no create/delete quota bypass.
        with self.transaction() as db:
            if db.execute(
                "SELECT 1 FROM sessions WHERE tenant=? AND session=?", (tenant, session)
            ).fetchone():
                return
            if (
                db.execute("SELECT count(*) FROM sessions WHERE tenant=?", (tenant,)).fetchone()[0]
                >= self.max_sessions
            ):
                raise AccessError(429, "session_quota_exhausted")
            db.execute("INSERT INTO sessions VALUES(?,?)", (tenant, session))

    def events(self, tenant, after, limit):
        with self.transaction() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM audit WHERE tenant=? AND seq>? ORDER BY seq LIMIT ?",
                    (opaque(tenant), after, limit),
                )
            ]
