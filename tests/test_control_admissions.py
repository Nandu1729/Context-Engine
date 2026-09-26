"""D093: duplicate-clock admissions and explicit lossless control migration."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from context_engine.service.auth import AccessError, Principal
from context_engine.service.control import ControlStore, opaque

PRINCIPAL = Principal("operator", "tenant", "admin", ("*",))


@pytest.fixture
def clock(monkeypatch):
    now = [123456.0]
    monkeypatch.setattr("context_engine.service.control.time.time", lambda: now[0])
    return now


def snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            name: db.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall()
            for name in ("admissions", "audit", "sessions", "policy")
        }
        return version, tables


@pytest.fixture
def legacy(tmp_path, clock):
    path = tmp_path / "control.sqlite"
    store = ControlStore(path, rpm=2, max_sessions=1)
    store.reserve_session("tenant", "session")
    store.begin(PRINCIPAL, "original", "session", "read")
    store.finish("original", "success", 7)
    # Synthetic v1 fixture; never touch owner databases or frozen artifacts.
    with store.transaction() as db:
        db.execute("ALTER TABLE admissions RENAME TO current_admissions")
        db.execute("CREATE TABLE admissions(tenant TEXT, at REAL, PRIMARY KEY(tenant,at))")
        db.execute("INSERT INTO admissions SELECT tenant,at FROM current_admissions")
        db.execute("DROP TABLE current_admissions")
        db.execute("PRAGMA user_version=1")
    return path


def test_equal_timestamps_count_every_request_and_enforce_exact_quota(tmp_path, clock):
    store = ControlStore(tmp_path / "control.sqlite", rpm=3)
    for index in range(3):
        store.begin(PRINCIPAL, str(index), "session", "read")
    with pytest.raises(AccessError) as error:
        store.begin(PRINCIPAL, "denied", "session", "read")
    assert error.value.status == 429
    version, rows = snapshot(store.path)
    assert version == 2
    assert len(rows["admissions"]) == 3
    assert len({row[0] for row in rows["admissions"]}) == 3
    assert {row[2] for row in rows["admissions"]} == {clock[0]}
    events = store.events("tenant", 0, 10)
    assert len(events) == 4 and events[-1]["outcome"] == "quota_exhausted"
    clock[0] += 59.999
    with pytest.raises(AccessError):
        store.begin(PRINCIPAL, "still-denied", "session", "read")
    clock[0] = 123516.0
    store.begin(PRINCIPAL, "after-window", "session", "read")
    assert len(snapshot(store.path)[1]["admissions"]) == 1


def test_same_clock_concurrent_store_instances_admit_exact_limit(tmp_path, clock):
    path = tmp_path / "control.sqlite"
    stores = [ControlStore(path, rpm=3), ControlStore(path, rpm=3)]

    def admit(index):
        try:
            stores[index % 2].begin(PRINCIPAL, str(index), "session", "read")
            return 200
        except AccessError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(admit, range(6)))
    assert sorted(results) == [200, 200, 200, 429, 429, 429]
    assert len(stores[0].events("tenant", 0, 10)) == 6
    assert len(snapshot(path)[1]["admissions"]) == 3


def test_duplicate_request_id_rolls_back_admission(tmp_path, clock):
    store = ControlStore(tmp_path / "control.sqlite", rpm=2)
    store.begin(PRINCIPAL, "one", "session", "read")
    before = snapshot(store.path)
    with pytest.raises(sqlite3.IntegrityError):
        store.begin(PRINCIPAL, "one", "session", "read")
    assert snapshot(store.path) == before
    store.begin(PRINCIPAL, "two", "session", "read")


def test_same_timestamp_different_tenants_have_independent_quotas(tmp_path, clock):
    store = ControlStore(tmp_path / "control.sqlite", rpm=1)
    store.begin(PRINCIPAL, "one", "session", "read")
    other = Principal("operator", "other", "admin", ("*",))
    store.begin(other, "two", "session", "read")
    assert {row[1] for row in snapshot(store.path)[1]["admissions"]} == {
        opaque("tenant"),
        opaque("other"),
    }


def test_v1_requires_opt_in_and_preserves_every_record(legacy):
    before = snapshot(legacy)
    with pytest.raises(ValueError, match="explicit migrate_v1"):
        ControlStore(legacy, rpm=2, max_sessions=1)
    assert snapshot(legacy) == before
    store = ControlStore(legacy, rpm=2, max_sessions=1, migrate_v1=True)
    version, after = snapshot(legacy)
    assert version == 2
    assert [row[1:] for row in after["admissions"]] == before[1]["admissions"]
    for name in ("audit", "sessions", "policy"):
        assert after[name] == before[1][name]
    assert snapshot(ControlStore(legacy, rpm=2, max_sessions=1).path) == (version, after)
    assert snapshot(ControlStore(legacy, rpm=2, max_sessions=1, migrate_v1=True).path) == (
        version,
        after,
    )
    store.begin(PRINCIPAL, "second", "session", "read")
    with pytest.raises(AccessError) as error:
        store.begin(PRINCIPAL, "third", "session", "read")
    assert error.value.status == 429
    with pytest.raises(AccessError):
        store.reserve_session("tenant", "new-session")


def test_migration_does_not_change_quota_policy(legacy):
    before = snapshot(legacy)
    with pytest.raises(ValueError, match="policy changed"):
        ControlStore(legacy, rpm=3, max_sessions=1, migrate_v1=True)
    assert snapshot(legacy) == before


def test_migration_failure_rolls_back_schema_and_data(legacy, monkeypatch):
    before = snapshot(legacy)
    original = sqlite3.connect

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "ALTER TABLE admissions_v2 RENAME TO admissions":
                raise sqlite3.OperationalError("synthetic migration failure")
            return super().execute(sql, parameters)

    with monkeypatch.context() as patch:
        patch.setattr(
            sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=FailingConnection)
        )
        with pytest.raises(sqlite3.OperationalError, match="synthetic"):
            ControlStore(legacy, rpm=2, max_sessions=1, migrate_v1=True)
    assert snapshot(legacy) == before
    ControlStore(legacy, rpm=2, max_sessions=1, migrate_v1=True)


@pytest.mark.parametrize("flag", [1, "yes", None])
def test_migration_flag_is_strict(tmp_path, flag):
    with pytest.raises(ValueError, match="explicit boolean"):
        ControlStore(tmp_path / "control.sqlite", migrate_v1=flag)
    assert not (tmp_path / "control.sqlite").exists()
