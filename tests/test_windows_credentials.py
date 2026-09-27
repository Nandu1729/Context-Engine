"""Portable policy regressions plus real Windows ACL/handle enforcement tests."""

import os
from types import SimpleNamespace

import pytest
from private_files import set_private_permissions

from context_engine.errors import ContractError
from context_engine.providers import credentials
from context_engine.providers import windows_credentials as windows

USER = "S-1-5-21-1-2-3-1001"
OTHER = "S-1-5-21-1-2-3-1002"
EVERYONE = "S-1-1-0"


@pytest.mark.parametrize(
    "owner,entries,accepted",
    [
        (USER, [(0, 0, 1, USER)], True),
        ("S-1-5-18", [(0, 0, 1, USER)], True),
        ("S-1-5-32-544", [(0, 0, 1, USER)], True),
        (OTHER, [(0, 0, 1, USER)], False),
        (USER, None, False),  # Missing/null DACL permits everyone.
        (USER, [], True),  # Empty DACL grants nothing; native read must still succeed.
        (USER, [(0, 0, 1, EVERYONE)], False),
        (USER, [(0, 0x10, 1, EVERYONE)], False),  # Inherited grant also applies.
        (USER, [(0, 0x08, 1, EVERYONE)], True),  # Inherit-only does not.
        (USER, [(0, 0, 0x40000, OTHER)], False),  # WRITE_DAC is unsafe too.
        (USER, [(1, 0, 1, EVERYONE)], True),
        (USER, [(1, 0, 1, EVERYONE), (0, 0, 1, EVERYONE)], False),
        (USER, [(0, 0, 1, "S-1-5-18"), (0, 0, 1, "S-1-5-32-544")], True),
        (USER, [(5, 0, 1, USER)], False),  # Object ACE, no guessed semantics.
        (USER, [(9, 0, 1, USER)], False),  # Conditional/callback ACE.
        (USER, [(0, 0, 0, OTHER)], True),
    ],
)
def test_acl_policy(owner, entries, accepted):
    if accepted:
        windows.check_acl(owner, USER, entries)
    else:
        with pytest.raises(ContractError):
            windows.check_acl(owner, USER, entries)


@pytest.mark.parametrize("failure", [None, "init", "open", "validate", "read", "close"])
def test_reader_same_handle_fail_closed_and_cleanup(monkeypatch, failure):
    events = []

    def event(name):
        events.append(name)
        if failure == name:
            raise OSError("PRIVATE_PATH_AND_SECRET")

    handle = SimpleNamespace(Close=lambda: event("close"))

    class Reader:
        def __init__(self):
            event("init")

        def open(self, path):
            event("open")
            return handle

        def validate(self, candidate):
            assert candidate is handle
            event("validate")

        def read(self, candidate, size):
            assert candidate is handle and size == 9
            event("read")
            return b"synthetic"

    monkeypatch.setattr(windows, "WindowsReader", Reader)
    # Exercise public dispatch without changing global os.name / pathlib semantics.
    monkeypatch.setattr(credentials, "os", SimpleNamespace(name="nt"))
    if failure:
        with pytest.raises(ContractError) as exc:
            credentials.private_bytes("unused", 8)
        assert "PRIVATE" not in str(exc.value)
        assert exc.value.__suppress_context__
        if failure in ("init", "open", "validate"):
            assert "read" not in events
        if failure not in ("init", "open"):
            assert events[-1] == "close"
    else:
        with pytest.raises(ContractError, match="size limit"):
            credentials.private_bytes("unused", 8)
        assert events == ["init", "open", "validate", "read", "close"]


@pytest.mark.parametrize("attributes,kind", [(0x400, 1), (0x10, 1), (0, 2), (0, 3)])
def test_reparse_directory_and_device_rejected_before_acl_or_read(attributes, kind):
    reader = windows.WindowsReader.__new__(windows.WindowsReader)
    reader.file = SimpleNamespace(
        GetFileInformationByHandle=lambda _: (attributes,), GetFileType=lambda _: kind
    )
    with pytest.raises(ContractError, match="regular non-reparse"):
        reader.validate(object())


native_windows = pytest.mark.skipif(os.name != "nt", reason="Requires real Windows ACL APIs")


@pytest.mark.parametrize("length", [0, 8, 9])
def test_reader_returns_exact_bounded_bytes(monkeypatch, length):
    closed = []
    handle = SimpleNamespace(Close=lambda: closed.append(True))
    raw = b"x" * length
    monkeypatch.setattr(
        windows,
        "WindowsReader",
        lambda: SimpleNamespace(
            open=lambda _: handle, validate=lambda _: None, read=lambda _, size: raw[:size]
        ),
    )
    assert windows.private_bytes("unused", 9) == raw
    assert closed == [True]


