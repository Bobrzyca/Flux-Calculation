"""Structured logging for the backend.

Production-grade structured logging built on the **standard library** ``logging``
(no extra runtime dependency, fully typeable under ``mypy --strict``):

- a JSON formatter (:class:`JsonFormatter`) for machine-readable logs in
  production, and a compact human formatter (:class:`ConsoleFormatter`) for local
  development — selected by ``LOG_FORMAT``;
- a correlation id (``request_id``) carried in a :class:`~contextvars.ContextVar`
  and injected into every record by :class:`RequestIdFilter`, so all logs emitted
  while handling one HTTP request share the same id;
- :func:`redact` / :class:`JsonFormatter`, which mask sensitive values
  (Authorization, Cookie, passwords, tokens, API keys, session ids, …) so secrets
  never reach the log stream.

Call :func:`configure_logging` once at process startup (done in ``app.main``).
Everywhere else, use ``get_logger(__name__)`` and pass structured fields via
``extra=`` — e.g. ``log.info("request.completed", extra={"status_code": 200})``.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

# --------------------------------------------------------------------------- #
# Correlation id                                                              #
# --------------------------------------------------------------------------- #

#: The id of the HTTP request currently being handled (``None`` outside a
#: request, e.g. at startup). Set by the request middleware; read by the log
#: filter so every line carries it.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


# --------------------------------------------------------------------------- #
# Redaction                                                                   #
# --------------------------------------------------------------------------- #

#: Placeholder written in place of any sensitive value.
REDACTED = "***REDACTED***"

#: Substrings that mark a key as sensitive (matched case-insensitively against
#: the key). Covers HTTP auth/session headers, credentials, and secret config.
SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "authorization",
    "cookie",  # also matches "set-cookie"
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",  # access_token, refresh_token, csrf_token, ...
    "api_key",
    "apikey",
    "api-key",
    "x-api-key",
    "access_key",
    "private_key",
    "credential",
    "session",
    "auth",
)

#: Cap on recursion / size so a hostile or huge structure can't blow up logging.
_MAX_REDACT_DEPTH = 6


def is_sensitive_key(key: str) -> bool:
    """True if ``key`` looks like it holds a secret and should be redacted."""
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, _depth: int = 0) -> Any:
    """Return a copy of ``value`` with sensitive values masked.

    Recurses into dicts and lists/tuples. Dict values whose *key* matches
    :func:`is_sensitive_key` are replaced with :data:`REDACTED`. Scalars pass
    through unchanged. Anything not JSON-friendly is stringified by the caller.
    """
    if _depth >= _MAX_REDACT_DEPTH:
        return "***TRUNCATED***"
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, val in value.items():
            if isinstance(key, str) and is_sensitive_key(key):
                out[key] = REDACTED
            else:
                out[key] = redact(val, _depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth + 1) for item in value]
    return value


# --------------------------------------------------------------------------- #
# Filters and formatters                                                      #
# --------------------------------------------------------------------------- #


class RequestIdFilter(logging.Filter):
    """Attach the current ``request_id`` (or ``None``) to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


# LogRecord attributes that are part of the machinery, not user-supplied
# structured fields. Everything else in ``record.__dict__`` is treated as an
# ``extra=`` field and included (redacted) in the JSON output.
_RESERVED_RECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
        "request_id",
    }
)


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Structured fields passed via ``extra=`` (everything non-reserved)."""
    return {
        key: val
        for key, val in record.__dict__.items()
        if key not in _RESERVED_RECORD_KEYS and not key.startswith("_")
    }


def _iso_timestamp(created: float) -> str:
    """UTC ISO-8601 timestamp (milliseconds) for a record's ``created`` time."""
    return (
        _dt.datetime.fromtimestamp(created, tz=_dt.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class JsonFormatter(logging.Formatter):
    """Render a record as a single-line JSON object, with secrets redacted."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _iso_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            payload["request_id"] = request_id

        extras = _extra_fields(record)
        if extras:
            payload.update(redact(extras))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        # default=str keeps us robust to stray non-serialisable values.
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Compact, human-friendly formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None)
        rid = f" [{request_id}]" if request_id else ""
        base = (
            f"{_iso_timestamp(record.created)} {record.levelname:<7} "
            f"{record.name}{rid} {record.getMessage()}"
        )
        extras = redact(_extra_fields(record))
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

# Loggers that uvicorn installs its own handlers on; we take them over so their
# output shares our format and correlation id. ``uvicorn.access`` is silenced
# because our request middleware emits a richer ``request.completed`` line.
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error")

_configured = False


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure the root logger. Idempotent — safe to call more than once.

    :param level: minimum level name (``DEBUG``/``INFO``/``WARNING``/...); an
        unknown value falls back to ``INFO``.
    :param fmt: ``"json"`` (default, production) or ``"console"`` (development).
    """
    global _configured

    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    formatter: logging.Formatter = (
        ConsoleFormatter() if fmt.lower() == "console" else JsonFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Route uvicorn through our handler (clear its own to avoid double output).
    for name in _UVICORN_LOGGERS:
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True
        uv.setLevel(numeric_level)
    # We emit our own per-request line, so silence uvicorn's access log.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True

    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger; ensures logging is configured at least with defaults."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
