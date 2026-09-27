"""D095: shared storage ACL policy, plus real Windows SQLite/sidecar coverage."""

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from private_files import set_private_permissions

from context_engine import _sqlite
from context_engine import _windows_storage as windows
from context_engine._windows_security import WindowsReader
from context_engine.errors import ContractError, StorageError
from context_engine.memory import MemoryStore
from context_engine.providers.store import RuntimeStore
from context_engine.service.control import ControlStore

USER = "S-1-5-21-1-2-3-1001"
native = pytest.mark.skipif(os.name != "nt", reason="Requires real Windows storage ACL APIs")


def test_windows_sqlite_temporaries_stay_in_memory(monkeypatch):
    monkeypatch.setattr(_sqlite, "os", SimpleNamespace(name="nt"))
    db = _sqlite.connect(":memory:")
    try:
        assert db.execute("PRAGMA temp_store").fetchone()[0] == 2
    finally:
        db.close()


def test_sqlite_configuration_failure_closes_connection(monkeypatch):
    closed = []

    def fail(*args):
        raise sqlite3.OperationalError("synthetic")

    db = SimpleNamespace(execute=fail, close=lambda: closed.append(True))
    monkeypatch.setattr(_sqlite, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: db)
    with pytest.raises(sqlite3.OperationalError):
        _sqlite.connect(":memory:")
    assert closed == [True]


@pytest.mark.parametrize(
    "entries,accepted",
    [
        ([(0, 3, 0x1F01FF, USER)], True),
        ([(0, 0, 0x1F01FF, USER)], False),  # No file inheritance.
        ([(0, 2, 0x1F01FF, USER)], False),  # Directory-only inheritance.
        ([(0, 3, 1, USER)], False),  # Insufficient rights for SQLite sidecars.
        ([(0, 3, 0x1F01FF, USER), (0, 9, 1, "S-1-1-0")], False),
        ([(0, 3, 0x1F01FF, USER), (9, 9, 1, USER)], False),
        ([], False),
        (None, False),
    ],
)
def test_directory_acl_requires_safe_inheritance(entries, accepted):
    reader = WindowsReader.__new__(WindowsReader)
    reader.file = SimpleNamespace(
        GetFileInformationByHandle=lambda _: (0x10,), GetFileType=lambda _: 1
    )
    acl = (
        None
        if entries is None
        else SimpleNamespace(
            GetAceCount=lambda: len(entries),
            GetAce=lambda i: ((entries[i][0], entries[i][1]), entries[i][2], entries[i][3]),
        )
    )
    sd = SimpleNamespace(
        GetSecurityDescriptorOwner=lambda: USER, GetSecurityDescriptorDacl=lambda: acl
    )
    reader.security = SimpleNamespace(
        SE_FILE_OBJECT=1,
        OWNER_SECURITY_INFORMATION=1,
        DACL_SECURITY_INFORMATION=4,
        GetSecurityInfo=lambda *args: sd,
        ConvertSidToStringSid=lambda sid: sid,
    )
    reader.user = lambda: USER
    if accepted:
        reader.validate(object(), directory=True)
    else:
        with pytest.raises(ContractError):
            reader.validate(object(), directory=True)


@pytest.mark.parametrize("failure", [None, "init", "parent", "file", "sidecar"])
def test_boundary_fail_closed_and_no_acl_rewrite(monkeypatch, tmp_path, failure):
    events = []

    def event(name):
        events.append(name)
        if name == failure:
            raise OSError("PRIVATE_PATH")

    class Boundary:
        def __init__(self):
            event("init")

        def local_path(self, path):
            return Path(path)

        def directory(self, path, *, create):
            event("parent")

        def file_boundary(self, path, **kwargs):
            event("sidecar" if kwargs.get("optional") else "file")

    monkeypatch.setattr(windows, "WindowsStorage", Boundary)
    if failure:
        with pytest.raises(StorageError) as error:
            windows.private_file(tmp_path / "db.sqlite", create=True)
        assert "PRIVATE_PATH" not in str(error.value)
        assert error.value.__suppress_context__
        assert events[-1] == failure
    else:
        assert windows.private_file(tmp_path / "db.sqlite") == tmp_path / "db.sqlite"
        assert events == ["init", "parent", "file", "sidecar", "sidecar", "sidecar"]


