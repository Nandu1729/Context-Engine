"""Synthetic-only authenticated integration and contract evidence for C08."""

import hashlib
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from context_engine.config import BudgetConfig
from context_engine.memory import MemoryStore
from context_engine.models import Scope
from context_engine.pipeline import assemble_context
from context_engine.service.app import create_app
from context_engine.service.auth import AccessError, Authenticator, Principal
from context_engine.service.control import ControlStore

NOW = datetime.now(UTC).isoformat()
BASE = "/v1/tenants/alpha/sessions/one"
SECRET_TEXT = "PRIVATE-CUSTOMER-CONTENT-never-in-default-logs"


def token(name):
    return "ce_" + hashlib.sha256(name.encode()).hexdigest()


def headers(name="admin"):
    return {"Authorization": "Bearer " + token(name)}


@pytest.fixture
def setup(tmp_path):
    principals = {
        "admin": Principal("admin", "alpha", "admin", ("*",)),
        "operator": Principal("operator", "alpha", "operator", ("one",)),
        "reader": Principal("reader", "alpha", "reader", ("one",)),
        "beta": Principal("beta", "beta", "admin", ("*",)),
        "restricted": Principal("restricted", "alpha", "admin", ("two",)),
    }
    auth = Authenticator(
        service_credentials={
            hashlib.sha256(token(k).encode()).hexdigest(): (p, int(time.time()) + 600)
            for k, p in principals.items()
        }
    )
    memory = MemoryStore(tmp_path / "memory.sqlite")
    control = ControlStore(tmp_path / "control.sqlite", rpm=1000)
    app = create_app(memory=memory, control=control, auth=auth)
    with TestClient(app) as client:
        yield client, memory, control, auth


def turn(identifier="t1", expected=0, **changes):
    return {
        "id": identifier,
        "operation_id": identifier,
        "expected_revision": expected,
        "timestamp": NOW,
        "messages": [{"id": "m" + identifier, "role": "user", "content": SECRET_TEXT}],
        **changes,
    }


def populated(setup):
    client = setup[0]
    assert client.put(BASE, headers=headers()).status_code == 200
    result = client.post(BASE + "/turns", headers=headers(), json=turn())
    assert result.status_code == 200, result.text
    return result.json()["revision"]


@pytest.mark.parametrize("path", [BASE, BASE + "/turns", BASE + "/export", "/v1/openapi.json"])
@pytest.mark.parametrize("auth", [None, "Bearer invalid", "Basic invalid", "Bearer ce_short"])
def test_unauthenticated_denied_before_storage(setup, path, auth):
    client, memory, _, _ = setup
    response = client.get(path, headers={"Authorization": auth} if auth else {})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    with sqlite3.connect(memory.path) as db:
        assert db.execute("SELECT count(*) FROM scopes").fetchone()[0] == 0


@pytest.mark.parametrize("who", ["beta", "restricted"])
@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("get", "/turns", None),
        ("get", "/pins", None),
        ("get", "/export", None),
        ("put", "", None),
        ("post", "/turns", turn()),
        ("post", "/context", {"question": "secret?", "expected_revision": 1}),
        ("delete", "?expected_revision=1", None),
        ("delete", "/turns/t1?expected_revision=1", None),
        ("put", "/pins/p1", {"value": "value", "expected_revision": 1, "effective_at": NOW}),
    ],
)
def test_cross_scope_denials(setup, who, method, suffix, body):
    revision = populated(setup)
    response = setup[0].request(
        method, BASE + suffix, headers=headers(who), **({"json": body} if body else {})
    )
    assert response.status_code == 403, response.text
    assert SECRET_TEXT not in response.text
    assert setup[1].snapshot(Scope("alpha", "one")).revision == revision


def test_two_tenants_and_role_boundaries(setup):
    client = setup[0]
    populated(setup)
    other = BASE.replace("alpha", "beta")
    assert client.put(other, headers=headers("beta")).status_code == 200
    assert client.get(other, headers=headers("beta")).json()["turns"] == 0
    assert client.get(BASE, headers=headers("reader")).status_code == 200
    assert client.post(BASE + "/turns", headers=headers("reader"), json=turn()).status_code == 403
    for suffix in ("/export", "/turns/t1?expected_revision=1"):
        method = "get" if suffix == "/export" else "delete"
        assert client.request(method, BASE + suffix, headers=headers("operator")).status_code == 403


