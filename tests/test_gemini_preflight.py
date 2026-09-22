"""Offline Gemini setup guards; no real credential, HTTP call or inference."""

import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "gemini_preflight", Path(__file__).resolve().parents[1] / "scripts/gemini_preflight.py"
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
KEY = "AUTH.synthetic_key"


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / ".env.gemini"
    path.write_text(f"# Synthetic test fixture\nGEMINI_API_KEY={KEY}\n")
    path.chmod(0o600)
    return path


def metadata():
    return {
        "models": [
            {
                "name": "models/gemini-test",
                "inputTokenLimit": 1000,
                "outputTokenLimit": 100,
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            }
        ]
    }


def test_current_auth_key_and_explicit_file_only(key_file, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "must_not_be_used")
    monkeypatch.setenv("GOOGLE_API_KEY", "must_not_be_used_either")
    assert preflight.load_key(key_file) == KEY


@pytest.mark.parametrize(
    "body",
    [
        "",
        "GEMINI_API_KEY=",
        "GROQ_API_KEY=secret",
        "GEMINI_API_KEY=a\nGEMINI_API_KEY=b",
        "bare_secret",
        "GEMINI_API_KEY=space value",
        "GEMINI_API_KEY=a\x00b",
        "é",
    ],
)
def test_invalid_input_is_redacted(key_file, body):
    key_file.write_text(body)
    with pytest.raises(preflight.PreflightError, match="^private_credential_invalid$"):
        preflight.load_key(key_file)


def test_quotes_are_data_not_shell_execution(key_file):
    key_file.write_text('GEMINI_API_KEY="AUTH.synthetic_key"\n')
    assert preflight.load_key(key_file) == KEY


def test_private_regular_bounded_file(key_file, tmp_path):
    key_file.chmod(0o644)
    with pytest.raises(preflight.PreflightError):
        preflight.load_key(key_file)
    key_file.chmod(0o600)
    link = tmp_path / "alias"
    link.symlink_to(key_file)
    with pytest.raises(preflight.PreflightError):
        preflight.load_key(link)
    key_file.write_text("#" * 8193)
    with pytest.raises(preflight.PreflightError):
        preflight.load_key(key_file)


def test_one_fixed_read_only_request_and_filtered_output():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert str(request.url) == preflight.ENDPOINT + "?pageSize=1000"
        assert request.headers["x-goog-api-key"] == KEY
        assert KEY not in str(request.url)
        data = metadata()
        data["models"][0]["description"] = "untrusted text omitted"
        data["nextPageToken"] = "opaque cursor omitted"
        return httpx.Response(200, json=data)

    result = asyncio.run(preflight.discover(KEY, transport=httpx.MockTransport(handler)))
    assert result["status"] == "authenticated" and result["more_pages"]
    assert len(requests) == 1
    assert "omitted" not in json.dumps(result)


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 429, 500])
def test_no_redirect_retry_or_error_body_disclosure(status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, text=KEY, headers={"location": "https://example.com"})

    result = asyncio.run(preflight.discover(KEY, transport=httpx.MockTransport(handler)))
    assert result == {"status": "api_rejected", "http_status": status}
    assert len(requests) == 1 and KEY not in json.dumps(result)


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{}", b"x" * 1_000_001])
def test_invalid_or_oversized_response_is_rejected(body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    with pytest.raises(preflight.PreflightError):
        asyncio.run(preflight.discover(KEY, transport=transport))


def test_secret_reflection_and_transport_errors_redacted():
    data = metadata()
    data["models"][0]["name"] = "models/" + KEY
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=data))
    with pytest.raises(preflight.PreflightError, match="^invalid_model_metadata$"):
        asyncio.run(preflight.discover(KEY, transport=transport))

    def fail(request):
        raise httpx.ConnectError(KEY)

    with pytest.raises(preflight.PreflightError, match="^model_discovery_failed$"):
        asyncio.run(preflight.discover(KEY, transport=httpx.MockTransport(fail)))


def test_local_cli_never_dispatches_and_exclusive_export(key_file, tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(preflight, "discover", forbidden)
    output = tmp_path / "metadata.json"
    args = ["--env-file", str(key_file), "--output", str(output)]
    assert preflight.main(args) == 0
    result = json.loads(output.read_text())
    assert result["inference_calls"] == result["network_requests"] == 0
    assert result["billing_tier"] == result["account_quotas"] == "unverified"
    before = output.read_bytes()
    assert preflight.main([*args, "--allow-network"]) == 1
    assert output.read_bytes() == before
    text = capsys.readouterr()
    assert KEY not in text.out + text.err


def test_output_symlink_refused_before_network(key_file, tmp_path, monkeypatch):
    output = tmp_path / "output.json"
    output.symlink_to(key_file)
    before = key_file.read_bytes()
    monkeypatch.setattr(preflight, "discover", lambda key: pytest.fail("must not dispatch"))
    assert (
        preflight.main(["--env-file", str(key_file), "--output", str(output), "--allow-network"])
        == 1
    )
    assert key_file.read_bytes() == before