@pytest.mark.parametrize("links,invalid", [(1, False), (2, False), (1, True)])
def test_storage_handle_is_closed_on_rejection(links, invalid):
    boundary = windows.WindowsStorage.__new__(windows.WindowsStorage)
    closed = []
    handle = SimpleNamespace(Close=lambda: closed.append(True))
    boundary.open_storage = lambda *args, **kwargs: handle
    boundary.error = OSError
    boundary.file = SimpleNamespace(GetFileInformationByHandle=lambda _: (0,) * 7 + (links,))

    def validate(actual):
        assert actual is handle
        if invalid:
            raise ContractError("invalid")

    boundary.validate = validate
    if links != 1 or invalid:
        with pytest.raises((StorageError, ContractError)):
            boundary.file_boundary("unused")
    else:
        boundary.file_boundary("unused")
    assert closed == [True]


@native
@pytest.mark.parametrize("factory", [MemoryStore, RuntimeStore, ControlStore])
def test_native_new_store_and_reopen_private_acl(tmp_path, factory):
    path = tmp_path / "new" / "nested" / "数据 %#.sqlite"
    store = factory(path)
    windows.private_file(store.path)
    factory(path)
    assert path.exists()


@native
@pytest.mark.parametrize("factory", [MemoryStore, RuntimeStore, ControlStore])
def test_native_public_database_rejected_without_rewrite(tmp_path, factory):
    path = tmp_path / "db.sqlite"
    factory(path)
    original = path.read_bytes()
    set_private_permissions(path, public=True)
    with pytest.raises(StorageError, match="private"):
        factory(path)
    assert path.read_bytes() == original
    # The rejected file remains public: validation must not silently repair it.
    with pytest.raises(StorageError):
        windows.private_file(path)


@native
@pytest.mark.parametrize("factory", [MemoryStore, RuntimeStore, ControlStore])
@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm", "-mj-test"])
def test_native_public_sidecars_rejected_before_sqlite(tmp_path, factory, suffix):
    path = tmp_path / "db.sqlite"
    factory(path)
    original = path.read_bytes()
    sidecar = path.with_name(path.name + suffix)
    sidecar.write_bytes(b"synthetic")
    set_private_permissions(sidecar, public=True)
    with pytest.raises(StorageError):
        factory(path)
    assert path.read_bytes() == original and sidecar.read_bytes() == b"synthetic"


@native
def test_native_parent_acl_rejected_and_not_changed(tmp_path):
    parent = tmp_path / "broad"
    parent.mkdir()
    set_private_permissions(parent, public=True)
    with pytest.raises(StorageError):
        RuntimeStore(parent / "db.sqlite")
    assert not (parent / "db.sqlite").exists()
    with pytest.raises(StorageError):
        RuntimeStore(parent / "other.sqlite")


