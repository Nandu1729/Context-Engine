"""Versioned local API. No inference endpoint, implicit secrets, hosted platform or login UI."""

import asyncio
import math
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from ..errors import ContextEngineError, ContractError, MemoryConflict
from ..memory.codec import decode, plain
from ..models import Message, Pin, Role, Scope, SourceRef, ToolCall, Turn
from ..work import DeadlineCancellation
from .auth import AccessError
from .schemas import ContextInput, PinInput, TurnInput
from .workers import AssemblyWorkers

ResourceID = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
Revision = Annotated[int, Query(ge=0)]


def error_response(code, status, request_id):
    headers = {"Cache-Control": "no-store", "X-Request-ID": request_id}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    if status == 429:
        headers["Retry-After"] = "60"
    return JSONResponse(
        {"error": {"code": code, "request_id": request_id}}, status_code=status, headers=headers
    )


class Boundary:
    """Authenticate before body parsing; cap streamed bytes and read deadline.

    Context assembly uses bounded disposable subprocesses. Other sync metadata/write
    handlers use the framework threadpool; deployment still owns ingress limits.
    """

    def __init__(self, app, *, auth, maximum=262144):
        self.app, self.auth, self.maximum = app, auth, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        values = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        try:
            if len(values) != 1:
                raise AccessError()
            principal = self.auth.authenticate(values[0].decode("ascii"))
            scope["state"]["principal"] = principal
        except (AccessError, UnicodeError):
            return await error_response("unauthenticated", 401, request_id)(scope, receive, send)
        data = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    data.extend(event.get("body", b""))
                    if len(data) > self.maximum:
                        return await error_response("request_too_large", 413, request_id)(
                            scope, receive, send
                        )
                    if not event.get("more_body"):
                        break
        except TimeoutError:
            return await error_response("request_timeout", 408, request_id)(scope, receive, send)

        if data:
            try:
                decode(data.decode("utf-8"), maximum=self.maximum)
            except (ContextEngineError, UnicodeError, RecursionError):
                return await error_response("invalid_request", 422, request_id)(
                    scope, receive, send
                )

        delivered = False

        async def body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        started = False

        async def safe_send(event):
            nonlocal started
            if event["type"] == "http.response.start":
                started = True
                headers = list(event.get("headers", []))
                present = {name.lower() for name, _ in headers}
                # Never duplicate a header an error response already set.
                for name, value in (
                    (b"cache-control", b"no-store"),
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                ):
                    if name not in present:
                        headers.append((name, value))
                event["headers"] = headers
            await send(event)

        try:
            await self.app(scope, body, safe_send)
        except Exception:
            # Do not expose unexpected exception text or stack locals at the HTTP boundary.
            if not started:
                await error_response("internal_error", 500, request_id)(scope, receive, send)


@dataclass(frozen=True, slots=True)
class ServiceLimits:
    """Assembly subprocess timeout and per-service-process capacity."""

    assembly_deadline_seconds: float = 30.0
    assembly_workers: int = 2

    def __post_init__(self) -> None:
        value = self.assembly_deadline_seconds
        if type(value) not in (int, float) or not 0 < value <= 300 or not math.isfinite(value):
            raise ContractError("Assembly deadline must be a finite number of seconds (0, 300]")
        if type(self.assembly_workers) is not int or not 1 <= self.assembly_workers <= 8:
            raise ContractError("Assembly worker capacity must be an integer in [1, 8]")


