# Flux Calculation — frontend

React 19 + Vite + TypeScript UI for the Flux Calculation app. A stepper-driven flow
**Upload → Confirm → Results**, plus per-spot detail and a processing-log view, and a
Home list of saved analyses. It talks to the FastAPI backend over HTTP through a
typed `fetch` client. See [`CLAUDE.md`](CLAUDE.md) for the full developer guide and
[`../README.md`](../README.md) for the whole system.

## Quick start

```bash
npm install
cp .env.example .env          # .env is git-ignored
npm run dev                   # http://localhost:5173
```

Run the backend (`uvicorn app.main:app --reload` in `../backend/`) alongside the dev
server. The API base URL is `VITE_API_BASE_URL` (default
`http://localhost:8000/api`); keep the backend's `CORS_ORIGINS` in sync with the dev
origin.

## Commands

```bash
npm test              # vitest — co-located unit/component tests (src/**)
npm run test:e2e      # playwright e2e smoke (first run: npx playwright install --with-deps chromium)
npm run lint          # oxlint
npm run format:check  # prettier --check   (npm run format to apply)
npm run typecheck     # tsc -b --noEmit
npm run build         # tsc -b && vite build
```

Lint, format, type-check, and tests must be green before every commit.

## Stack

- **React 19** + **Vite** + **TypeScript**, **Tailwind CSS**.
- **Plotly** (`react-plotly.js`) for the per-spot regression plot, lazily loaded.
- Routing: **react-router-dom** v7; path alias **`@/*` → `src/*`**.
- Tests: **Vitest** + React Testing Library (unit/component), **Playwright** (e2e).
- Lint/format: **oxlint** + **Prettier**.

## Layout (`src/`)

```text
api/          typed fetch client (client.ts) + types — the backend seam
pages/        Home, Upload, ConfirmNotes, Results, SpotDetail, ProcessingLog
components/    shared UI (Button, Card, Stepper, RegressionPlot, states, …)
hooks/        reusable hooks (e.g. useAsync)
lib/          formatting, unit-ladder display, constants, cn()
theme/        ThemeProvider (light/dark)
```

## Observability

Structured, level-gated logging (`src/lib/logger.ts`, `VITE_LOG_LEVEL`) with
redaction; the API client threads an `X-Request-ID` per call that matches the backend
logs. Optional Sentry (`src/lib/monitoring.ts`) is off unless `VITE_SENTRY_DSN` is
set. Full reference: [`../docs/operations.md`](../docs/operations.md).