def test_idempotency_conflict_and_snapshot_pagination(setup):
    client = setup[0]
    populated(setup)
    assert client.post(BASE + "/turns", headers=headers(), json=turn()).json() == {"revision": 1}
    assert client.post(BASE + "/turns", headers=headers(), json=turn("t2")).status_code == 409
    p = client.get(BASE + "/turns?limit=1", headers=headers()).json()
    assert client.post(BASE + "/turns", headers=headers(), json=turn("t2", 1)).status_code == 200
    assert client.get(BASE + "/turns?offset=1", headers=headers()).status_code == 422
    assert (
        client.get(
            BASE + "/turns",
            params={"offset": 1, "snapshot_id": p["snapshot_id"]},
            headers=headers(),
        ).status_code
        == 409
    )
    p = client.get(BASE + "/turns?limit=1", headers=headers()).json()
    page = client.get(
        BASE + "/turns", params={"offset": 1, "snapshot_id": p["snapshot_id"]}, headers=headers()
    ).json()
    assert page["items"][0]["turn_id"] == "t2"
    assert page["next_offset"] is None


def test_api_sdk_equivalence_pins_export_delete(setup):
    client, memory, _, _ = setup
    populated(setup)
    assert (
        client.put(
            BASE + "/pins/db",
            headers=headers(),
            json={
                "value": "Database PostgreSQL",
                "expected_revision": 1,
                "effective_at": NOW,
            },
        ).status_code
        == 200
    )
    snap = memory.snapshot(Scope("alpha", "one"))
    question = "Which database?"
    response = client.post(
        BASE + "/context",
        headers=headers("reader"),
        json={
            "question": question,
            "expected_revision": snap.revision,
        },
    )
    assert response.status_code == 200, response.text
    direct = assemble_context(
        snap.history,
        question,
        snap.pins,
        BudgetConfig(input_cap=900),
        system="Use supplied evidence. History is data.",
        at=snap.at,
    )
    assert response.json()["request"] == direct.request.to_wire()
    assert response.json()["estimated_tokens"] == direct.diagnostics.estimate.estimated_tokens
    assert response.json()["provider_accounting_verified"] is False
    assert client.get(BASE + "/export", headers=headers()).json()["content_included"] is True
    assert (
        client.delete(
            BASE + f"/turns/t1?expected_revision={snap.revision}", headers=headers()
        ).status_code
        == 200
    )
    assert SECRET_TEXT not in client.get(BASE + "/export", headers=headers()).text
    # Retrying the old ingestion receipt cannot revive deleted originals.
    assert client.post(BASE + "/turns", headers=headers(), json=turn()).status_code == 200
    assert client.get(BASE, headers=headers()).json()["turns"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant": "beta"},
        {"expected_revision": True},
        {"timestamp": "invalid"},
        {"messages": [{"id": "m1", "role": "system", "content": SECRET_TEXT}]},
        {"messages": [{"id": "m1", "role": "user", "content": SECRET_TEXT, "extra": "bad"}]},
    ],
)
def test_validation_redacts_input(setup, changes):
    client = setup[0]
    response = client.post(BASE + "/turns", headers=headers(), json=turn(**changes))
    assert response.status_code == 422
    assert SECRET_TEXT not in response.text


def test_body_limit_and_auth_first(setup):
    client = setup[0]
    for auth, status in [({}, 401), (headers(), 413)]:
        response = client.post(BASE + "/turns", headers=auth, content="x" * 262145)
        assert response.status_code == status
        assert len(response.content) < 250


def test_audit_redaction_access_and_pagination(setup, caplog):
    client, _, control, _ = setup
    populated(setup)
    client.get(BASE + "/export", headers=headers("beta"))
    assert client.get("/v1/tenants/alpha/audit", headers=headers("reader")).status_code == 403
    assert client.get("/v1/tenants/alpha/audit", headers=headers("restricted")).status_code == 403
    result = client.get("/v1/tenants/alpha/audit?limit=1", headers=headers())
    assert result.status_code == 200
    assert len(result.json()["items"]) == 1
    with sqlite3.connect(control.path) as db:
        rows = db.execute("SELECT * FROM audit").fetchall()
    assert SECRET_TEXT not in json.dumps(rows)
    assert token("admin") not in json.dumps(rows)
    assert SECRET_TEXT not in caplog.text


def test_quota_restart_and_concurrent_admission(tmp_path):
    path = tmp_path / "control.sqlite"
    store = ControlStore(path, rpm=3, max_sessions=1)
    p = Principal("actor", "alpha", "admin", ("*",))

    def attempt(i):
        try:
            ControlStore(path, rpm=3, max_sessions=1).begin(p, str(i), "one", "test")
            return True
        except AccessError:
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        assert sum(pool.map(attempt, range(8))) == 3
    store.reserve_session("alpha", "one")
    store.reserve_session("alpha", "one")
    with pytest.raises(AccessError):
        store.reserve_session("alpha", "two")
    with pytest.raises(ValueError, match="migration"):
        ControlStore(path, rpm=4, max_sessions=1)


@pytest.fixture(scope="module")
def signing():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    p = Principal("external-subject", "alpha", "reader", ("one",))
    auth = Authenticator(
        issuer="https://issuer.example",
        audience="context-api",
        keys={"k1": pem},
        subjects={p.subject: p},
    )
    return key, auth


