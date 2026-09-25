"""Real subprocess termination/reaping, capacity and transactional recovery tests."""

import asyncio
import hashlib
import json
import os
import sys
import time

import pytest

from context_engine.errors import ContractError, MemoryIntegrityError, WorkCancelled
from context_engine.memory import MemoryStore
from context_engine.models import Scope
from context_engine.service import workers as module
from context_engine.service.app import ServiceLimits, create_app
from context_engine.service.auth import AccessError, Authenticator, Principal
from context_engine.service.control import ControlStore
from context_engine.service.workers import AssemblyWorkers


async def connected():
    await asyncio.Event().wait()


async def started(workers):
    async with asyncio.timeout(5):
        while not workers._processes:
            await asyncio.sleep(0.005)
    return next(iter(workers._processes))


def command(monkeypatch, code):
    monkeypatch.setattr(module, "worker_command", lambda: (sys.executable, "-I", "-c", code))


@pytest.mark.parametrize("mode", ["timeout", "disconnect", "task_cancel", "shutdown"])
def test_uncooperative_process_is_killed_reaped_and_slot_reusable(monkeypatch, mode):
    command(monkeypatch, "while True: pass")

    async def exercise():
        workers = AssemblyWorkers(1)
        signal = asyncio.Event()

        async def receive():
            await signal.wait()
            return {"type": "http.disconnect"}

        task = asyncio.create_task(
            workers.run({}, timeout=0.25 if mode == "timeout" else 5, receive=receive)
        )
        process = await started(workers)
        if mode == "disconnect":
            signal.set()
        elif mode == "task_cancel":
            task.cancel()
        elif mode == "shutdown":
            await workers.close()
        with pytest.raises((WorkCancelled, asyncio.CancelledError, AccessError)):
            await task
        assert process.returncode is not None
        assert not workers._processes
        if os.name == "posix":
            with pytest.raises(ProcessLookupError):
                os.kill(process.pid, 0)
        command(monkeypatch, 'print(\'{"result":{"ok":true}}\')')
        if mode == "shutdown":
            with pytest.raises(AccessError, match="assembly_busy"):
                await workers.run({}, timeout=5, receive=connected)
        else:
            assert await workers.run({}, timeout=5, receive=connected) == {"ok": True}
        await workers.close()

    begin = time.monotonic()
    asyncio.run(exercise())
    assert time.monotonic() - begin < 10


def test_capacity_rejected_without_spawning_and_recovers(monkeypatch):
    command(monkeypatch, "while True: pass")

    async def exercise():
        workers = AssemblyWorkers(1)
        first = asyncio.create_task(workers.run({}, timeout=5, receive=connected))
        process = await started(workers)
        with pytest.raises(AccessError) as caught:
            await workers.run({}, timeout=5, receive=connected)
        assert caught.value.code == "assembly_busy"
        assert workers._processes == {process}
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not workers._processes

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "code",
    [
        "print('x'*2000001)",
        "print('not json')",
        "raise RuntimeError('SECRET')",
        "import sys\nwhile True: sys.stdout.buffer.write(b'x'*65536);sys.stdout.buffer.flush()",
    ],
)
def test_oversized_malformed_or_failed_worker_does_not_leak_or_hold_slot(monkeypatch, code):
    command(monkeypatch, code)

    async def exercise():
        workers = AssemblyWorkers(1)
        with pytest.raises((AccessError, MemoryIntegrityError)) as caught:
            await workers.run({}, timeout=5, receive=connected)
        assert "SECRET" not in str(caught.value)
        assert not workers._processes
        command(monkeypatch, 'print(\'{"result":{"ok":true}}\')')
        assert await workers.run({}, timeout=5, receive=connected) == {"ok": True}

    asyncio.run(exercise())


def test_startup_cancellation_reaps_late_child(monkeypatch):
    command(monkeypatch, "while True: pass")
    original = asyncio.create_subprocess_exec
    observed = []

    async def slow_start(*args, **kwargs):
        process = await original(*args, **kwargs)
        observed.append(process)
        await asyncio.sleep(0.1)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_start)

    async def exercise():
        workers = AssemblyWorkers(1)
        with pytest.raises(WorkCancelled):
            await workers.run({}, timeout=0.01, receive=connected)
        assert len(observed) == 1 and observed[0].returncode is not None
        assert not workers._processes

    asyncio.run(exercise())


