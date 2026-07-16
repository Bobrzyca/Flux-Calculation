"""Optional error/performance monitoring via Sentry.

Monitoring is **off unless ``SENTRY_DSN`` is set** — the app must start and run
fully without it (there is no hard dependency on Sentry being configured). When a
DSN is present, :func:`configure_monitoring` initialises the Sentry SDK with the
FastAPI/Starlette integrations, which capture **unhandled exceptions** (→ 5xx) and
performance transactions.

It is wired to the rest of the app so an issue in Sentry can be traced back to the
logs:

- **Correlation id** — :func:`_before_send` reads the same ``request_id`` context
  var the logger uses (:data:`app.core.logging.request_id_ctx`) and stamps it on
  every event as a tag, so a Sentry issue links straight to the ``request.*`` log
  lines for that request.
- **Redaction** — :func:`_scrub_event` masks sensitive values (Authorization,
  Cookie, passwords, tokens, api keys, session ids, …) in request headers/cookies/
  body, ``extra``/``contexts`` and captured stack-frame locals before the event
  leaves the process, reusing the logger's key list. ``send_default_pii`` is off.

Release is taken from ``SENTRY_RELEASE`` (set from the git SHA at build/run time);
in a dev checkout it falls back to ``git rev-parse HEAD``.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, cast

import sentry_sdk
from sentry_sdk.types import Event, Hint

from app.core.logging import is_sensitive_key, redact, request_id_ctx

log = logging.getLogger("app.monitoring")

# Event sub-trees that may carry request-derived or captured data worth scrubbing
# by key. (The whole event isn't blanket-redacted so structural fields such as
# "message"/"exception" keep their shape.)
_SCRUB_KEYS = ("extra", "contexts")


def _git_sha() -> str | None:
    """Best-effort git SHA for a dev checkout (Docker images set SENTRY_RELEASE)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _scrub_request(request: dict[str, Any]) -> None:
    """Redact headers, cookies and body of a Sentry event's ``request``."""
    for key in ("headers", "cookies", "data"):
        if key in request:
            request[key] = redact(request[key])
    # A raw query string can carry tokens; drop it rather than guess.
    if "query_string" in request:
        request["query_string"] = redact({"query_string": request["query_string"]})[
            "query_string"
        ]


def _scrub_frames(exception: dict[str, Any]) -> None:
    """Redact captured local variables in each stack frame by key."""
    for value in exception.get("values", []):
        stacktrace = value.get("stacktrace") or {}
        for frame in stacktrace.get("frames", []):
            if isinstance(frame.get("vars"), dict):
                frame["vars"] = redact(frame["vars"])


def _scrub_event(event: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive values throughout an event before it is sent."""
    request = event.get("request")
    if isinstance(request, dict):
        _scrub_request(request)
    for key in _SCRUB_KEYS:
        if isinstance(event.get(key), dict):
            event[key] = redact(event[key])
    for exc_container in ("exception", "threads"):
        if isinstance(event.get(exc_container), dict):
            _scrub_frames(event[exc_container])
    # Never attach the logged-in user's IP/id (single-user tool; no PII).
    event.pop("user", None)
    return event


def _before_send(event: Event, _hint: Hint) -> Event:
    """Attach the request correlation id, then redact — for error events."""
    # Sentry's Event is a TypedDict; treat it as a plain mapping for the dynamic
    # key work below (tags/redaction), then hand the same object back.
    data = cast(dict[str, Any], event)
    request_id = request_id_ctx.get()
    if request_id is not None:
        data.setdefault("tags", {})["request_id"] = request_id
    _scrub_event(data)
    return event


def _before_send_transaction(event: Event, _hint: Hint) -> Event:
    """Same correlation id + redaction for performance transactions."""
    return _before_send(event, _hint)


def _mask_dsn(dsn: str) -> str:
    """A DSN embeds a public key; log only its host, never the whole value."""
    try:
        host = dsn.split("@", 1)[1].split("/", 1)[0]
    except IndexError, AttributeError:
        return "set"
    return host


def configure_monitoring(
    dsn: str | None,
    environment: str,
    release: str | None,
    traces_sample_rate: float,
) -> bool:
    """Initialise Sentry if a DSN is provided. Returns True when enabled.

    No-op (returns False) when ``dsn`` is falsy, so the app runs unmonitored in
    dev and wherever the DSN is left blank.
    """
    if not dsn:
        log.info("monitoring.disabled", extra={"reason": "no SENTRY_DSN"})
        return False

    resolved_release = release or _git_sha()
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=resolved_release,
        traces_sample_rate=traces_sample_rate,
        # We never want Sentry to auto-attach cookies, headers or client IP.
        send_default_pii=False,
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
    )
    log.info(
        "monitoring.enabled",
        extra={
            "environment": environment,
            "release": resolved_release,
            "traces_sample_rate": traces_sample_rate,
            "dsn_host": _mask_dsn(dsn),
        },
    )
    return True


def capture_exception(error: BaseException, **tags: str) -> None:
    """Explicitly report a handled but noteworthy domain error (no-op if off)."""
    with sentry_sdk.new_scope() as scope:
        for key, value in tags.items():
            scope.set_tag(key, value)
        sentry_sdk.capture_exception(error)


# Re-exported so callers/tests can assert the shared redaction key list is used.
__all__ = ["capture_exception", "configure_monitoring", "is_sensitive_key"]
