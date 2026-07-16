/**
 * Optional error/performance monitoring via Sentry (browser).
 *
 * Monitoring is **off unless `VITE_SENTRY_DSN` is set** — the app builds and runs
 * fully without it. When a DSN is present, `initMonitoring()` starts the Sentry
 * React SDK, which captures uncaught runtime errors and unhandled promise
 * rejections automatically; `browserTracingIntegration` adds route/navigation
 * performance transactions.
 *
 * Linked to logging: the API client (`src/api/client.ts`) adds a breadcrumb per
 * request carrying the same `requestId` it sends as `X-Request-ID`, so a captured
 * error shows which backend requests preceded it — and those ids match the
 * backend's `request.*` log lines and Sentry `request_id` tag.
 *
 * Redaction: `scrubEvent` masks sensitive values (auth, cookie, token, password,
 * session, …) in the event's request headers/cookies/body, `extra` and `contexts`
 * before anything is sent, reusing the logger's key list. `sendDefaultPii` is off.
 */
import * as Sentry from '@sentry/react'

import { redact } from './logger'

/** Minimal view of the parts of a Sentry event we scrub. */
interface ScrubbableEvent {
  request?: {
    headers?: unknown
    cookies?: unknown
    data?: unknown
    query_string?: unknown
  }
  extra?: Record<string, unknown>
  contexts?: Record<string, unknown>
  user?: unknown
}

/** Mask sensitive values in an event before it leaves the browser. */
export function scrubEvent<T extends ScrubbableEvent>(event: T): T {
  const req = event.request
  if (req) {
    if (req.headers) req.headers = redact(req.headers)
    if (req.cookies) req.cookies = redact(req.cookies)
    if (req.data) req.data = redact(req.data)
    // A raw query string can carry tokens; drop it rather than guess.
    delete req.query_string
  }
  if (event.extra) event.extra = redact(event.extra) as Record<string, unknown>
  if (event.contexts)
    event.contexts = redact(event.contexts) as Record<string, unknown>
  // Single-user tool — never attach a user identity / IP.
  delete event.user
  return event
}

/** Start Sentry if a DSN is configured. Returns whether it was enabled. */
export function initMonitoring(): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return false

  const rawRate = import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE
  const tracesSampleRate = rawRate ? Number(rawRate) || 0 : 0

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? 'development',
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
    tracesSampleRate,
    sendDefaultPii: false,
    integrations: [Sentry.browserTracingIntegration()],
    beforeSend: (event) => scrubEvent(event),
    beforeSendTransaction: (event) => scrubEvent(event),
    beforeBreadcrumb: (crumb) => {
      if (crumb.data) crumb.data = redact(crumb.data) as Record<string, unknown>
      return crumb
    },
  })
  return true
}

/** Tag the active scope with the current route, for error grouping/context. */
export function setRouteContext(pathname: string): void {
  Sentry.getCurrentScope().setTag('route', pathname)
}

/** Record an API call as a breadcrumb so errors show the preceding requests. */
export function recordApiBreadcrumb(data: {
  method: string
  path: string
  status?: number
  requestId: string
  level: 'info' | 'warning' | 'error'
}): void {
  Sentry.addBreadcrumb({
    category: 'http',
    type: 'http',
    level: data.level,
    message: `${data.method} ${data.path}`,
    data: {
      status: data.status,
      request_id: data.requestId,
    },
  })
}

/** Capture a network/API exception, tagged with its correlation id. */
export function captureApiError(
  error: unknown,
  ctx: { method: string; path: string; requestId: string },
): void {
  Sentry.captureException(error, {
    tags: { request_id: ctx.requestId },
    extra: { method: ctx.method, path: ctx.path },
  })
}
