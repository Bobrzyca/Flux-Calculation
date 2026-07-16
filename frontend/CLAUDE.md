# CLAUDE.md — Flux Calculation frontend

Standing instructions for the **React + Vite + TypeScript** UI. Read alongside the
root [`../CLAUDE.md`](../CLAUDE.md) (cross-app picture + engineering rules) and the
frontend brief [`../assignment/frontend.md`](../assignment/frontend.md) (the detailed
screen/behaviour spec).

The frontend is a **local, single-user, desktop-style web tool**: a stepper-driven
flow **Upload → Confirm → Results**, plus per-spot detail and a processing-log view
that open from Results, and a Home list of saved analyses. Tone: a competent,
friendly field colleague — plain sentences, no jargon, every transformation visible.

## Talking to the backend
The app runs on the **real FastAPI backend** over HTTP. All calls go through the
typed client in **`src/api/client.ts`** (`fetch`); the base URL is
**`VITE_API_BASE_URL`** (default `http://localhost:8000/api`, set in `.env` — see
`.env.example`, git-ignored). The backend is a black box behind the client — the UI
never assumes internals. Backend errors arrive as `{"detail": {code, message,
field?}}` and become an `ApiError { code, field }` so the Upload screen highlights
the right field (409 duplicate name, 422 missing-file / bad-LI-7810).

Run the backend (`uvicorn app.main:app --reload` in `backend/`) alongside
`npm run dev`; keep the backend's `CORS_ORIGINS` in sync with the dev origin.

**Fit mode (one global switch):** the Results page has a **"Block auto-fit (whole
recording)"** checkbox. It holds one `fitMode: 'auto' | 'full'` and threads it to
`api.getResults`, `api.getTimeseries`, and `SpotDetail` (as a prop) — so the table,
the graph, and the detail drawer all recompute together (`?fit_mode=full` blocks the
automatic best-window selection and fits each spot's whole recording). `SpotDetail`
shows how far the fit window shifted after the recorded start, its length, whether it
was shortened to recover R², and the per-gas isolated-spike drop count
(`SpotDetail.fit_offset_s/fit_window_s/window_shortened`, `GasFit.n_spikes`).

**Deferred features keep their placeholders** end-to-end: `quality_check.available
=== false` → "quality check unavailable" (n8n, `TODO: later seminar`);
`parse_failed` fallback on Confirm (LLM parser, `TODO: seminar 6`). Neither is built.

**Tests** don't need a live backend: a fetch stub (`src/test/apiMock.ts`, installed
in `src/test/setup.ts`) serves the fixtures in `src/test/mockData.ts`. Those
fixtures are **test-only** — nothing in the app's runtime imports them.

## Tech stack
- **React 19** + **Vite** + **TypeScript**; **Tailwind CSS** (`@tailwindcss/vite`).
- **Plotly** (`react-plotly.js`) for the per-spot regression plot, loaded lazily so
  it stays in its own code-split chunk.
- Routing: **react-router-dom** v7. Path alias **`@/*` → `src/*`**.
- Tests: **Vitest** + React Testing Library (jsdom). Specs are co-located
  (`*.test.tsx`) or under `src/test/`.
- Lint/format: **oxlint** + **Prettier** (the Vite `react-ts` template ships oxlint,
  not ESLint).

## How to run / test / lint
From `frontend/`:
```bash
npm install
npm run dev            # Vite dev server (http://localhost:5173)
npm run build          # tsc -b && vite build
npm test               # vitest run   (watch: npm run test:watch)
npm run lint           # oxlint
npm run format:check   # prettier --check   (npm run format to apply)
npm run typecheck      # tsc -b --noEmit
```
Lint, format, type-check, and tests must be **green before every commit**.

## Layout (`src/`)
```
api/          typed fetch client (client.ts) + types (the backend seam)
pages/        Home, Upload, ConfirmNotes, Results, SpotDetail, ProcessingLog, ...
components/    shared UI (Button, Card, Stepper, RegressionPlot, states, ...)
hooks/        reusable hooks (e.g. useAsync)
lib/          helpers — formatting, unit-ladder display, constants, cn()
theme/        ThemeProvider (light/dark)
```

## The update rule
**When you add a screen or component, change a route, or change the API-client
shape/commands, update this file** (and the root `../CLAUDE.md` if the cross-app
picture changed, e.g. once the UI talks to the real API) **in the same commit.**
Docs drift is a bug.
