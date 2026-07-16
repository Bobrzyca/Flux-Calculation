"""Tests for structured logging: redaction, correlation id, error logging."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import (
    REDACTED,
    JsonFormatter,
    is_sensitive_key,
    redact,
    request_id_ctx,
)
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware

# --------------------------------------------------------------------------- #
# Redaction                                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "key",
    [
        "Authorization",
        "authorization",
        "Cookie",
        "Set-Cookie",
        "password",
        "user_password",
        "api_key",
        "X-API-Key",
        "access_token",
        "refresh_token",
        "session_id",
        "llm_api_key",
        "db_credential",
    ],
)
def test_sensitive_keys_flagged(key: str) -> None:
    assert is_sensitive_key(key) is True


@pytest.mark.parametrize(
    "key", ["method", "path", "status_code", "duration_ms", "name"]
)
def test_non_sensitive_keys_pass(key: str) -> None:
    assert is_sensitive_key(key) is False


def test_redact_masks_sensitive_values_nested() -> None:
    payload: dict[str, Any] = {
        "method": "POST",
        "headers": {
            "Authorization": "Bearer supersecret",
            "Cookie": "session=abc123",
            "Content-Type": "application/json",
        },
        "user": {"name": "Zuzanna", "api_key": "sk-live-xxx"},
        "items": [{"token": "t0p"}, {"safe": "ok"}],
    }
    cleaned = redact(payload)

    assert cleaned["method"] == "POST"
    assert cleaned["headers"]["Authorization"] == REDACTED
    assert cleaned["headers"]["Cookie"] == REDACTED
    assert cleaned["headers"]["Content-Type"] == "application/json"
    assert cleaned["user"]["name"] == "Zuzanna"
    assert cleaned["user"]["api_key"] == REDACTED
    assert cleaned["items"][0]["token"] == REDACTED
    assert cleaned["items"][1]["safe"] == "ok"
    # The original is not mutated.
    assert payload["headers"]["Authorization"] == "Bearer supersecret"


# --------------------------------------------------------------------------- #
# JSON formatter                                                              #
# --------------------------------------------------------------------------- #


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_valid_json_with_fields() -> None:
    record = _record(status_code=200, request_id="rid-123")
    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test"
    assert parsed["message"] == "hello"
    assert parsed["status_code"] == 200
    assert parsed["request_id"] == "rid-123"
    assert "timestamp" in parsed


def test_json_formatter_redacts_extras() -> None:
    record = _record(authorization="Bearer secret", ok="visible")
    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["authorization"] == REDACTED
    assert parsed["ok"] == "visible"


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    parsed = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in parsed["exception"]


# --------------------------------------------------------------------------- #
# Request-id middleware                                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture
def mw_app() -> FastAPI:
    """A tiny app wired with only the request-context middleware."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware, slow_request_ms=1000)

    @app.get("/ok")
    def ok() -> dict[str, str | None]:
        return {"seen_request_id": request_id_ctx.get()}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    return app


def test_request_id_generated_when_absent(mw_app: FastAPI) -> None:
    client = TestClient(mw_app)
    res = client.get("/ok")
    assert res.status_code == 200
    rid = res.headers.get(REQUEST_ID_HEADER)
    assert rid is not None and len(rid) == 32
    # The handler saw the same id via the context var.
    assert res.json()["seen_request_id"] == rid


def test_request_id_propagated_when_provided(mw_app: FastAPI) -> None:
    client = TestClient(mw_app)
    res = client.get("/ok", headers={REQUEST_ID_HEADER: "caller-supplied-id"})
    assert res.headers.get(REQUEST_ID_HEADER) == "caller-supplied-id"
    assert res.json()["seen_request_id"] == "caller-supplied-id"


def test_request_completed_logged_with_request_id(
    mw_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    # NB: don't call configure_logging() here — it clears the root handlers,
    # including the one pytest's caplog installs. caplog captures records via
    # propagation regardless of our formatter, so the default config is fine.
    client = TestClient(mw_app)
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/ok", headers={REQUEST_ID_HEADER: "rid-xyz"})

    completed = [r for r in caplog.records if r.getMessage() == "request.completed"]
    assert completed, "expected a request.completed log line"
    rec: Any = completed[0]
    assert rec.request_id == "rid-xyz"
    assert rec.status_code == 200
    assert rec.method == "GET"


def test_handler_exception_is_logged(
    mw_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    # Do not re-raise into the test; capture the 500 instead.
    client = TestClient(mw_app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app.request"):
        res = client.get("/boom", headers={REQUEST_ID_HEADER: "rid-err"})

    assert res.status_code == 500
    failed = [r for r in caplog.records if r.getMessage() == "request.failed"]
    assert failed, "expected a request.failed log line"
    rec: Any = failed[0]
    assert rec.levelno == logging.ERROR
    assert rec.exc_info is not None  # traceback captured
    assert rec.request_id == "rid-err"


def test_health_response_carries_request_id(client: TestClient) -> None:
    """The real app echoes a correlation id on a normal response."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get(REQUEST_ID_HEADER)
