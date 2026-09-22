"""Operator-configured identities; no tenant/role authorization from untrusted claims."""

import hashlib
import re
import time
from dataclasses import dataclass
from types import MappingProxyType

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
ROLES = {"reader", "operator", "admin"}


class AccessError(Exception):
    def __init__(self, status=401, code="unauthenticated"):
        self.status, self.code = status, code


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant: str
    role: str
    sessions: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "sessions", tuple(self.sessions))
        if (
            not isinstance(self.subject, str)
            or not 1 <= len(self.subject) <= 256
            or not ID.fullmatch(self.tenant)
            or self.role not in ROLES
            or not self.sessions
            or any(s != "*" and not ID.fullmatch(s) for s in self.sessions)
        ):
            raise ValueError("Invalid configured identity")

    def authorize(self, tenant, session=None, *, write=False, admin=False):
        if (
            tenant != self.tenant
            or (session is not None and "*" not in self.sessions and session not in self.sessions)
            or (write and self.role == "reader")
            or (admin and self.role != "admin")
        ):
            raise AccessError(403, "forbidden")


class Authenticator:
    """Pinned RS256 public keys + explicit subject bindings, or hashed service credentials.

    External IdP provisions short-lived access tokens for this API audience. Key rotation
    and role/session revocation are operator config reloads; no token-selected URL is fetched.
    Service credential mapping: SHA256(token) -> (Principal, UTC expiry timestamp).
    """

    def __init__(
        self,
        *,
        service_credentials=None,
        issuer=None,
        audience=None,
        keys=None,
        subjects=None,
        max_token_lifetime=3600,
    ):
        self.credentials = MappingProxyType(dict(service_credentials or {}))
        self.subjects = MappingProxyType(dict(subjects or {}))
        self.issuer, self.audience = issuer, audience
        self.max_token_lifetime = max_token_lifetime
        loaded = {}
        for kid, pem in (keys or {}).items():
            key = serialization.load_pem_public_key(pem.encode())
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError("Only RSA public keys of at least 2048 bits are allowed")
            loaded[kid] = key
        self.keys = MappingProxyType(loaded)
        if self.keys and (not issuer or not issuer.startswith("https://") or not audience):
            raise ValueError("OIDC requires explicit HTTPS issuer and API audience")
        if type(max_token_lifetime) is not int or not 1 <= max_token_lifetime <= 86400:
            raise ValueError("Invalid token lifetime policy")
        for digest, (principal, expires) in self.credentials.items():
            if not re.fullmatch(r"[a-f0-9]{64}", digest) or not isinstance(principal, Principal):
                raise ValueError("Invalid credential configuration")
            if type(expires) is not int or expires <= 0:
                raise ValueError("Service credentials require expiry")
        if any(
            not isinstance(p, Principal) or sub != p.subject for sub, p in self.subjects.items()
        ):
            raise ValueError("Invalid subject binding")

    def authenticate(self, authorization):
        if not isinstance(authorization, str) or len(authorization) > 8192:
            raise AccessError()
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token or " " in token:
            raise AccessError()
        if token.startswith("ce_"):
            if len(token) < 35:
                raise AccessError()
            match = self.credentials.get(hashlib.sha256(token.encode()).hexdigest())
            if not match or match[1] <= time.time():
                raise AccessError()
            return match[0]
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("crit"):
                raise AccessError()
            key = self.keys.get(header.get("kid"))
            if key is None:
                raise AccessError()
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
                leeway=0,
            )
            if any(type(claims[k]) is not int for k in ("exp", "iat", "nbf")):
                raise AccessError()
            if not 0 < claims["exp"] - claims["iat"] <= self.max_token_lifetime:
                raise AccessError()
            principal = self.subjects.get(claims["sub"])
            if principal is None:
                raise AccessError()
            return principal
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise AccessError() from None