@native_windows
@pytest.mark.parametrize("public", [False, True])
def test_native_acl_and_unicode_path(tmp_path, public):
    path = tmp_path / "配置.env"
    path.write_bytes(b"synthetic")
    set_private_permissions(path, public=public)
    if public:
        with pytest.raises(ContractError, match="private Windows ACL"):
            credentials.private_bytes(path, 9)
    else:
        assert credentials.private_bytes(path, 9) == b"synthetic"


@native_windows
@pytest.mark.parametrize("mode", ["null", "write_grant"])
def test_native_unsafe_dacls_rejected(tmp_path, mode):
    import win32con
    import win32security as security

    path = tmp_path / "credential"
    path.write_bytes(b"synthetic")
    set_private_permissions(path)
    acl = security.GetNamedSecurityInfo(
        str(path), security.SE_FILE_OBJECT, security.DACL_SECURITY_INFORMATION
    ).GetSecurityDescriptorDacl()
    if mode == "null":
        acl = None
    else:
        acl.AddAccessAllowedAceEx(
            security.ACL_REVISION,
            0,
            win32con.WRITE_DAC,
            security.ConvertStringSidToSid(EVERYONE),
        )
    security.SetNamedSecurityInfo(
        str(path),
        security.SE_FILE_OBJECT,
        security.DACL_SECURITY_INFORMATION | security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
    try:
        with pytest.raises(ContractError, match="private Windows ACL"):
            credentials.private_bytes(path, 9)
    finally:
        set_private_permissions(path)


@native_windows
def test_native_inherited_public_grant_rejected(tmp_path):
    import ntsecuritycon
    import win32con
    import win32security as security

    parent = tmp_path / "inherited"
    parent.mkdir()
    set_private_permissions(parent)
    acl = security.GetNamedSecurityInfo(
        str(parent), security.SE_FILE_OBJECT, security.DACL_SECURITY_INFORMATION
    ).GetSecurityDescriptorDacl()
    flags = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE
    # Test-only inheritance on a new synthetic directory, never an operator file.
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        acl.AddAccessAllowedAceEx(security.ACL_REVISION, flags, ace[1], ace[2])
    acl.AddAccessAllowedAceEx(
        security.ACL_REVISION,
        flags,
        ntsecuritycon.FILE_GENERIC_READ,
        security.ConvertStringSidToSid(EVERYONE),
    )
    security.SetNamedSecurityInfo(
        str(parent),
        security.SE_FILE_OBJECT,
        security.DACL_SECURITY_INFORMATION | security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
    path = parent / "credential"
    path.write_bytes(b"synthetic")
    inherited = security.GetNamedSecurityInfo(
        str(path), security.SE_FILE_OBJECT, security.DACL_SECURITY_INFORMATION
    ).GetSecurityDescriptorDacl()
    assert any(
        inherited.GetAce(i)[0][1] & security.INHERITED_ACE
        and security.ConvertSidToStringSid(inherited.GetAce(i)[2]) == EVERYONE
        for i in range(inherited.GetAceCount())
    )
    with pytest.raises(ContractError, match="private Windows ACL"):
        credentials.private_bytes(path, 9)
    set_private_permissions(path)
    set_private_permissions(parent)


@native_windows
def test_native_handle_blocks_replacement_and_write(tmp_path, monkeypatch):
    path = tmp_path / "credential"
    path.write_bytes(b"synthetic")
    set_private_permissions(path)
    validate = windows.WindowsReader.validate

    def validate_and_attempt_replace(self, handle):
        validate(self, handle)
        with pytest.raises(OSError):
            path.rename(tmp_path / "replaced")
        with pytest.raises(OSError):
            path.write_bytes(b"changed")

    monkeypatch.setattr(windows.WindowsReader, "validate", validate_and_attempt_replace)
    assert credentials.private_bytes(path, 9) == b"synthetic"
    path.rename(tmp_path / "closed")  # Handle released after success.


@native_windows
@pytest.mark.parametrize("problem", ["symlink", "directory", "missing", "oversize"])
def test_native_file_boundaries(tmp_path, problem):
    path = tmp_path / "credential"
    path.write_bytes(b"synthetic")
    set_private_permissions(path)
    if problem == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)  # No privilege-related skip; configured Windows CI must support it.
        path = link
    elif problem == "directory":
        path = tmp_path
    elif problem == "missing":
        path = tmp_path / "missing"
    with pytest.raises(ContractError):
        credentials.private_bytes(path, 8 if problem == "oversize" else 9)
    if problem == "oversize":
        path.rename(tmp_path / "closed")  # Handle released after failure too.
