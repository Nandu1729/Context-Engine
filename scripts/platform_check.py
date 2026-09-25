"""Executable local platform probes; never a three-platform qualification claim."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from context_engine.config import BudgetConfig
from context_engine.evaluation.protocol import runtime_identity
from context_engine.memory import MemoryStore
from context_engine.memory.demo import memory_demo
from context_engine.models import Message, Role, Scope, Turn
from context_engine.service.demo import run_demo
from context_engine.service.workers import AssemblyWorkers


async def worker_probe():
    """Real isolated assembly,process cleanup and repeat capacity use."""
    with TemporaryDirectory(prefix="context-platform-worker-") as directory:
        root = Path(directory)
        memory = MemoryStore(root / "memory.sqlite")
        scope = Scope("platform-synthetic", "one")
        memory.create_scope(scope)
        memory.put_turn(
            Turn(
                "t1",
                scope,
                (Message("m1", Role.USER, "Database is PostgreSQL."),),
                timestamp=datetime.now(UTC),
            ),
            operation_id="one",
            expected_revision=0,
        )
        snap, expected = memory.assemble(
            scope, "Which database?", BudgetConfig(input_cap=900), system="Use evidence."
        )
        job = {
            "memory_path": str(memory.path),
            "deletion_path": str(memory.deletion_path),
            "scope": {"tenant_id": scope.tenant_id, "session_id": scope.session_id},
            "expected_revision": snap.revision,
            "question": "Which database?",
            "input_cap": 900,
            "system": "Use evidence.",
            "timeout": 10,
        }

        async def connected():
            await asyncio.Event().wait()

        workers = AssemblyWorkers(1)
        checks = []
        try:
            for _ in range(2):
                result = await workers.run(job, timeout=15, receive=connected)
                checks.append(result["request"] == expected.request.to_wire())
                checks.append(not workers._processes and not workers._running)
        finally:
            await workers.close()
        return {"api_sdk_worker_equivalent": all(checks), "completed_jobs": 2}


async def kill_probe():
    process = None
    try:
        # Synthetic subprocess only;no provider credentials inherited.
        env = {
            k: v
            for k, v in os.environ.items()
            if k in ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "TMPDIR")
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            "import time; print('ready',flush=True); time.sleep(30)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        async with asyncio.timeout(10):
            if (await process.stdout.readline()).rstrip(b"\r\n") != b"ready":
                raise RuntimeError("Child readiness failed")
            process.kill()
            await process.wait()
        return {"subprocess_killed_and_reaped": process.returncode is not None}
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()


def directory_sync_probe():
    with TemporaryDirectory(prefix="context-platform-sync-") as directory:
        fd = None
        try:
            fd = os.open(directory, os.O_RDONLY)
            os.fsync(fd)
            return True
        except OSError:
            return False
        finally:
            if fd is not None:
                os.close(fd)


def check():
    probes = {}
    tasks = {
        "memory_recovery": memory_demo,
        "assembly_worker": lambda: asyncio.run(worker_probe()),
        "subprocess_termination": lambda: asyncio.run(kill_probe()),
        "authenticated_loopback": run_demo,
    }
    for name, call in tasks.items():
        started = time.perf_counter()
        try:
            result = call()
            if name in ("memory_recovery", "authenticated_loopback"):
                passed = result["status"] == "PASS" and all(result["checks"].values())
            else:
                passed = all(v for v in result.values())
            probes[name] = {"passed": bool(passed)}
        except Exception as exc:
            # Never expose exception messages,paths,payloads or generated bearer tokens.
            probes[name] = {"passed": False, "error_type": type(exc).__name__}
        probes[name]["milliseconds"] = (time.perf_counter() - started) * 1000
    return {
        "status": "LOCAL_PROBES_PASS" if all(p["passed"] for p in probes.values()) else "FAIL",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "runtime": runtime_identity(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probes": probes,
        "research_runner_capabilities": {
            "fcntl_module_available": importlib.util.find_spec("fcntl") is not None,
            "directory_fsync_available": directory_sync_probe(),
        },
        "inference_calls": 0,
        "loopback_only": True,
        "qualification_complete": False,
        "caveat": "Local probes only;full suites/evidence on all target OSes still needed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("Output already exists")
    report = check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report, sort_keys=True))
    return int(report["status"] != "LOCAL_PROBES_PASS")


if __name__ == "__main__":
    raise SystemExit(main())