def test_killed_transaction_rolls_back_and_store_reopens(tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite"
    marker = tmp_path / "ready"
    store = MemoryStore(path)
    scope = Scope("alpha", "one")
    store.create_scope(scope)
    command(
        monkeypatch,
        """
import json,sys
from pathlib import Path
from context_engine.memory import MemoryStore
job=json.load(sys.stdin)
store=MemoryStore(job['path'])
with store._transaction() as db:
    db.execute('UPDATE scopes SET revision=999')
    Path(job['marker']).write_text('transaction open')
    while True: pass
""",
    )

    async def receive():
        while not marker.exists():
            await asyncio.sleep(0.01)
        return {"type": "http.disconnect"}

    async def exercise():
        workers = AssemblyWorkers(1)
        with pytest.raises(WorkCancelled):
            await workers.run(
                {"path": str(path), "marker": str(marker)}, timeout=5, receive=receive
            )
        assert not workers._processes

    asyncio.run(exercise())
    assert marker.exists()  # The kill happened inside, not before, the transaction.
    assert MemoryStore(path).snapshot(scope).revision == 0
    assert store.snapshot(scope).revision == 0


def test_worker_does_not_inherit_credentials(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "SYNTHETIC-SECRET")
    monkeypatch.setenv("GEMINI_API_KEY", "SYNTHETIC-SECRET")
    command(monkeypatch, "import os,json;print(json.dumps({'result':dict(os.environ)}))")

    async def exercise():
        workers = AssemblyWorkers(1)
        result = await workers.run({}, timeout=5, receive=connected)
        assert "SYNTHETIC-SECRET" not in json.dumps(result)

    asyncio.run(exercise())


@pytest.mark.parametrize("value", [0, 9, True, 1.5, "2"])
def test_worker_capacity_configuration_is_bounded(value):
    with pytest.raises(ContractError):
        ServiceLimits(assembly_workers=value)


def test_asgi_disconnect_reaches_worker_and_is_audited(tmp_path, monkeypatch):
    command(monkeypatch, "while True: pass")
    memory = MemoryStore(tmp_path / "memory.sqlite")
    memory.create_scope(Scope("alpha", "one"))
    control = ControlStore(tmp_path / "control.sqlite")
    secret = "ce_" + "a" * 64
    auth = Authenticator(
        service_credentials={
            hashlib.sha256(secret.encode()).hexdigest(): (
                Principal("admin", "alpha", "admin", ("*",)),
                int(time.time()) + 60,
            )
        }
    )
    app = create_app(memory=memory, control=control, auth=auth)

    async def exercise():
        delivered = False

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "more_body": False,
                    "body": b'{"question":"Q?","expected_revision":0}',
                }
            await started(app.state.assembly_workers)
            return {"type": "http.disconnect"}

        sent = []

        async def send(event):
            sent.append(event)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/v1/tenants/alpha/sessions/one/context",
                "query_string": b"",
                "root_path": "",
                "server": ("test", 80),
                "client": ("test", 1234),
                "headers": [
                    (b"authorization", ("Bearer " + secret).encode()),
                    (b"content-type", b"application/json"),
                ],
            },
            receive,
            send,
        )
        assert next(e["status"] for e in sent if e["type"] == "http.response.start") == 503
        assert not app.state.assembly_workers._processes
        assert control.events("alpha", 0, 50)[-1]["outcome"] == "work_cancelled"
        await app.state.assembly_workers.close()

    asyncio.run(exercise())


def test_shutdown_during_spawn_waits_for_late_child(monkeypatch):
    command(monkeypatch, "while True: pass")
    original = asyncio.create_subprocess_exec
    observed = []

    async def slow_start(*args, **kwargs):
        process = await original(*args, **kwargs)
        observed.append(process)
        await asyncio.sleep(0.1)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_start)

    async def exercise():
        workers = AssemblyWorkers(1)
        task = asyncio.create_task(workers.run({}, timeout=5, receive=connected))
        async with asyncio.timeout(5):
            while not observed:
                await asyncio.sleep(0.005)
        await workers.close()
        assert observed[0].returncode is not None
        assert not workers._processes and not workers._running
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
