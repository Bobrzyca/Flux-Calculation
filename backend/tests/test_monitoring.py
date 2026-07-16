"""Sentry monitoring wiring: disabled-by-default, correlation id, redaction."""

from __future__ import annotations

from typing import Any, cast

from sentry_sdk.types import Event, Hint

from app.core.logging import REDACTED, request_id_ctx
from app.core.monitoring import (
    _before_send,
    _scrub_event,
    configure_monitoring,
)


def _event(**fields: Any) -> Event:
    return cast(Event, dict(fields))


def test_disabled_without_dsn() -> None:
    """No DSN → monitoring stays off and nothing is initialised."""
    assert (
        configure_monitoring(
            dsn=None, environment="test", release=None, traces_sample_rate=0.0
        )
        is False
    )
    assert (
        configure_monitoring(
            dsn="", environment="test", release=None, traces_sample_rate=0.0
        )
        is False
    )


def test_before_send_stamps_request_id() -> None:
    token = request_id_ctx.set("rid-abc")
    try:
        out = _before_send(_event(message="boom"), cast(Hint, {}))
    finally:
        request_id_ctx.reset(token)
    assert out["tags"]["request_id"] == "rid-abc"


def test_before_send_without_request_id_adds_no_tag() -> None:
    # Outside a request (e.g. a startup error) there is simply no id to add.
    request_id_ctx.set(None)
    out = _before_send(_event(message="startup"), cast(Hint, {}))
    assert "request_id" not in (out.get("tags") or {})


def test_scrub_event_redacts_request_headers_and_cookies() -> None:
    event: dict[str, Any] = {
        "request": {
            "headers": {
                "Authorization": "Bearer supersecret",
                "Cookie": "session=abc123",
                "Content-Type": "application/json",
            },
            "cookies": {"session_id": "zzz"},
            "data": {"password": "hunter2", "note": "ok"},
        },
        "extra": {"api_key": "sk-live-xxx", "count": 3},
    }
    out = _scrub_event(event)
    assert out["request"]["headers"]["Authorization"] == REDACTED
    assert out["request"]["headers"]["Cookie"] == REDACTED
    assert out["request"]["headers"]["Content-Type"] == "application/json"
    assert out["request"]["cookies"]["session_id"] == REDACTED
    assert out["request"]["data"]["password"] == REDACTED
    assert out["request"]["data"]["note"] == "ok"
    assert out["extra"]["api_key"] == REDACTED
    assert out["extra"]["count"] == 3


def test_scrub_event_redacts_stack_frame_locals() -> None:
    event: dict[str, Any] = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"vars": {"token": "t0p", "x": "1"}},
                            {"vars": {"safe": "ok"}},
                        ]
                    }
                }
            ]
        }
    }
    out = _scrub_event(event)
    frames = out["exception"]["values"][0]["stacktrace"]["frames"]
    assert frames[0]["vars"]["token"] == REDACTED
    assert frames[0]["vars"]["x"] == "1"
    assert frames[1]["vars"]["safe"] == "ok"


def test_scrub_event_drops_user_pii() -> None:
    out = _scrub_event({"user": {"ip_address": "1.2.3.4"}, "message": "x"})
    assert "user" not in out
