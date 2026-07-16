/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FastAPI backend (default http://localhost:8000/api). */
  readonly VITE_API_BASE_URL?: string
  /**
   * Minimum log level printed by the app logger:
   * `debug` | `info` | `warn` | `error` | `silent`.
   * Default: `debug` in dev, `warn` in production builds.
   */
  readonly VITE_LOG_LEVEL?: string
  /** Sentry DSN. Monitoring is OFF when unset (the app runs fine without it). */
  readonly VITE_SENTRY_DSN?: string
  /** Environment tag on Sentry events (e.g. production). Default `development`. */
  readonly VITE_SENTRY_ENVIRONMENT?: string
  /** Release id — set from the git commit SHA at build time. */
  readonly VITE_SENTRY_RELEASE?: string
  /** Performance trace sample rate 0..1 (default 0 = off). */
  readonly VITE_SENTRY_TRACES_SAMPLE_RATE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
