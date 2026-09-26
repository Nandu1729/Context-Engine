"""C09 resource bounds and cooperative cancellation; synthetic data only, no provider calls."""

import asyncio
import hashlib
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from context_engine.config import BudgetConfig, RetrievalConfig
from context_engine.context import ContextCarrier
from context_engine.errors import ContractError, MemoryIntegrityError, WorkCancelled
from context_engine.layers import CapLayer, PinLayer, RetrieveLayer, WindowLayer
from context_engine.layers.common import history_digest
from context_engine.memory import MemoryStore
from context_engine.models import KeyedPins, Message, Role, Scope, Turn
from context_engine.pipeline import _finalize, assemble_context
from context_engine.service.app import Boundary, ServiceLimits, create_app
from context_engine.service.auth import Authenticator, Principal
from context_engine.service.control import ControlStore
from context_engine.tokens import TiktokenCounter
from context_engine.work import DeadlineCancellation, validate_cancellation

AT = datetime(2026, 9, 22, tzinfo=UTC)
SCOPE = Scope("bounds-tenant", "bounds-session")
BASE = "/v1/tenants/bounds-tenant/sessions/bounds-session"


class CountingCancellation:
    """Deterministic cooperative token: raises once its check budget is reached."""

    def __init__(self, budget=1):
        self.remaining = budget
        self.checks = 0

    def check(self):
        self.checks += 1
        if self.checks >= self.remaining:
            raise WorkCancelled("synthetic cancellation for test")


def token():
    return "ce_" + hashlib.sha256(b"bounds").hexdigest()


def headers():
    return {"Authorization": "Bearer " + token()}


def turn(index, *, content=None, revision=1):
    text = content or (f"Turn {index}: " + "routine telemetry remained under review. " * 12)
    return Turn(f"t{index}", SCOPE, (Message(f"m{index}", Role.USER, text),), revision, AT)


def history(count=8):
    return tuple(turn(i) for i in range(1, count + 1))


@pytest.fixture
def service(tmp_path):
    auth = Authenticator(
        service_credentials={
            hashlib.sha256(token().encode()).hexdigest(): (
                Principal("admin", "bounds-tenant", "admin", ("*",)),
                int(time.time()) + 600,
            )
        }
    )
    memory = MemoryStore(tmp_path / "memory.sqlite")
    control = ControlStore(tmp_path / "control.sqlite", rpm=1000)
    app = create_app(memory=memory, control=control, auth=auth)
    with TestClient(app) as client:
        yield client, memory, control


def payload(**changes):
    body = {
        "question": "Which partition carried the blame?",
        "expected_revision": 0,
        "input_cap": 900,
    }
    body.update(changes)
    return body


def populated(service):
    client, _, _ = service
    assert client.put(BASE, headers=headers()).status_code == 200
    result = client.post(
        BASE + "/turns",
        headers=headers(),
        json={
            "id": "t1",
            "operation_id": "one",
            "expected_revision": 0,
            "timestamp": AT.isoformat(),
            "messages": [{"id": "m1", "role": "user", "content": "Partition shard-19 failed."}],
        },
    )
    assert result.status_code == 200, result.text
    return result.json()["revision"]


# --- cancellation contract -------------------------------------------------


def test_invalid_token_is_a_contract_error():
    class NonCallableCheck:
        check = 1

    for bad in (object(), "token", 3, NonCallableCheck()):
        with pytest.raises(ContractError):
            validate_cancellation(bad)
        with pytest.raises(ContractError):
            assemble_context(
                (),
                "Question?",
                KeyedPins(SCOPE),
                BudgetConfig(),
                system="Use evidence.",
                cancellation=bad,
            )


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), "1", None, True])
def test_invalid_deadline_values_are_rejected(deadline):
    with pytest.raises(ContractError):
        DeadlineCancellation(deadline)


def test_deadline_uses_injected_clock_and_stops_work():
    clock = [100.0]
    cancellation = DeadlineCancellation(105.0, clock=lambda: clock[0])
    cancellation.check()  # Before the deadline.
    clock[0] = 105.0
    with pytest.raises(WorkCancelled):
        cancellation.check()


