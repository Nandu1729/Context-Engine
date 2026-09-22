"""Explicit, bounded credential loading; no shell evaluation or secret-bearing errors."""

import os
import stat
from pathlib import Path

from ..errors import ContractError


def private_bytes(path, maximum):
    descriptor = None
    try:
        descriptor = os.open(
            Path(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and info.st_mode & 0o077):
            raise ContractError("Configuration must be a private regular file")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            raise ContractError("Private configuration exceeds its size limit")
        return raw
    except (OSError, TypeError, ValueError):
        raise ContractError("Cannot read private configuration") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def load_api_key(env_file=None):
    key = os.environ.get("GROQ_API_KEY")
    if env_file is not None:
        try:
            lines = private_bytes(env_file, 8192).decode("ascii").splitlines()
        except UnicodeError:
            raise ContractError("Credential file must contain a plain ASCII assignment") from None
        values = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.partition("=")
            if sep != "=" or name.strip() != "GROQ_API_KEY":
                raise ContractError("Credential file permits only GROQ_API_KEY and comments")
            value = value.strip()
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            values.append(value)
        if len(values) != 1:
            raise ContractError("Credential file requires exactly one GROQ_API_KEY assignment")
        if key and key != values[0]:
            raise ContractError("Environment and explicit credential file disagree")
        key = values[0]
    if (
        not key
        or len(key) > 4096
        or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in key)
    ):
        raise ContractError("Missing or invalid credential; value is never displayed")
    return key