@native
@pytest.mark.parametrize("mode", ["inherit-only-public", "null", "no-inheritance"])
def test_native_unsafe_directory_inheritance_rejected(tmp_path, mode):
    import win32security as security

    parent = tmp_path / "parent"
    parent.mkdir()
    set_private_permissions(parent)
    acl = security.GetNamedSecurityInfo(
        str(parent), security.SE_FILE_OBJECT, security.DACL_SECURITY_INFORMATION
    ).GetSecurityDescriptorDacl()
    if mode == "null":
        acl = None
    elif mode == "inherit-only-public":
        acl.AddAccessAllowedAceEx(
            security.ACL_REVISION,
            0x01 | 0x08,
            1,
            security.ConvertStringSidToSid("S-1-1-0"),
        )
    else:
        old = acl
        acl = security.ACL()
        for index in range(old.GetAceCount()):
            ace = old.GetAce(index)
            acl.AddAccessAllowedAceEx(security.ACL_REVISION, 0, ace[1], ace[2])
    security.SetNamedSecurityInfo(
        str(parent),
        security.SE_FILE_OBJECT,
        security.DACL_SECURITY_INFORMATION | security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
    try:
        with pytest.raises(StorageError):
            RuntimeStore(parent / "db.sqlite")
        assert not (parent / "db.sqlite").exists()
    finally:
        set_private_permissions(parent)


@native
def test_native_existing_instance_rechecks_parent(tmp_path):
    parent = tmp_path / "parent"
    store = RuntimeStore(parent / "db.sqlite")
    set_private_permissions(parent, public=True)
    with pytest.raises(StorageError):
        with store.transaction():
            pytest.fail("Unsafe directory reached SQLite")


@native
@pytest.mark.parametrize("alias", ["symlink", "hardlink", "directory"])
def test_native_storage_aliases_rejected(tmp_path, alias):
    path = tmp_path / "db.sqlite"
    RuntimeStore(path)
    candidate = tmp_path / "alias"
    if alias == "symlink":
        candidate.symlink_to(path)
    elif alias == "hardlink":
        os.link(path, candidate)
    else:
        candidate.mkdir()
    with pytest.raises(StorageError):
        windows.private_file(candidate)


@native
def test_native_directory_link_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(StorageError):
        RuntimeStore(link / "db.sqlite")
    assert not (actual / "db.sqlite").exists()


@native
def test_native_exclusive_creation_does_not_overwrite(tmp_path):
    path = tmp_path / "db.sqlite"
    RuntimeStore(path)
    original = path.read_bytes()
    with pytest.raises(StorageError):
        windows.private_file(path, create=True, exclusive=True)
    assert path.read_bytes() == original


@native
def test_native_real_journal_inherits_private_acl_and_allows_concurrent_check(tmp_path):
    path = tmp_path / "db.sqlite"
    store = RuntimeStore(path)
    with store.transaction() as db:
        assert db.execute("PRAGMA temp_store").fetchone()[0] == 2
        db.execute("INSERT INTO accounts VALUES('synthetic','{}',0)")
        journal = path.with_name(path.name + "-journal")
        assert journal.exists()
        # Metadata validation must not conflict with SQLite's existing RW handles.
        windows.private_file(path)
        windows.private_file(journal)
    assert not journal.exists()


@native
@pytest.mark.parametrize("factory", [MemoryStore, RuntimeStore, ControlStore])
def test_native_existing_instance_rechecks_permissions(tmp_path, factory):
    store = factory(tmp_path / "db.sqlite")
    set_private_permissions(store.path, public=True)
    transaction = store._transaction if factory is MemoryStore else store.transaction
    with pytest.raises(StorageError):
        with transaction():
            pytest.fail("Unsafe database reached transaction body")


@native
def test_native_deletion_authority_and_backup_acl_checked(tmp_path):
    store = MemoryStore(tmp_path / "db.sqlite")
    backup = store.backup(tmp_path / "backup.sqlite")
    windows.private_file(backup)
    set_private_permissions(store.deletion_path, public=True)
    with pytest.raises(StorageError):
        store.backup(tmp_path / "blocked.sqlite")
    assert not (tmp_path / "blocked.sqlite").exists()


@native
def test_native_rollback_journal_recovery_stays_private(tmp_path):
    # SQLite itself creates the journal; rollback leaves the original row count.
    path = tmp_path / "db.sqlite"
    RuntimeStore(path)
    db = sqlite3.connect(path)
    try:
        db.execute("INSERT INTO accounts VALUES('synthetic','{}',0)")
        windows.private_file(path)
        db.rollback()
        assert db.execute("SELECT count(*) FROM accounts").fetchone()[0] == 0
    finally:
        db.close()
    RuntimeStore(path)