def test_assemble_context_cancellation_preserves_original_history():
    turns = history(6)
    before = history_digest(turns)
    with pytest.raises(WorkCancelled):
        assemble_context(
            turns,
            "Which partition carried the blame?",
            KeyedPins(SCOPE),
            BudgetConfig(input_cap=900),
            system="Use supplied evidence.",
            at=AT,
            token_counter=TiktokenCounter(),
            cancellation=CountingCancellation(budget=2),
        )
    assert history_digest(turns) == before
    assert [t.turn_id for t in turns] == [f"t{i}" for i in range(1, 7)]


def test_uncancelled_token_produces_identical_assembly():
    turns = history(6)
    pins = KeyedPins(SCOPE)
    counter = TiktokenCounter()
    plain = assemble_context(
        turns,
        "Question?",
        pins,
        BudgetConfig(input_cap=900),
        system="S.",
        at=AT,
        token_counter=counter,
    )
    token_used = CountingCancellation(budget=10**6)
    guarded = assemble_context(
        turns,
        "Question?",
        pins,
        BudgetConfig(input_cap=900),
        system="S.",
        at=AT,
        token_counter=counter,
        cancellation=token_used,
    )
    assert guarded.request == plain.request
    assert guarded.diagnostics.estimate == plain.diagnostics.estimate
    assert token_used.checks > 0


def test_finalizer_honours_cancellation_after_layers():
    turns = history(8)
    counter = TiktokenCounter()
    carrier = ContextCarrier(SCOPE, turns, turns, KeyedPins(SCOPE), Message("q", Role.USER, "Q?"))
    context = PinLayer(counter, BudgetConfig(input_cap=900), "S.", AT).apply(
        CapLayer(counter).apply(carrier)
    )
    context = WindowLayer(counter).apply(RetrieveLayer(counter).apply(context))
    budget = BudgetConfig(input_cap=context.plan.input_allowance)
    cancelled = replace(context, cancellation=CountingCancellation(budget=1))
    with pytest.raises(WorkCancelled):
        _finalize(cancelled, counter, budget)
    request, blocks, estimate, *_ = _finalize(context, counter, budget)
    assert estimate.estimated_tokens <= budget.input_allowance and blocks


