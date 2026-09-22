"""One local SQLite transaction boundary for quota admission, ledger and opt-in replay."""

import json
import math
import os
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from ..errors import CacheError, ContractError, ProviderError, QuotaError, StorageError
from ..models import canonical_json, integer_value
from .contracts import (
    Completion,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    Usage,
    fingerprint,
    identifier,
)

ACTIVE = {"reserved", "inflight", "uncertain"}


@dataclass(frozen=True)
class Admission:
    attempt_id: str | None = None
    completion: Completion | None = None
    source_attempt: str | None = None
    original_cost: int | None = None


class RuntimeStore:
    def __init__(self, path: Path):
        try:
            self.path = Path(path).absolute()
            if self.path.is_symlink():
                raise StorageError("Runtime database cannot be a symlink")
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(
                self.path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
            )
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and info.st_mode & 0o077):
                    raise StorageError("Runtime database must be a private regular file")
            finally:
                os.close(descriptor)
            with self.transaction() as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise StorageError("Unsupported runtime database version")
                if version == 0:
                    if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                        raise StorageError("Refusing to adopt an unrelated database")
                    for sql in (
                        """CREATE TABLE accounts(account TEXT PRIMARY KEY, policy TEXT NOT NULL,
                            last_clock REAL NOT NULL)""",
                        """CREATE TABLE attempts(
                            id TEXT PRIMARY KEY, account TEXT NOT NULL, request_key TEXT NOT NULL,
                            model TEXT NOT NULL, created REAL NOT NULL, settled REAL,
                            state TEXT NOT NULL,
                            reserved_tokens INTEGER NOT NULL, reserved_cost INTEGER NOT NULL,
                            charged_tokens INTEGER, cost INTEGER, usage_json TEXT,
                            price_json TEXT NOT NULL, completion_hash TEXT, reason TEXT,
                            request_count INTEGER NOT NULL DEFAULT 1)""",
                        "CREATE INDEX account_attempts ON attempts(account,created)",
                        """CREATE UNIQUE INDEX one_active_request ON attempts(account,request_key)
                            WHERE state IN ('reserved','inflight','uncertain')""",
                        """CREATE TABLE replay(request_key TEXT PRIMARY KEY,
                            source_attempt TEXT NOT NULL,
                            created REAL NOT NULL, expires REAL NOT NULL,
                            payload TEXT NOT NULL, digest TEXT NOT NULL,
                            FOREIGN KEY(source_attempt) REFERENCES attempts(id))""",
                        """CREATE TABLE events(id TEXT PRIMARY KEY, account TEXT NOT NULL,
                            request_key TEXT NOT NULL, created REAL NOT NULL, kind TEXT NOT NULL,
                            source_attempt TEXT, evidence_ref TEXT,
                            new_cost INTEGER NOT NULL DEFAULT 0)""",
                    ):
                        db.execute(sql)
                    db.execute("PRAGMA user_version=1")
        except (OSError, ValueError, TypeError):
            raise StorageError("Cannot initialize private runtime database") from None

    @contextmanager
    def transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=0.2, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except sqlite3.Error:
            if db is not None and db.in_transaction:
                db.rollback()
            raise StorageError("Runtime database unavailable or corrupt") from None
        except BaseException:
            if db is not None and db.in_transaction:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _clock(now):
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise StorageError("Invalid accounting clock")
        return now

    def _account(self, db, policy, now):
        now = self._clock(now)
        key, encoded = fingerprint(policy.account_id), canonical_json(asdict(policy))
        row = db.execute("SELECT * FROM accounts WHERE account=?", (key,)).fetchone()
        if row is None:
            db.execute("INSERT INTO accounts VALUES(?,?,?)", (key, encoded, now))
        else:
            if row["policy"] != encoded:
                raise QuotaError("Shared account policy changed; explicit migration is required")
            if now + 5 < row["last_clock"]:
                raise QuotaError("Accounting clock moved backwards")
            now = max(now, row["last_clock"])
            db.execute("UPDATE accounts SET last_clock=? WHERE account=?", (now, key))
        return key, now

    def admit(
        self,
        *,
        policy: QuotaPolicy,
        key: str,
        model: str,
        reserved_tokens: int,
        reserved_cost: int,
        prices: PriceCard,
        replay: ReplayPolicy,
        now: float,
        send_allowed: bool = True,
    ) -> Admission:
        policy.validate_prices(prices)
        if policy.billing_mode == "free_tier" and reserved_cost != 0:
            raise ContractError("Free-tier mode cannot reserve paid spending")
        for value in (reserved_tokens, reserved_cost):
            integer_value("reservation", value)
            if value > 10**12:
                raise ContractError("Reservation exceeds accounting range")
        with self.transaction() as db:
            account, now = self._account(db, policy, now)
            if replay.enabled:
                cached = db.execute("SELECT * FROM replay WHERE request_key=?", (key,)).fetchone()
                if cached and now < min(cached["expires"], cached["created"] + replay.ttl_seconds):
                    source = db.execute(
                        "SELECT * FROM attempts WHERE id=?", (cached["source_attempt"],)
                    ).fetchone()
                    try:
                        value = json.loads(cached["payload"])
                        completion = Completion.from_dict(value)
                        digest = fingerprint(value)
                        if (
                            digest != cached["digest"]
                            or not source
                            or source["account"] != account
                            or source["request_key"] != key
                            or source["state"] != "completed"
                            or digest != source["completion_hash"]
                            or completion.finish_reason != "stop"
                            or completion.model != model
                        ):
                            raise ValueError
                    except (ValueError, KeyError, TypeError, ContractError, RecursionError):
                        raise CacheError(
                            "Replay entry failed integrity checks; no request was sent"
                        ) from None
                    db.execute(
                        """INSERT INTO events(id,account,request_key,created,kind,source_attempt)
                           VALUES(?,?,?,?,?,?)""",
                        (uuid.uuid4().hex, account, key, now, "replay", source["id"]),
                    )
                    return Admission(
                        completion=completion,
                        source_attempt=source["id"],
                        original_cost=source["cost"],
                    )
            if not send_allowed:
                raise ProviderError("Credentials are required for a new provider request")
            if db.execute(
                """SELECT id FROM attempts WHERE account=? AND request_key=?
                   AND state IN ('reserved','inflight','uncertain')""",
                (account, key),
            ).fetchone():
                raise QuotaError("An identical request is active or has uncertain billing")
            if policy.daily_budget_microusd == 0 and policy.billing_mode != "free_tier":
                raise QuotaError("Provider spending is disabled")
            usage = {"rpm": 0, "tpm": 0, "rpd": 0, "tpd": 0, "cost": 0}
            day = int(now // 86400) * 86400
            for row in db.execute("SELECT * FROM attempts WHERE account=?", (account,)):
                self._validate_row(row)
                active = row["state"] in ACTIVE
                anchor = row["settled"] if row["settled"] is not None else row["created"]
                tokens = row["reserved_tokens"] if active else row["charged_tokens"] or 0
                cost = row["reserved_cost"] if active else row["cost"] or 0
                requests = 1 if active else row["request_count"]
                if active or anchor > now - 60:
                    usage["rpm"] += requests
                    usage["tpm"] += tokens
                if active or anchor >= day:
                    usage["rpd"] += requests
                    usage["tpd"] += tokens
                    usage["cost"] += cost
            for field, extra in (
                ("rpm", 1),
                ("tpm", reserved_tokens),
                ("rpd", 1),
                ("tpd", reserved_tokens),
                ("cost", reserved_cost),
            ):
                ceiling = (
                    policy.daily_budget_microusd if field == "cost" else getattr(policy, field)
                )
                if usage[field] + extra > ceiling:
                    raise QuotaError("Local account quota exhausted", dimension=field)
            attempt = uuid.uuid4().hex
            db.execute(
                """INSERT INTO attempts(id,account,request_key,model,created,state,
                        reserved_tokens,reserved_cost,price_json)
                        VALUES(?,?,?,?,?,'reserved',?,?,?)""",
                (
                    attempt,
                    account,
                    key,
                    model,
                    now,
                    reserved_tokens,
                    reserved_cost,
                    canonical_json(asdict(prices)),
                ),
            )
            return Admission(attempt_id=attempt)

    def mark_inflight(self, attempt: str):
        with self.transaction() as db:
            if (
                db.execute(
                    "UPDATE attempts SET state='inflight' WHERE id=? AND state='reserved'",
                    (attempt,),
                ).rowcount
                != 1
            ):
                raise StorageError("Reservation is not ready for dispatch")

    def settle(
        self,
        attempt: str,
        *,
        now: float,
        completion: Completion | None = None,
        usage: Usage | None = None,
        uncertain=False,
        reason=None,
        sent=True,
        replay: ReplayPolicy | None = None,
    ) -> tuple[int | None, str | None]:
        now = self._clock(now)
        replay = replay or ReplayPolicy()
        with self.transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (attempt,)).fetchone()
            if not row or row["state"] not in ("reserved", "inflight"):
                raise StorageError("Reservation already reconciled or missing")
            usage = completion.usage if completion else usage
            warning = None
            if uncertain and usage is None:
                db.execute(
                    "UPDATE attempts SET state='uncertain',reason=? WHERE id=?", (reason, attempt)
                )
                return None, "usage_unknown_reservation_held"
            prices = PriceCard(**json.loads(row["price_json"]))
            cost = prices.observed_cost(usage) if usage else 0
            tokens = (
                usage.total_tokens if usage else 0
            )  # Conservatively count cached input in local limits.
            if tokens > row["reserved_tokens"] or cost > row["reserved_cost"]:
                warning = "provider_usage_exceeded_reservation"
            elif usage and usage.cached_input_tokens is None:
                warning = "cached_usage_unknown_cost_is_upper_estimate"
            state = "completed" if completion and completion.finish_reason == "stop" else "rejected"
            encoded = canonical_json(completion.to_dict()) if completion else None
            digest = fingerprint(completion.to_dict()) if completion else None
            db.execute(
                """UPDATE attempts SET state=?,settled=?,charged_tokens=?,cost=?,usage_json=?,
                        completion_hash=?,reason=?,request_count=? WHERE id=?""",
                (
                    state,
                    max(now, row["created"]),
                    tokens,
                    cost,
                    canonical_json(asdict(usage)) if usage else None,
                    digest,
                    reason or (completion.finish_reason if completion else None),
                    int(sent),
                    attempt,
                ),
            )
            if state == "completed" and replay.enabled:
                db.execute(
                    """INSERT INTO replay VALUES(?,?,?,?,?,?) ON CONFLICT(request_key) DO UPDATE SET
                            source_attempt=excluded.source_attempt,created=excluded.created,expires=excluded.expires,
                            payload=excluded.payload,digest=excluded.digest""",
                    (row["request_key"], attempt, now, now + replay.ttl_seconds, encoded, digest),
                )
            return cost, warning

    def resolve_uncertain(
        self,
        attempt: str,
        *,
        evidence_ref: str,
        now: float,
        usage: Usage | None = None,
        confirmed_not_processed: bool = False,
    ):
        identifier(evidence_ref)
        self._clock(now)
        if type(confirmed_not_processed) is not bool or (usage is None) == (
            not confirmed_not_processed
        ):
            raise ContractError("Supply observed usage OR confirmed-not-processed evidence")
        if usage is not None and not isinstance(usage, Usage):
            raise ContractError("Reconciliation requires validated usage")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (attempt,)).fetchone()
            if not row or row["state"] not in ACTIVE:
                raise StorageError("No unresolved reservation to reconcile")
            prices = PriceCard(**json.loads(row["price_json"]))
            cost = prices.observed_cost(usage) if usage else 0
            db.execute(
                """UPDATE attempts SET state='reconciled',settled=?,charged_tokens=?,cost=?,
                        usage_json=?,reason='external_reconciliation',request_count=? WHERE id=?""",
                (
                    max(now, row["created"]),
                    usage.total_tokens if usage else 0,
                    cost,
                    canonical_json(asdict(usage)) if usage else None,
                    int(not confirmed_not_processed),
                    attempt,
                ),
            )
            db.execute(
                """INSERT INTO events(id,account,request_key,created,kind,
                   source_attempt,evidence_ref)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex,
                    row["account"],
                    row["request_key"],
                    now,
                    "reconciliation",
                    attempt,
                    evidence_ref,
                ),
            )

    def snapshot(self, policy: QuotaPolicy) -> dict:
        with self.transaction() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM attempts WHERE account=?", (fingerprint(policy.account_id),)
                )
            ]
            events = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM events WHERE account=?", (fingerprint(policy.account_id),)
                )
            ]
        return {
            "attempts": rows,
            "events": events,
            "known_cost_microusd": sum(row["cost"] or 0 for row in rows),
            "held_cost_microusd": sum(
                row["reserved_cost"] for row in rows if row["state"] in ACTIVE
            ),
            "unresolved_attempts": sum(row["state"] in ACTIVE for row in rows),
        }

    @staticmethod
    def _validate_row(row):
        if row["state"] not in ACTIVE | {"completed", "rejected", "reconciled"}:
            raise StorageError("Invalid accounting state")
        names = ["reserved_tokens", "reserved_cost", "request_count"]
        if row["state"] not in ACTIVE:
            names += ["charged_tokens", "cost"]
        if any(type(row[name]) is not int or row[name] < 0 for name in names):
            raise StorageError("Invalid accounting values")
