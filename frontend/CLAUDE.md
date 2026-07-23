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

**Complete record on the overview graph:** `Timeseries.TSGas` carries
`background` — the raw concentration points not assigned to any spot —
and `TimeSeriesPlot` draws them as a faint trace in the all-spots view (skipped
in single-spot view so the axis stays zoomed to the spot), so no part of the
LI-7810 record silently disappears from the graph. The backend **downsamples**
`background` (uniform thinning to a cap) so long campaigns don't make Plotly
stutter; all traces already render via `scattergl` (WebGL).

**Per-spot shift context:** `GasDetail.context` (optional) is a wider slice of the
raw record around the spot; `RegressionPlot` draws it as a faint "Surrounding
record" trace behind the spot's own points, so the manual-shift control shows far
more than the fit window and it's easy to see where to move it.

**Manual per-spot shift + crop:** `SpotDetail` has a "Manual fit window" control
(−30/−5/+5/+30 s nudges + a seconds input + Apply / Reset to auto) that calls
`api.setSpotFit(id, nr, offsetS, endOffsetS?)` (`PUT …/spots/{nr}/fit`,
`offsetS=null` resets both). The offset is **relative to the recorded start and may
be negative** (shift the window *earlier*, into the lead margin of data the matcher
keeps before the recorded start). A **"Crop the end too"** toggle reveals a second
(end) offset so the window can be trimmed at **both ends** for spots disturbed at
both ends; unticked, the window keeps its full length so a shift never cuts the
measurement (Apply is disabled if the end isn't after the start). The saved window
overrides the page fit mode for that spot (`SpotDetail.mode === 'manual'`,
`manual_offset_s`/`manual_end_offset_s`, `fit_end_s`), and the drawer calls
`onFitChanged` so Results refetches the table + graph (a `fitVersion` counter in
Results deps). **Out-of-window points are NOT discarded:** both plots draw them in
the gas colour (faded) labelled "Outside window (recorded)" — not grey "excluded" —
so the whole measurement line stays visible while picking the window; only spots
with no readings/temperature are truly skipped (low R² never hides a spot).

**Temperature confirmation:** the Confirm step is now two pages — `ConfirmNotes`
("Approve & continue" saves notes, then routes to
`/analyses/:id/confirm-temperature`) → `ConfirmTemperature` (reviews the parsed
temperature via `api.getTemperature`: count, time range, min/max/mean, and a
`TemperaturePlot` preview; "Confirm & compute" runs the match + fit and goes to
Results). If the temperature can't be read (`available===false`) the page points the
user back to Upload rather than failing at match time. Both pages sit under the
"Confirm" `Stepper` step.

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
npm test               # vitest run — co-located unit/component tests (src/**)
npm run test:e2e       # playwright — e2e smoke suite (tests/e2e/, builds + previews)
npm run lint           # oxlint
npm run format:check   # prettier --check   (npm run format to apply)
npm run typecheck      # tsc -b --noEmit
```
Lint, format, type-check, and tests must be **green before every commit**. Tests
are two layers: **Vitest** unit/component tests co-located under `src/**` (Vitest is
scoped there via `vite.config.ts` `test.include`), and **Playwright** e2e specs in
`tests/e2e/` (first run needs `npx playwright install --with-deps chromium`). See
`tests/README.md`. CI runs both plus lint/typecheck/build (`.github/workflows/test.yml`).

## Observability (logging + monitoring)
Structured, level-gated logging (`src/lib/logger.ts`, `VITE_LOG_LEVEL`) with
redaction; the API client threads an `X-Request-ID` per call that matches the
backend logs. **Error/performance monitoring is optional Sentry**
(`src/lib/monitoring.ts`, `@sentry/react`): **off unless `VITE_SENTRY_DSN` is set**.
When on, it captures uncaught errors + unhandled rejections (`Sentry.ErrorBoundary`
in `main.tsx`), tags the current `route` (`App.tsx`), adds an API breadcrumb per
request carrying the same `requestId` (link to backend), and redacts sensitive
values with the logger's key list before send. Source maps upload at build only
when `SENTRY_AUTH_TOKEN` is set and are never served publicly. Env (build-time):
`VITE_SENTRY_DSN`, `VITE_SENTRY_ENVIRONMENT`, `VITE_SENTRY_RELEASE`,
`VITE_SENTRY_TRACES_SAMPLE_RATE`. See `../report.md` for details + alert rules.

## Layout (`src/`)
```
api/          typed fetch client (client.ts) + types (the backend seam)
pages/        Home, Upload, ConfirmNotes, ConfirmTemperature, Results, SpotDetail, ProcessingLog, ...
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
