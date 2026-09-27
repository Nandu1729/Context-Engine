"""Fail-closed Windows credential reads; never change an operator's ACL.

Parent directories and local administrators are trusted, as on POSIX. Only the
effective user, LocalSystem and built-in Administrators may own the file or have
applicable allow ACEs. Complex/unknown ACE forms are rejected, not approximated.
Native imports are lazy so this module is harmless on non-Windows platforms.
"""

from pathlib import Path

from .errors import ContractError

TRUSTED_SYSTEM_SIDS = frozenset({"S-1-5-18", "S-1-5-32-544"})


def check_acl(owner, user, entries):
    """Evaluate normalized (type, flags, mask, SID) ACEs, including inherited ACEs."""
    trusted = TRUSTED_SYSTEM_SIDS | {user}
    if not user or owner not in trusted or entries is None:
        raise ContractError("Configuration must have a private Windows ACL")
    for kind, flags, mask, sid in entries:
        if flags & 0x08:  # INHERIT_ONLY_ACE does not apply to the file itself.
            continue
        if kind not in (0, 1):  # Standard allow/deny only; fail closed on complex ACEs.
            raise ContractError("Unsupported Windows configuration ACL")
        # A deny ACE never excuses a broad allow. This intentionally conservative
        # policy avoids pretending to implement Windows' effective-access algorithm.
        if kind == 0 and mask and sid not in trusted:
            raise ContractError("Configuration must have a private Windows ACL")


class WindowsReader:
    def __init__(self):
        import pywintypes
        import win32api
        import win32con
        import win32file
        import win32security

        self.error = pywintypes.error
        self.api, self.con = win32api, win32con
        self.file, self.security = win32file, win32security

    def local_path(self, path):
        path = Path(path).absolute()
        # Exclude device/UNC namespaces, alternate streams and remote drives before
        # CreateFile can open a pipe/device or initiate a remote connection.
        if (
            len(path.drive) != 2
            or path.drive[1] != ":"
            or not path.drive[0].isascii()
            or not path.drive[0].isalpha()
            or path.is_reserved()
            or any(
                any(char in part for char in ':<>"|?*') or part.endswith((".", " "))
                for part in path.parts[1:]
            )
            or self.file.GetDriveType(path.anchor) != 3  # DRIVE_FIXED
        ):
            raise ContractError("Configuration requires a local disk file")
        return path

    def open(self, path):
        c = self.con
        path = self.local_path(path)
        return self.file.CreateFile(
            str(path),
            c.GENERIC_READ | c.READ_CONTROL,
            c.FILE_SHARE_READ,  # No concurrent writer or delete/rename handle.
            None,  # Non-inheritable handle; no ACL mutation.
            c.OPEN_EXISTING,
            self.file.FILE_FLAG_OPEN_REPARSE_POINT | c.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

    def user(self):
        s, c = self.security, self.con
        try:
            token = s.OpenThreadToken(self.api.GetCurrentThread(), c.TOKEN_QUERY, True)
        except self.error as exc:
            if exc.winerror != 1008:  # ERROR_NO_TOKEN only; other errors fail closed.
                raise
            token = s.OpenProcessToken(self.api.GetCurrentProcess(), c.TOKEN_QUERY)
        try:
            return s.ConvertSidToStringSid(s.GetTokenInformation(token, s.TokenUser)[0])
        finally:
            token.Close()

    def validate(self, handle, *, directory=False):
        # Validate the opened object, not a path that can be replaced before reading.
        attributes = self.file.GetFileInformationByHandle(handle)[0]
        if (
            self.file.GetFileType(handle) != 1
            or attributes & 0x400
            or bool(attributes & 0x10) != directory
        ):
            raise ContractError("Configuration must be a regular non-reparse file")
        s = self.security
        sd = s.GetSecurityInfo(
            handle, s.SE_FILE_OBJECT, s.OWNER_SECURITY_INFORMATION | s.DACL_SECURITY_INFORMATION
        )
        owner = s.ConvertSidToStringSid(sd.GetSecurityDescriptorOwner())
        acl = sd.GetSecurityDescriptorDacl()
        entries = None
        if acl is not None:
            entries = []
            for index in range(acl.GetAceCount()):
                ace = acl.GetAce(index)
                kind, flags = ace[0]
                # Object/callback ACE layouts differ; do not misinterpret their SID.
                sid = s.ConvertSidToStringSid(ace[2]) if kind in (0, 1) else None
                entries.append((kind, flags, ace[1], sid))
        user = self.user()
        check_acl(owner, user, entries)
        if directory:
            # Include inherit-only grants: SQLite-created journals inherit them.
            check_acl(owner, user, [(k, f & ~0x08, m, s) for k, f, m, s in entries])
            if not any(
                k == 0 and f & 0x01 and s == user and m & 0x1F01FF == 0x1F01FF
                for k, f, m, s in entries
            ):
                raise ContractError("Storage directory requires private file inheritance")

    def read(self, handle, size):
        return self.file.ReadFile(handle, size)[1]
