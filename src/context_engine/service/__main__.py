"""Explicit local-only launcher. Production TLS/identity provisioning remains operator-owned."""

import argparse
from pathlib import Path

import uvicorn

from ..memory import MemoryStore
from ..memory.codec import decode
from ..providers.credentials import private_bytes
from .app import create_app
from .auth import Authenticator, Principal
from .control import ControlStore


def configured_app(path):
    config = decode(private_bytes(Path(path), 65536).decode("utf-8"), maximum=65536)
    if set(config) != {"memory_path", "control_path", "system", "auth", "quota"}:
        raise ValueError("Invalid service configuration fields")
    if any(not Path(config[k]).is_absolute() for k in ("memory_path", "control_path")):
        raise ValueError("Service database paths must be absolute")
    memory_path, control_path = Path(config["memory_path"]), Path(config["control_path"])
    if control_path in (memory_path, memory_path.with_suffix(".deletions.sqlite")):
        raise ValueError("Service databases require distinct paths")
    if not isinstance(config["system"], str) or not 1 <= len(config["system"]) <= 16000:
        raise ValueError("Invalid system policy")
    spec = dict(config["auth"])
    credentials = {
        digest: (Principal(**entry["principal"]), entry["expires_at"])
        for digest, entry in spec.pop("service_credentials", {}).items()
    }
    subjects = {sub: Principal(**p) for sub, p in spec.pop("subjects", {}).items()}
    auth = Authenticator(service_credentials=credentials, subjects=subjects, **spec)
    control = ControlStore(config["control_path"], **config["quota"])
    return create_app(
        memory=MemoryStore(config["memory_path"]),
        control=control,
        auth=auth,
        system=config["system"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    try:
        app = configured_app(args.config)
    except Exception:
        parser.exit(2, "Invalid or unavailable private service configuration\n")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        limit_concurrency=16,
        timeout_keep_alive=5,
        server_header=False,
    )


if __name__ == "__main__":
    main()
