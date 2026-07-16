"""HTTP middleware: request correlation ids and per-request logging.

:class:`RequestContextMiddleware` gives every request a correlation id and logs
its lifecycle:

- **Correlation id** — reads an inbound ``X-Request-ID`` (set by the frontend
  client, nginx, or Traefik) or generates a fresh UUID4, stores it in the
  :data:`~app.core.logging.request_id_ctx` context var (so *all* logs during the
  request carry it), and echoes it back in the ``X-Request-ID`` response header.
- **Request logging** — one ``request.completed`` line per request with method,
  path, status, and duration; ``request.failed`` (with traceback) if the handler
  raises; a ``slow_request`` warning when the duration exceeds
  ``SLOW_REQUEST_MS``; and a warning for 4xx / error for 5xx responses.

The client's raw query string and body are **never** logged (they may contain
personal data); only the path and coarse metadata are.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import get_logger, request_id_ctx

#: Header used to carry the correlation id in and out.
REQUEST_ID_HEADER = "X-Request-ID"

log = get_logger("app.request")


def _new_request_id() -> str:
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign/propagate a correlation id and log each request's outcome."""

    def __init__(self, app: ASGIApp, slow_request_ms: int = 1000) -> None:
        super().__init__(app)
        self.slow_request_ms = slow_request_ms

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER)
        request_id = inbound or _new_request_id()
        token = request_id_ctx.set(request_id)

        base = {
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        }
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            # exc_info=True → the traceback is captured (and formatted by the
            # JSON formatter). The exception then propagates to Starlette's
            # error handler, which returns the 500.
            log.error(
                "request.failed",
                exc_info=True,
                extra={**base, "duration_ms": duration_ms},
            )
            request_id_ctx.reset(token)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id

        fields = {
            **base,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        if response.status_code >= 500:
            log.error("request.completed", extra=fields)
        elif response.status_code >= 400:
            log.warning("request.completed", extra=fields)
        else:
            log.info("request.completed", extra=fields)

        if duration_ms > self.slow_request_ms:
            log.warning(
                "slow_request",
                extra={**fields, "threshold_ms": self.slow_request_ms},
            )

        request_id_ctx.reset(token)
        return response
