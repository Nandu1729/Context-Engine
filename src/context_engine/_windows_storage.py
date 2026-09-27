"""Private local SQLite files and inheritable directory ACLs on Windows.

SQLite reopens paths, so ancestors, the effective user, SYSTEM and administrators
must be trusted. This is not a sandbox against those principals. Existing ACLs
are never rewritten. All native imports are lazy; no unchecked fallback exists.
"""

from glob import escape

from ._windows_security import TRUSTED_SYSTEM_SIDS, WindowsReader
from .errors import StorageError


class WindowsStorage(WindowsReader):
    def attributes(self):
        import pywintypes

        s = self.security
        acl = s.ACL()
        for sid in sorted(TRUSTED_SYSTEM_SIDS | {self.user()}):
            acl.AddAccessAllowedAceEx(
                s.ACL_REVISION, 0x01 | 0x02, 0x1F01FF, s.ConvertStringSidToSid(sid)
            )
        sd = s.SECURITY_DESCRIPTOR()
        sd.SetSecurityDescriptorDacl(True, acl, False)
        sd.SetSecurityDescriptorOwner(s.ConvertStringSidToSid(self.user()), False)
        sd.SetSecurityDescriptorControl(s.SE_DACL_PROTECTED, s.SE_DACL_PROTECTED)
        attributes = pywintypes.SECURITY_ATTRIBUTES()
        attributes.SECURITY_DESCRIPTOR = sd
        attributes.bInheritHandle = False
        return attributes

    def open_storage(self, path, *, create=False, exclusive=False):
        c = self.con

        def open_with(disposition, attributes):
            return self.file.CreateFile(
                str(path),
                c.READ_CONTROL,
                c.FILE_SHARE_READ | c.FILE_SHARE_WRITE | c.FILE_SHARE_DELETE,
                attributes,
                disposition,
                self.file.FILE_FLAG_OPEN_REPARSE_POINT | c.FILE_FLAG_BACKUP_SEMANTICS,
                None,
            )

        if create:
            try:
                return open_with(c.CREATE_NEW, self.attributes())
            except self.error as exc:
                if exclusive or exc.winerror not in (80, 183):
                    raise
        return open_with(c.OPEN_EXISTING, None)

    def directory(self, path, *, create):
        try:
            handle = self.open_storage(path)
        except self.error as exc:
            if not create or exc.winerror not in (2, 3) or path == path.parent:
                raise
            # Only missing directories get new ACLs. Ancestors remain trusted.
            self.make_directory(path)
            handle = self.open_storage(path)
        try:
            self.validate(handle, directory=True)
        finally:
            handle.Close()

    def make_directory(self, path):
        # Security is applied at creation, never via a later permission rewrite.
        if not path.parent.exists():
            self.make_directory(path.parent)
        try:
            self.file.CreateDirectory(str(path), self.attributes())
        except self.error as exc:
            if exc.winerror != 183:  # Concurrent creator: validate below.
                raise

    def file_boundary(self, path, *, create=False, exclusive=False, optional=False):
        try:
            handle = self.open_storage(path, create=create, exclusive=exclusive)
        except self.error as exc:
            if optional and exc.winerror == 2:
                return
            raise
        try:
            self.validate(handle)
            if self.file.GetFileInformationByHandle(handle)[7] != 1:
                raise StorageError("Private storage cannot have hard-link aliases")
        finally:
            handle.Close()


def private_file(path, *, create=False, exclusive=False):
    """Validate the DB, parent inheritance and any existing SQLite sidecars."""
    try:
        boundary = WindowsStorage()
        path = boundary.local_path(path)
        boundary.directory(path.parent, create=create)
        boundary.file_boundary(path, create=create, exclusive=exclusive)
        for suffix in ("-journal", "-wal", "-shm"):
            boundary.file_boundary(path.with_name(path.name + suffix), optional=True)
        # Multi-database DELETE transactions can leave super-journals.
        for sidecar in path.parent.glob(escape(path.name) + "-mj*"):
            boundary.file_boundary(sidecar, optional=True)
        return path
    except Exception:
        raise StorageError(
            "Storage requires private local Windows files and directory ACLs"
        ) from None
