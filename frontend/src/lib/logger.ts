/**
 * Structured, level-gated logger for the frontend.
 *
 * Wraps the browser `console` with:
 * - **Leveled output** gated by `VITE_LOG_LEVEL` (`debug` | `info` | `warn` |
 *   `error` | `silent`). Default: `debug` in dev, `warn` in production builds.
 * - **Structured records** — every line is `{ ts, level, msg, ...fields }`, with
 *   an optional `requestId` for correlating a frontend log with the backend log
 *   for the same request (the API client threads it through).
 * - **Redaction** — fields whose key looks sensitive (auth, cookie, password,
 *   token, api key, session, …) are masked before anything is printed, so a
 *   stray header or token never lands in the console.
 *
 * Keep app code free of raw `console.*`; import `logger` (or `logger.child`).
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent'

const LEVEL_WEIGHT: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
  silent: 100,
}

/** Placeholder written in place of any sensitive value. */
export const REDACTED = '***REDACTED***'

/** Substrings (case-insensitive) that mark a field key as sensitive. */
const SENSITIVE_KEY_PARTS = [
  'authorization',
  'cookie',
  'password',
  'passwd',
  'pwd',
  'secret',
  'token',
  'api_key',
  'apikey',
  'api-key',
  'x-api-key',
  'access_key',
  'private_key',
  'credential',
  'session',
  'auth',
]

const MAX_REDACT_DEPTH = 6

export function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase()
  return SENSITIVE_KEY_PARTS.some((part) => lowered.includes(part))
}

/** Return a copy of `value` with sensitive values masked (recursively). */
export function redact(value: unknown, depth = 0): unknown {
  if (depth >= MAX_REDACT_DEPTH) return '***TRUNCATED***'
  if (Array.isArray(value)) return value.map((v) => redact(v, depth + 1))
  if (value && typeof value === 'object') {
    // Headers are common and iterate differently — normalise to an object.
    const entries =
      value instanceof Headers
        ? [...value.entries()]
        : Object.entries(value as Record<string, unknown>)
    const out: Record<string, unknown> = {}
    for (const [key, val] of entries) {
      out[key] = isSensitiveKey(key) ? REDACTED : redact(val, depth + 1)
    }
    return out
  }
  return value
}

/** Structured fields attached to a log line. */
export type LogFields = Record<string, unknown>

function resolveLevel(): LogLevel {
  const raw = import.meta.env.VITE_LOG_LEVEL?.toLowerCase()
  if (raw && raw in LEVEL_WEIGHT) return raw as LogLevel
  return import.meta.env.PROD ? 'warn' : 'debug'
}

class Logger {
  private readonly level: LogLevel
  private readonly base: LogFields

  constructor(level: LogLevel, base: LogFields = {}) {
    this.level = level
    this.base = base
  }

  /** A logger that adds fixed fields (e.g. a requestId) to every line. */
  child(fields: LogFields): Logger {
    return new Logger(this.level, { ...this.base, ...fields })
  }

  private enabled(level: LogLevel): boolean {
    return LEVEL_WEIGHT[level] >= LEVEL_WEIGHT[this.level]
  }

  private emit(
    level: Exclude<LogLevel, 'silent'>,
    msg: string,
    fields?: LogFields,
  ): void {
    if (!this.enabled(level)) return
    const record = {
      ts: new Date().toISOString(),
      level,
      msg,
      ...(redact({ ...this.base, ...fields }) as LogFields),
    }
    // Route to the matching console method so browser devtools filtering works.
    const sink =
      level === 'error'
        ? console.error
        : level === 'warn'
          ? console.warn
          : level === 'info'
            ? console.info
            : console.debug
    sink(JSON.stringify(record))
  }

  debug(msg: string, fields?: LogFields): void {
    this.emit('debug', msg, fields)
  }
  info(msg: string, fields?: LogFields): void {
    this.emit('info', msg, fields)
  }
  warn(msg: string, fields?: LogFields): void {
    this.emit('warn', msg, fields)
  }
  error(msg: string, fields?: LogFields): void {
    this.emit('error', msg, fields)
  }
}

/** The shared app logger. */
export const logger = new Logger(resolveLevel())

/** Test/advanced use: build a logger pinned to an explicit level. */
export function createLogger(level: LogLevel, base?: LogFields): Logger {
  return new Logger(level, base)
}

export type { Logger }
