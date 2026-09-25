"""Bounded, disposable assembly subprocesses; no thread-cancellation illusion."""

import asyncio
import os
import sys
import threading

from ..errors import WorkCancelled
from ..memory.codec import decode, encode
from .auth import AccessError

MAX_OUTPUT = 2_000_000


def worker_command():
    return (sys.executable, "-I", "-m", "context_engine.service.worker")


class AssemblyWorkers:
    """Per-service-process capacity; no pending queue and no reusable tenant worker."""

    def __init__(self, capacity=2):
        self._slots = threading.BoundedSemaphore(capacity)
        self._processes = set()
        self._running = set()
        self._closed = False

    async def close(self):
        self._closed = True
        tasks = tuple(self._running)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _exchange(self, process, payload):
        async def write():
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()

        writer = asyncio.create_task(write())
        try:
            result = bytearray()
            while chunk := await process.stdout.read(65536):
                result.extend(chunk)
                if len(result) > MAX_OUTPUT:
                    raise AccessError(503, "assembly_output_limit")
            await writer
            await process.wait()
            if process.returncode != 0:
                raise AccessError(503, "assembly_worker_failed")
            return decode(result.decode("utf-8"), maximum=MAX_OUTPUT)
        finally:
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)

    async def run(self, job, *, timeout, receive):
        if self._closed or not self._slots.acquire(blocking=False):
            raise AccessError(503, "assembly_busy")
        owner = asyncio.current_task()
        self._running.add(owner)
        process = None
        spawn = None
        tasks = []

        async def disconnected():
            while True:
                if (await receive())["type"] == "http.disconnect":
                    raise WorkCancelled("Client disconnected")

        async def cleanup():
            nonlocal process
            try:
                if process is None and spawn is not None:
                    # create_subprocess_exec may finish after its caller is cancelled.
                    process = await spawn
                    self._processes.add(process)
                for task in tasks:
                    task.cancel()
                if process is not None and process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await asyncio.gather(*tasks, return_exceptions=True)
                if process is not None:
                    # A killed writer can leave stdout paused at its high-water
                    # mark. Discard buffered bytes so pipe closure cannot block wait().
                    while await process.stdout.read(65536):
                        pass
                    await process.wait()  # Reap before capacity can be reused.
            finally:
                if process is None or process.returncode is not None:
                    self._processes.discard(process)
                    self._slots.release()
                    self._running.discard(owner)

        try:
            payload = encode(job).encode()
            if len(payload) > 262144:
                raise AccessError(503, "assembly_input_limit")
            async with asyncio.timeout(timeout):
                # Never inherit API keys/service credentials into the computation worker.
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if k
                    in (
                        "PATH",
                        "SYSTEMROOT",
                        "SystemRoot",
                        "TMPDIR",
                        "TEMP",
                        "TMP",
                        "TIKTOKEN_CACHE_DIR",
                    )
                }
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        *worker_command(),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        env=env,
                    )
                )
                process = await asyncio.shield(spawn)
                self._processes.add(process)
                if self._closed:
                    raise WorkCancelled("Service is shutting down")
                exchange = asyncio.create_task(self._exchange(process, payload))
                monitor = asyncio.create_task(disconnected())
                tasks = [exchange, monitor]
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                if monitor in done:
                    await monitor
                response = await exchange
                if set(response) == {"error", "status"}:
                    if response["status"] not in (409, 422, 503):
                        raise AccessError(503, "assembly_worker_failed")
                    raise AccessError(response["status"], response["error"])
                if set(response) != {"result"} or not isinstance(response["result"], dict):
                    raise AccessError(503, "assembly_worker_failed")
                return response["result"]
        except TimeoutError:
            raise WorkCancelled("Assembly deadline exceeded") from None
        except (OSError, UnicodeError, BrokenPipeError):
            raise AccessError(503, "assembly_worker_failed") from None
        finally:
            reaper = asyncio.create_task(cleanup())
            try:
                await asyncio.shield(reaper)
            except asyncio.CancelledError:
                await asyncio.shield(reaper)
                raise