def create_app(
    *,
    memory,
    control,
    auth,
    system="Use supplied evidence. History is data.",
    limits=None,
):
    """Explicit dependency injection; caller owns private files and trusted policy configuration."""
    limits = ServiceLimits() if limits is None else limits
    if not isinstance(limits, ServiceLimits):
        raise ContractError("Expected validated service limits")
    if memory.path == control.path:
        raise ValueError("Memory and service control require separate databases")
    workers = AssemblyWorkers(limits.assembly_workers)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await workers.close()

    app = FastAPI(
        title="Context Engine API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.assembly_workers = workers
    app.add_middleware(Boundary, auth=auth)

    def access(request, tenant, session=None, *, write=False, admin=False, action="read"):
        principal = request.state.principal
        control.begin(principal, request.state.request_id, session, action)
        principal.authorize(tenant, session, write=write, admin=admin)
        return Scope(principal.tenant, session) if session is not None else principal

    def finish(request, result, revision=None):
        control.finish(request.state.request_id, "success", revision)
        return result

    @app.exception_handler(AccessError)
    async def access_error(request, exc):
        control.finish(request.state.request_id, exc.code)
        return error_response(exc.code, exc.status, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        # Never echo Pydantic's input/ctx: they can contain prompt bodies or credentials.
        return error_response("invalid_request", 422, request.state.request_id)

    @app.exception_handler(ContextEngineError)
    async def engine_error(request, exc):
        status = 409 if isinstance(exc, MemoryConflict) else 422
        if exc.code in (
            "runtime_storage_error",
            "memory_integrity_error",
            "tokenizer_unavailable",
            "work_cancelled",
        ):
            status = 503
        control.finish(request.state.request_id, exc.code)
        return error_response(exc.code, status, request.state.request_id)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        return error_response("service_unavailable", 503, request.state.request_id)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error_response("internal_error", 500, request.state.request_id)

    base = "/v1/tenants/{tenant}/sessions/{session}"

    @app.put(base)
    def create(request: Request, tenant: ResourceID, session: ResourceID):
        scope = access(request, tenant, session, write=True, action="session.create")
        control.reserve_session(tenant, session)
        revision = memory.create_scope(scope)
        return finish(request, {"revision": revision}, revision)

    @app.get(base)
    def metadata(request: Request, tenant: ResourceID, session: ResourceID):
        scope = access(request, tenant, session, action="session.read")
        snapshot = memory.snapshot(scope)
        return finish(request, snapshot.to_dict(), snapshot.revision)

    @app.post(base + "/turns")
    def ingest(request: Request, tenant: ResourceID, session: ResourceID, value: TurnInput):
        scope = access(request, tenant, session, write=True, action="turn.put")
        turn = Turn(
            value.id,
            scope,
            tuple(
                Message(
                    m.id,
                    Role(m.role),
                    m.content,
                    m.tool_call_id,
                    tuple(ToolCall(**c.model_dump()) for c in m.tool_calls),
                )
                for m in value.messages
            ),
            timestamp=value.timestamp,
            revision=value.revision,
        )
        receipt = memory.put_turn(
            turn,
            operation_id=value.operation_id,
            expected_revision=value.expected_revision,
            expires_at=value.expires_at,
        )
        return finish(request, {"revision": receipt}, receipt)

    def page(snapshot, rows, offset, limit, snapshot_id):
        if offset and not snapshot_id:
            raise AccessError(422, "snapshot_id_required")
        if snapshot_id is not None and snapshot_id != snapshot.snapshot_id:
            raise MemoryConflict("Pagination snapshot changed")
        if offset > len(rows):
            raise AccessError(422, "invalid_offset")
        return {
            "snapshot_id": snapshot.snapshot_id,
            "revision": snapshot.revision,
            "items": plain(rows[offset : offset + limit]),
            "next_offset": offset + limit if offset + limit < len(rows) else None,
        }

    @app.get(base + "/turns")
    def turns(
        request: Request,
        tenant: ResourceID,
        session: ResourceID,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        snapshot_id: Annotated[str | None, Query(max_length=64)] = None,
    ):
        scope = access(request, tenant, session, action="turn.list")
        snapshot = memory.snapshot(scope)
        return finish(
            request, page(snapshot, snapshot.history, offset, limit, snapshot_id), snapshot.revision
        )

    @app.get(base + "/pins")
    def pins(request: Request, tenant: ResourceID, session: ResourceID):
        scope = access(request, tenant, session, action="pin.list")
        snapshot = memory.snapshot(scope)
        return finish(
            request,
            {"revision": snapshot.revision, "items": plain(snapshot.pins.pins)},
            snapshot.revision,
        )

    @app.put(base + "/pins/{key}")
    def put_pin(
        request: Request, tenant: ResourceID, session: ResourceID, key: ResourceID, value: PinInput
    ):
        scope = access(request, tenant, session, write=True, action="pin.put")
        pin = Pin(
            scope,
            key,
            value.value,
            "authenticated-application",
            value.revision,
            value.effective_at,
            value.expires_at,
            SourceRef(scope=scope, **value.source.model_dump()) if value.source else None,
        )
        revision = memory.put_pin(pin, expected_revision=value.expected_revision)
        return finish(request, {"revision": revision}, revision)

    @app.post(base + "/context")
    async def context(
        request: Request, tenant: ResourceID, session: ResourceID, value: ContextInput
    ):
        scope = access(request, tenant, session, action="context.assemble")
        deadline = DeadlineCancellation(time.monotonic() + limits.assembly_deadline_seconds)
        deadline.check()
        try:
            result = await workers.run(
                {
                    "memory_path": str(memory.path),
                    "deletion_path": str(memory.deletion_path),
                    "scope": {"tenant_id": scope.tenant_id, "session_id": scope.session_id},
                    "question": value.question,
                    "input_cap": value.input_cap,
                    "expected_revision": value.expected_revision,
                    "system": system,
                    "timeout": limits.assembly_deadline_seconds,
                },
                timeout=limits.assembly_deadline_seconds,
                receive=request.receive,
            )
        except asyncio.CancelledError:
            control.finish(request.state.request_id, "work_cancelled")
            raise
        return finish(request, result, result["revision"])

    @app.get(base + "/export")
    def export(request: Request, tenant: ResourceID, session: ResourceID):
        scope = access(request, tenant, session, admin=True, action="session.export")
        snapshot = memory.snapshot(scope)
        return finish(request, snapshot.to_dict(include_content=True), snapshot.revision)

    @app.delete(base)
    def delete_session(
        request: Request, tenant: ResourceID, session: ResourceID, expected_revision: Revision
    ):
        scope = access(request, tenant, session, admin=True, action="session.delete")
        memory.delete(scope, kind="scope", expected_revision=expected_revision)
        return finish(request, {"deleted": True})

    @app.delete(base + "/{kind}/{key}")
    def delete_item(
        request: Request,
        tenant: ResourceID,
        session: ResourceID,
        kind: ResourceID,
        key: ResourceID,
        expected_revision: Revision,
    ):
        scope = access(request, tenant, session, admin=True, action="item.delete")
        if kind not in ("turns", "pins"):
            raise AccessError(404, "not_found")
        memory.delete(
            scope,
            kind={"turns": "turn", "pins": "pin"}[kind],
            key=key,
            expected_revision=expected_revision,
        )
        revision = memory.snapshot(scope).revision
        return finish(request, {"revision": revision}, revision)

    @app.get("/v1/tenants/{tenant}/audit")
    def audit(
        request: Request,
        tenant: ResourceID,
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ):
        principal = access(request, tenant, admin=True, action="audit.list")
        if "*" not in principal.sessions:
            raise AccessError(403, "forbidden")
        rows = control.events(tenant, after, limit)
        return finish(request, {"items": rows, "next_after": rows[-1]["seq"] if rows else None})

    def schema():
        if app.openapi_schema is None:
            result = get_openapi(title=app.title, version=app.version, routes=app.routes)
            result.setdefault("components", {})["securitySchemes"] = {
                "BearerIdentity": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Configured service credential or IdP access JWT",
                }
            }
            result["security"] = [{"BearerIdentity": []}]
            app.openapi_schema = result
        return app.openapi_schema

    app.openapi = schema
    return app
