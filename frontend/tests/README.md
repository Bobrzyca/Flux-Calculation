# Frontend tests

Two layers, run by different tools:

| Location | Tool | Command | Needs a backend? |
|---|---|---|---|
| `src/**/*.test.{ts,tsx}` (co-located unit/component) | **Vitest** + RTL | `npm test` | no (fetch stub) |
| `tests/e2e/*.spec.ts` (end-to-end) | **Playwright** | `npm run test:e2e` | smoke: no; deeper flows: yes |

**Why unit tests stay co-located:** they sit next to the code they cover (project
convention, see `../CLAUDE.md`) and are green in CI as-is; we didn't move them into
a `tests/unit/` folder. Vitest is scoped to `src/**` (see `vite.config.ts`
`test.include`), so it never picks up the Playwright specs.

**e2e today:** `tests/e2e/smoke.spec.ts` builds the app, serves it with `vite
preview`, and checks the shell renders (backend-independent). Deeper journeys
(upload → confirm → results) that need a live FastAPI backend are added later —
start `uvicorn` in `backend/` and point specs at real fixtures.

First run locally needs the browser: `npx playwright install --with-deps chromium`.