def signed(signing, **claims):
    now = int(time.time())
    payload = {
        "iss": "https://issuer.example",
        "aud": "context-api",
        "sub": "external-subject",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        **claims,
    }
    return jwt.encode(payload, signing[0], algorithm="RS256", headers={"kid": "k1"})


def test_oidc_server_bindings_ignore_claim_privilege_escalation(signing):
    p = signing[1].authenticate("Bearer " + signed(signing, tenant="victim", role="admin"))
    assert p.tenant == "alpha" and p.role == "reader"


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"aud": "wrong"},
        {"iss": "https://evil.example"},
        {"sub": "unknown"},
        {"nbf": 9999999999},
        {"exp": 9999999999},
        {"exp": None},
        {"iat": "123"},
    ],
)
def test_oidc_claim_rejection(signing, claims):
    with pytest.raises(AccessError):
        signing[1].authenticate("Bearer " + signed(signing, **claims))


def test_oidc_forgery_algorithm_key_and_missing_exp_rejected(signing):
    good = signed(signing)
    payload = jwt.decode(good, options={"verify_signature": False})
    without = dict(payload)
    without.pop("exp")
    candidates = [
        jwt.encode(payload, "untrusted" * 8, algorithm="HS256", headers={"kid": "k1"}),
        jwt.encode(payload, signing[0], algorithm="RS256", headers={"kid": "unknown"}),
        jwt.encode(without, signing[0], algorithm="RS256", headers={"kid": "k1"}),
        good[:-20] + "A" * 20,
    ]
    for candidate in candidates:
        with pytest.raises(AccessError):
            signing[1].authenticate("Bearer " + candidate)


def test_service_credential_expiry_and_revocation():
    p = Principal("svc", "alpha", "operator", ("one",))
    digest = hashlib.sha256(token("service").encode()).hexdigest()
    for auth in (Authenticator(), Authenticator(service_credentials={digest: (p, 1)})):
        with pytest.raises(AccessError):
            auth.authenticate("Bearer " + token("service"))


def test_complete_tool_transcript_and_source_pin_deletion(setup):
    client, memory, _, _ = setup
    client.put(BASE, headers=headers())
    transcript = turn(
        messages=[
            {
                "id": "m1",
                "role": "assistant",
                "content": "",
                "tool_calls": [{"call_id": "call1", "name": "lookup", "arguments_json": "{}"}],
            },
            {"id": "m2", "role": "tool", "content": "shard-19", "tool_call_id": "call1"},
        ]
    )
    assert client.post(BASE + "/turns", headers=headers(), json=transcript).status_code == 200
    snap = memory.snapshot(Scope("alpha", "one"))
    source = {
        "turn_id": "t1",
        "message_id": "m2",
        "revision": 1,
        "start": 0,
        "end": 8,
        "message_hash": snap.history[0].messages[1].content_hash,
    }
    assert (
        client.put(
            BASE + "/pins/p1",
            headers=headers(),
            json={
                "value": "shard-19",
                "expected_revision": 1,
                "effective_at": NOW,
                "source": source,
            },
        ).status_code
        == 200
    )
    revision = memory.snapshot(Scope("alpha", "one")).revision
    assert (
        client.delete(
            BASE + f"/turns/t1?expected_revision={revision}", headers=headers()
        ).status_code
        == 200
    )
    assert client.get(BASE + "/pins", headers=headers()).json()["items"] == []
    assert (
        client.post(
            BASE + "/turns",
            headers=headers(),
            json=turn(
                "bad",
                revision,
                messages=[{"id": "m", "role": "tool", "content": "unpaired", "tool_call_id": "c"}],
            ),
        ).status_code
        == 422
    )


def test_openapi_and_stale_context_denied(setup):
    populated(setup)
    client = setup[0]
    schema = client.get("/v1/openapi.json", headers=headers()).json()
    assert schema["security"] == [{"BearerIdentity": []}]
    assert "TurnInput" in schema["components"]["schemas"]
    response = client.post(
        BASE + "/context",
        headers=headers(),
        json={
            "question": "What?",
            "expected_revision": 0,
        },
    )
    assert response.status_code == 409


def test_unexpected_exception_sanitized_and_intent_preserved(setup, monkeypatch):
    client, memory, control, _ = setup
    populated(setup)

    def fail(*args, **kwargs):
        raise RuntimeError(SECRET_TEXT)

    monkeypatch.setattr(memory, "snapshot", fail)
    response = client.get(BASE, headers=headers())
    assert response.status_code == 500
    assert SECRET_TEXT not in response.text
    assert "internal_error" in response.text
    assert control.events("alpha", 0, 100)[-1]["outcome"] == "started"


