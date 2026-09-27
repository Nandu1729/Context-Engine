"""Fail-closed Windows credential reads; never change an operator's ACL."""

from .._windows_security import WindowsReader, check_acl  # noqa: F401
from ..errors import ContractError


def private_bytes(path, maximum):
    """Bounded bytes from the same verified handle; all OS errors are redacted."""
    try:
        reader = WindowsReader()
        handle = reader.open(path)
        try:
            reader.validate(handle)
            raw = reader.read(handle, maximum + 1)
            if len(raw) > maximum:
                raise ContractError("Private configuration exceeds its size limit")
            return raw
        finally:
            handle.Close()
    except ContractError:
        raise
    except Exception:
        raise ContractError("Cannot read private Windows configuration") from None