def test_memory_assemble_cancellation_leaves_store_unchanged(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    memory.create_scope(SCOPE)
    for index in range(1, 7):
        memory.put_turn(turn(index), operation_id=f"op-{index}", expected_revision=index - 1)
    before = memory.snapshot(SCOPE)
    with pytest.raises(WorkCancelled):
        memory.assemble(
            SCOPE,
            "Which partition carried the blame?",
            BudgetConfig(input_cap=900),
            system="Use evidence.",
            cancellation=CountingCancellation(budget=1),
        )
    after = memory.snapshot(SCOPE)
    assert after == before
    with memory._transaction() as db:
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0


def test_index_batch_cancellation_rolls_back_and_resumes(tmp_path, monkeypatch):
    memory = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    memory.create_scope(SCOPE)
    for index in range(1, 5):
        memory.put_turn(turn(index), operation_id=f"op-{index}", expected_revision=index - 1)
    snapshot = memory.snapshot(SCOPE)
    import context_engine.memory.store as module

    original = module.chunk_turns
    processed = []

    def cancel_second(turns, config, **kwargs):
        if processed:
            raise WorkCancelled("second turn cancelled")
        chunks = original(turns, config, **kwargs)
        processed.append(turns[0].turn_id)
        return chunks

    # Cancel inside the batch transaction after the first turn is processed.
    monkeypatch.setattr(module, "chunk_turns", cancel_second)
    with pytest.raises(WorkCancelled):
        memory.index_batch(snapshot, batch_size=4)
    assert processed == ["t1"]
    with memory._transaction() as db:
        assert db.execute("SELECT count(*) FROM coverage").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
    monkeypatch.setattr(module, "chunk_turns", original)
    assert memory.index_batch(snapshot, batch_size=4)["status"] == "READY"
    assert memory.chunk_index(snapshot).chunks


def test_cap_checks_cancellation_inside_one_large_message():
    from context_engine.layers.cap import bounded_piece

    cancellation = CountingCancellation(budget=3)
    with pytest.raises(WorkCancelled):
        bounded_piece("long content " * 1000, 20, TiktokenCounter(), cancellation=cancellation)
    assert cancellation.checks == 3


def test_chunking_checks_cancellation_inside_one_large_message():
    from context_engine.layers.retrieve import chunk_turns

    cancellation = CountingCancellation(budget=5)
    with pytest.raises(WorkCancelled):
        chunk_turns(
            (turn(1, content="text " * 1000),), RetrievalConfig(), cancellation=cancellation
        )
    assert cancellation.checks == 5


def test_index_batch_cancellation_before_commit_rolls_back(tmp_path, monkeypatch):
    import context_engine.memory.store as module

    memory = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    memory.create_scope(SCOPE)
    memory.put_turn(turn(1), operation_id="one", expected_revision=0)
    snapshot = memory.snapshot(SCOPE)
    expired = [False]
    cancellation = DeadlineCancellation(1, clock=lambda: 2 if expired[0] else 0)
    original = module.chunk_turns

    def expire_after_chunking(*args, **kwargs):
        chunks = original(*args, **kwargs)
        expired[0] = True
        return chunks

    monkeypatch.setattr(module, "chunk_turns", expire_after_chunking)
    with pytest.raises(WorkCancelled):
        memory.index_batch(snapshot, cancellation=cancellation)
    with memory._transaction() as db:
        assert db.execute("SELECT count(*) FROM coverage").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
    assert memory.snapshot(SCOPE).history == snapshot.history


def test_index_batch_accepts_only_valid_tokens(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    memory.create_scope(SCOPE)
    snapshot = memory.snapshot(SCOPE)
    with pytest.raises(ContractError):
        memory.index_batch(snapshot, cancellation="not-a-token")


# --- service-level limits and request bounds -------------------------------


def test_service_limits_validation():
    assert ServiceLimits().assembly_deadline_seconds == 30.0
    for bad in (0, -1, 301, float("nan"), True, "30"):
        with pytest.raises(ContractError):
            ServiceLimits(assembly_deadline_seconds=bad)
    with pytest.raises(ContractError):
        create_app(memory=None, control=None, auth=None, limits="fail")


def test_service_context_cancellation_returns_content_free_503(service, monkeypatch):
    client, _, control = service
    revision = populated(service)
    import context_engine.service.app as module

    original = module.DeadlineCancellation

    def pre_cancelled(deadline, clock=time.monotonic):
        return original(deadline - 10**6, clock=clock)

    monkeypatch.setattr(module, "DeadlineCancellation", pre_cancelled)
    result = client.post(
        BASE + "/context", headers=headers(), json=payload(expected_revision=revision)
    )
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "work_cancelled"
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    events = control.events("bounds-tenant", 0, 50)
    assert events[-1]["outcome"] == "work_cancelled"
    assert "shard-19" not in json.dumps(events)


def test_service_default_limits_still_assemble(service):
    client, _, _ = service
    revision = populated(service)
    result = client.post(
        BASE + "/context", headers=headers(), json=payload(expected_revision=revision)
    )
    assert result.status_code == 200, result.text
    assert result.json()["estimated_tokens"] <= 900
    assert "work_cancelled" not in json.dumps(result.json())


def test_oversized_body_is_rejected_after_authentication(service):
    client, _, _ = service
    client.put(BASE, headers=headers())
    oversize = b"a" * 300_000
    assert client.post(BASE + "/turns", headers=headers(), content=oversize).status_code == 413
    # Authentication precedes body handling: no credential means no body work.
    assert client.post(BASE + "/turns", content=oversize).status_code == 401


def test_streamed_body_boundary_caps_bytes_and_requires_identity():
    reached = []

    async def app(scope, receive, send):  # pragma: no cover - must never be reached
        reached.append(1)

    auth = Authenticator(
        service_credentials={
            hashlib.sha256(token().encode()).hexdigest(): (
                Principal("admin", "bounds-tenant", "admin", ("*",)),
                int(time.time()) + 600,
            )
        }
    )
    boundary = Boundary(app, auth=auth, maximum=64)

    def driver(authorization):
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 40, "more_body": True},
                {"type": "http.request", "body": b"x" * 40, "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(chunks)

        async def send(event):
            sent.append(event)

        scope = {
            "type": "http",
            "headers": [(b"authorization", authorization)] if authorization else [],
            "state": {},
        }
        asyncio.run(boundary(scope, receive, send))
        return sent

    unauthorised = driver(None)
    assert unauthorised[0]["status"] == 401 and not reached
    rejected = driver(b"Bearer " + token().encode())
    assert rejected[0]["status"] == 413 and not reached


def test_slow_body_times_out_with_408(monkeypatch):
    class ImmediateTimeout:
        def __init__(self, _):
            pass

        async def __aenter__(self):
            raise TimeoutError

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(asyncio, "timeout", ImmediateTimeout)
    auth = Authenticator(
        service_credentials={
            hashlib.sha256(token().encode()).hexdigest(): (
                Principal("admin", "bounds-tenant", "admin", ("*",)),
                int(time.time()) + 600,
            )
        }
    )

    async def app(scope, receive, send):  # pragma: no cover
        raise AssertionError("body must not be forwarded")

    boundary = Boundary(app, auth=auth)

    async def receive():
        await asyncio.sleep(3600)

    sent = []

    async def send(event):
        sent.append(event)

    asyncio.run(
        boundary(
            {
                "type": "http",
                "headers": [(b"authorization", b"Bearer " + token().encode())],
                "state": {},
            },
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 408


@pytest.mark.parametrize(
    "content",
    [
        b"{" + b'{"x":' * 2000 + b"1" + b"}" * 2000 + b"}",
        b'{"x":NaN}',
        b'{"x":"\\ud800"}',
        b"[]",
        b"\xff\xfe",
    ],
)
def test_deep_and_malformed_json_are_rejected(service, content):
    client, _, _ = service
    client.put(BASE, headers=headers())
    result = client.post(BASE + "/context", headers=headers(), content=content)
    assert result.status_code == 422
    assert result.json()["error"]["code"] in ("invalid_request", "unauthenticated")


def test_oversized_unicode_and_tool_payloads_are_bounded(service):
    client, _, _ = service
    client.put(BASE, headers=headers())
    large = {
        "id": "t1",
        "operation_id": "one",
        "expected_revision": 0,
        "timestamp": AT.isoformat(),
        "messages": [{"id": "m1", "role": "user", "content": "x" * 64001}],
    }
    assert client.post(BASE + "/turns", headers=headers(), json=large).status_code == 422
    emoji = {**large, "messages": [{"id": "m1", "role": "user", "content": "\U0001f39b" * 9000}]}
    assert client.post(BASE + "/turns", headers=headers(), json=emoji).status_code == 200
    tool = {
        **large,
        "id": "t2",
        "messages": [
            {
                "id": "m2",
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"call_id": f"c{i}", "name": "lookup", "arguments_json": "{}"}
                    for i in range(17)
                ],
            }
        ],
    }
    assert client.post(BASE + "/turns", headers=headers(), json=tool).status_code == 422
    huge_pin = {"value": "p" * 16001, "expected_revision": 1, "effective_at": AT.isoformat()}
    assert client.put(BASE + "/pins/k", headers=headers(), json=huge_pin).status_code == 422


def test_persistent_turn_and_chunk_bounds_are_enforced(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    store.create_scope(SCOPE)
    import context_engine.memory.store as module

    monkeypatch.setattr(module, "MAX_TURNS", 2)
    store.put_turn(turn(1), operation_id="a", expected_revision=0)
    store.put_turn(turn(2), operation_id="b", expected_revision=1)
    with pytest.raises(MemoryIntegrityError):
        store.put_turn(turn(3), operation_id="c", expected_revision=2)
    monkeypatch.setattr(module, "MAX_CHUNKS", 1)
    snapshot = store.snapshot(SCOPE)
    with pytest.raises(MemoryIntegrityError):
        store.index_batch(snapshot, RetrievalConfig(chunk_characters=80, overlap_characters=20))


def test_turn_exceeding_persistent_payload_limit_is_rejected(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: AT)
    store.create_scope(SCOPE)
    oversized = Turn("t1", SCOPE, (Message("m1", Role.USER, "x" * 1_000_001),), 1, AT)
    with pytest.raises(MemoryIntegrityError):
        store.put_turn(oversized, operation_id="one", expected_revision=0)


# --- concurrency and races -------------------------------------------------


@pytest.fixture
def storage_diagnostics(monkeypatch):
    """Test-only error codes/stages, never SQL parameters, paths or exception text."""
    events = []
    connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            try:
                return super().execute(sql, parameters)
            except sqlite3.Error as exc:
                # Only static transaction stages are retained, never arbitrary SQL.
                stage = sql.split()[0].upper() if isinstance(sql, str) and sql else "other"
                if stage not in {"BEGIN", "COMMIT", "PRAGMA", "ATTACH", "INSERT", "UPDATE"}:
                    stage = "other"
                events.append(
                    {"stage": stage, "sqlite_code": getattr(exc, "sqlite_errorcode", None)}
                )
                raise

        def commit(self):
            try:
                return super().commit()
            except sqlite3.Error as exc:
                events.append(
                    {"stage": "commit", "sqlite_code": getattr(exc, "sqlite_errorcode", None)}
                )
                raise

    def observed_connect(*args, **kwargs):
        kwargs.setdefault("factory", ObservedConnection)
        return connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", observed_connect)
    return events


def response_status(response):
    # API codes are allowlisted, rather than dumping a response body on failure.
    codes = {
        "runtime_storage_error",
        "service_unavailable",
        "memory_integrity_error",
        "memory_revision_conflict",
        "quota_exhausted",
        "internal_error",
    }
    code = response.json().get("error", {}).get("code")
    return response.status_code, code if code in codes else None


def test_storage_diagnostics_preserve_failure_and_hide_payload(tmp_path, storage_diagnostics):
    path = tmp_path / "private-sentinel.sqlite"
    with sqlite3.connect(path, timeout=0, isolation_level=None) as first:
        with sqlite3.connect(path, timeout=0, isolation_level=None) as second:
            first.execute("BEGIN IMMEDIATE")
            try:
                with pytest.raises(sqlite3.OperationalError):
                    second.execute("BEGIN IMMEDIATE")
            finally:
                first.rollback()
    first.close()
    second.close()
    assert storage_diagnostics == [{"stage": "BEGIN", "sqlite_code": sqlite3.SQLITE_BUSY}]


def test_concurrent_writes_are_serialised_by_revision(service, storage_diagnostics):
    client, _, _ = service
    client.put(BASE, headers=headers())

    def write(index):
        return response_status(
            client.post(
                BASE + "/turns",
                headers=headers(),
                json={
                    "id": f"t{index}",
                    "operation_id": f"op{index}",
                    "expected_revision": 0,
                    "timestamp": AT.isoformat(),
                    "messages": [{"id": f"m{index}", "role": "user", "content": "value"}],
                },
            )
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(write, range(6)))
    statuses = [status for status, _ in results]
    assert statuses.count(200) == 1, (results, storage_diagnostics)
    assert set(statuses) <= {200, 409}, (results, storage_diagnostics)


def test_concurrent_reads_succeed_and_quota_race_returns_429(service, storage_diagnostics):
    client, _, control = service
    populated(service)

    def read(_):
        # Metadata reads test quota concurrency independently of the new worker cap.
        # Assembly overload/reaping is covered by test_c09_workers.
        return response_status(client.get(BASE, headers=headers()))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, range(8)))
        assert [status for status, _ in results] == [200] * 8, (results, storage_diagnostics)
    control.rpm = 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read, range(4)))
    statuses = [status for status, _ in results]
    assert statuses.count(429) >= 1, (results, storage_diagnostics)
    assert set(statuses) <= {200, 429}, (results, storage_diagnostics)


def test_pin_race_is_resolved_by_optimistic_revision(service, storage_diagnostics):
    client, memory, _ = service
    client.put(BASE, headers=headers())
    body = {"value": "shard-9", "expected_revision": 0, "effective_at": AT.isoformat()}

    def put(_):
        return response_status(client.put(BASE + "/pins/partition", headers=headers(), json=body))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(put, range(4)))
    statuses = [status for status, _ in results]
    assert statuses.count(200) == 1, (results, storage_diagnostics)
    assert set(statuses) <= {200, 409}, (results, storage_diagnostics)
    snapshot = memory.snapshot(Scope("bounds-tenant", "bounds-session"))
    assert snapshot.pins.pins[0].value == "shard-9"