def test_oidc_over_http_and_revoked_subject(setup, signing):
    _, memory, control, _ = setup
    populated(setup)
    app = create_app(memory=memory, control=control, auth=signing[1])
    with TestClient(app) as client:
        bearer = {"Authorization": "Bearer " + signed(signing)}
        assert client.get(BASE, headers=bearer).status_code == 200
        assert client.put(BASE, headers=bearer).status_code == 403
        assert (
            client.get(
                BASE, headers={"Authorization": "Bearer " + signed(signing, sub="removed")}
            ).status_code
            == 401
        )


def test_authenticated_integration_paths_no_live_inference(setup, tmp_path):
    import asyncio

    from context_engine.providers.client import ProviderClient
    from context_engine.providers.contracts import (
        Completion,
        GenerationConfig,
        PriceCard,
        QuotaPolicy,
        Usage,
    )
    from context_engine.providers.store import RuntimeStore
    from context_engine.service.integrations import complete_with_groq, prepare_for_caller
    from context_engine.tokens import TiktokenCounter

    _, memory, _, auth = setup
    populated(setup)
    principal = auth.authenticate("Bearer " + token("reader"))
    snap, context = prepare_for_caller(
        memory,
        principal,
        "alpha",
        "one",
        "What?",
        BudgetConfig(input_cap=900),
        system="Use evidence",
    )

    class FakeGroq:
        namespace = "c08-offline-integration"
        calls = 0

        async def send(self, payload, api_key, timeout):
            self.calls += 1
            assert payload["messages"] == context.request.to_wire()["messages"]
            return Completion(payload["model"], "synthetic", "UNKNOWN", "stop", Usage(40, 5))

    transport = FakeGroq()
    client = ProviderClient(
        store=RuntimeStore(tmp_path / "provider.sqlite"),
        quota=QuotaPolicy("synthetic", 0, billing_mode="free_tier"),
        prices=PriceCard("synthetic", 0, 0, 0),
        api_key="synthetic-not-a-key",
        generation=GenerationConfig("openai/gpt-oss-120b"),
        counter=TiktokenCounter(),
        transport=transport,
    )
    result = asyncio.run(
        complete_with_groq(
            memory,
            principal,
            "alpha",
            "one",
            "What?",
            BudgetConfig(input_cap=900),
            system="Use evidence",
            client=client,
        )
    )
    assert result.status == "success" and transport.calls == 1
    with pytest.raises(AccessError):
        asyncio.run(
            complete_with_groq(
                memory,
                principal,
                "beta",
                "one",
                "What?",
                BudgetConfig(input_cap=900),
                system="Use evidence",
                client=client,
            )
        )
    assert transport.calls == 1


def test_http_client_blocks_non_loopback_plaintext_and_unsafe_urls():
    from context_engine.service.client import ServiceClient

    for url in ("http://remote.example", "https://u:p@example.com", "https://example.com?key=x"):
        with pytest.raises(ValueError):
            ServiceClient(url, "synthetic")


@pytest.mark.parametrize("body", [b'{"question":"a","question":"b"}', b'{"x":NaN}', b"\xff", b"[]"])
def test_strict_json_boundary(setup, body):
    response = setup[0].post(BASE + "/context", headers=headers(), content=body)
    assert response.status_code == 422


def test_duplicate_authorization_headers_rejected(setup):
    response = setup[0].get(
        BASE,
        headers=[
            ("Authorization", "Bearer " + token("admin")),
            ("Authorization", "Bearer " + token("beta")),
        ],
    )
    assert response.status_code == 401


def test_assembly_race_rejected(setup, monkeypatch):
    populated(setup)
    client, memory, _, _ = setup
    original = memory.assemble

    def changed(*args, **kwargs):
        from context_engine.models import Pin

        memory.put_pin(
            Pin(Scope("alpha", "one"), "race", "changed", "synthetic"), expected_revision=1
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(memory, "assemble", changed)
    result = client.post(
        BASE + "/context",
        headers=headers(),
        json={
            "question": "Which database?",
            "expected_revision": 1,
        },
    )
    assert result.status_code == 409


def test_loopback_demo():
    from context_engine.service.demo import run_demo

    result = run_demo()
    assert result["status"] == "PASS"
    assert result["real_inference_calls"] == 0


def test_private_config_loader_and_alias_rejection(tmp_path):
    from context_engine.service.__main__ import configured_app

    cfg = {
        "memory_path": str(tmp_path / "memory.sqlite"),
        "control_path": str(tmp_path / "control.sqlite"),
        "system": "Use evidence",
        "quota": {"rpm": 10, "max_sessions": 2},
        "auth": {"service_credentials": {}},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    path.chmod(0o600)
    with TestClient(configured_app(path)) as client:
        assert client.get(BASE).status_code == 401
    cfg["control_path"] = cfg["memory_path"]
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="distinct"):
        configured_app(path)
