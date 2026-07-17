"""Security baseline tests (black-box, via the API TestClient).

These assert security-relevant behaviour that must stay true:
- the app never runs in debug mode (no tracebacks to clients),
- CORS never reflects an arbitrary origin (esp. with credentials allowed),
- unknown resources return a clean structured 404 with no internal detail,
- a sensitive request header is never echoed back to the client,
- every response carries a correlation id (audit trail → logs/Sentry).

Deeper security tests (headers hardening, upload limits, authz once/if added)
are tracked in this dir's README for a later pass.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.middleware import REQUEST_ID_HEADER
from app.main import app


def test_app_not_in_debug_mode() -> None:
    # Debug mode would leak tracebacks / interactive debugger to clients.
    assert app.debug is False


def test_cors_not_wildcard_with_credentials() -> None:
    # Wildcard origins + credentials is a classic misconfiguration.
    assert "*" not in settings.cors_origins


def test_cors_does_not_reflect_arbitrary_origin(client: TestClient) -> None:
    res = client.get("/api/health", headers={"Origin": "https://evil.example"})
    acao = res.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example"
    assert acao != "*"


def test_unknown_analysis_returns_clean_404(client: TestClient) -> None:
    res = client.get("/api/analyses/does-not-exist")
    assert res.status_code == 404
    body = res.text
    # No stack trace / internal file paths leaked in the error body.
    assert "Traceback" not in body
    assert "/app/" not in body


def test_sensitive_request_header_not_reflected(client: TestClient) -> None:
    secret = "Bearer super-secret-token"
    res = client.get("/api/health", headers={"Authorization": secret})
    assert res.status_code == 200
    assert "super-secret-token" not in res.text
    assert "authorization" not in {k.lower() for k in res.headers}


def test_every_response_has_correlation_id(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.headers.get(REQUEST_ID_HEADER)
