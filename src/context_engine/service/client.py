"""Optional caller-managed HTTP integration. Credentials never enter a URL or result."""

from urllib.parse import urlsplit

import httpx

from .auth import ID


class ServiceClient:
    def __init__(self, base_url, token, *, transport=None):
        parsed = urlsplit(base_url)
        if (
            (
                parsed.scheme != "https"
                and not (
                    parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                )
            )
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("HTTPS required except explicit loopback development")
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def context(self, tenant, session, *, question, expected_revision, input_cap=900):
        if not ID.fullmatch(tenant) or not ID.fullmatch(session):
            raise ValueError("Invalid resource identifier")
        response = self.client.post(
            f"/v1/tenants/{tenant}/sessions/{session}/context",
            json={
                "question": question,
                "expected_revision": expected_revision,
                "input_cap": input_cap,
            },
        )
        if response.status_code != 200:
            # HTTPX exceptions include URLs; return only the controlled status here.
            raise RuntimeError(f"Context service returned status {response.status_code}")
        return response.json()

    def close(self):
        self.client.close()
