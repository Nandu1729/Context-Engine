"""Private stdin/stdout assembly worker; no HTTP, auth, provider or secret loading."""

import sys
import time

from ..config import BudgetConfig
from ..errors import ContextEngineError, MemoryConflict
from ..memory import MemoryStore
from ..memory.codec import decode, encode
from ..models import Scope
from ..work import DeadlineCancellation


def execute(job):
    memory = MemoryStore(job["memory_path"], deletion_path=job["deletion_path"])
    scope = Scope(**job["scope"])
    before = memory.snapshot(scope)
    if before.revision != job["expected_revision"]:
        raise MemoryConflict("Assembly snapshot changed")
    snapshot, result = memory.assemble(
        scope,
        job["question"],
        BudgetConfig(input_cap=job["input_cap"]),
        system=job["system"],
        cancellation=DeadlineCancellation(time.monotonic() + job["timeout"]),
    )
    if snapshot.snapshot_id != before.snapshot_id:
        raise MemoryConflict("Assembly snapshot changed")
    memory.assert_current(snapshot)
    return {
        "snapshot_id": snapshot.snapshot_id,
        "revision": snapshot.revision,
        "request": result.request.to_wire(),
        "estimated_tokens": result.diagnostics.estimate.estimated_tokens,
        "provider_accounting_verified": False,
    }


def main():
    try:
        job = decode(sys.stdin.buffer.read(262145).decode("utf-8"), maximum=262144)
        response = {"result": execute(job)}
    except ContextEngineError as exc:
        status = 409 if isinstance(exc, MemoryConflict) else 422
        if exc.code in (
            "runtime_storage_error",
            "memory_integrity_error",
            "tokenizer_unavailable",
            "work_cancelled",
        ):
            status = 503
        response = {"error": exc.code, "status": status}
    except Exception:
        response = {"error": "assembly_worker_failed", "status": 503}
    sys.stdout.write(encode(response))


if __name__ == "__main__":
    main()
