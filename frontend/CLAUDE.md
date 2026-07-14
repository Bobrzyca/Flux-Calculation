# CLAUDE.md — Flux Calculation frontend

Standing instructions for the **React + Vite + TypeScript** UI. Read alongside the
root [`../CLAUDE.md`](../CLAUDE.md) (cross-app picture + engineering rules) and the
frontend brief [`../assignment/frontend.md`](../assignment/frontend.md) (the detailed
screen/behaviour spec).

The frontend is a **local, single-user, desktop-style web tool**: a stepper-driven
flow **Upload → Confirm → Results**, plus per-spot detail and a processing-log view
that open from Results, and a Home list of saved analyses. Tone: a competent,
friendly field colleague — plain sentences, no jargon, every transformation visible.

## Phase note: mock data only
This app currently runs on **mock data**. Everything that will talk to the backend
goes through the typed client in **`src/api/`**; the seams are marked
**`TODO: connect to API`** in `src/api/client.ts`, with the mock shapes in
`src/api/mocks/`. The backend is a black box behind that client — the UI never
assumes backend internals. When wiring the real API, it lives under the **`/api`**
prefix over HTTP.

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
api/          typed client + types + mocks (the backend seam; TODO: connect to API)
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
