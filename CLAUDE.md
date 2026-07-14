# CLAUDE.md — Flux Calculation

Standing instructions for developing this app. Base decisions on `project-brief.md`;
where the brief is silent I use common defaults, marked **(assumption)**.

## Project
Flux Calculation is a **local, single-user desktop-style web tool** for closed-chamber
greenhouse-gas researchers (the author and lab friends, LI-7810 instrument family). It
ingests four raw field files — a 1 Hz LI-7810 CO₂/CH₄ concentration log, hand-typed
start/stop time notes, a temperature xlsx, and an IMGW pressure file — auto-matches them
by timestamp (with a correctable instrument-clock offset), fits a linear regression of
concentration vs. time per gas per spot, and computes CO₂/CH₄ flux across a full unit
ladder. An LLM normalises the messy notes/pressure into strict JSON (human-confirmed
before use); the physics/flux math is pure code and never LLM-touched. Every
transformation is exposed for supervision (per-spot regression plots, a processing log).

## Tech stack
**Frontend**
- React 19 + **Vite** + **TypeScript**, Tailwind CSS for styling.
- **Plotly** (`react-plotly.js`) for the per-spot regression plot (zoom/pan).
- Package manager: **npm** (matches the server's installed toolchain).
- Test runner: **Vitest** + React Testing Library.
- Lint/format: **oxlint** + **Prettier**. (The current Vite `react-ts` template
  ships oxlint, not ESLint, so we kept it and added Prettier for formatting.)
- Routing: **react-router-dom** v7. Path alias `@/*` → `src/*` (Vite + tsconfig).
- Plotly is loaded lazily (`React.lazy`) so it stays in its own code-split chunk.

**Backend**
- **Python 3.14** + **FastAPI**, served with **uvicorn**.
- Data/math: **pandas**, **numpy**, **scipy** (`scipy.stats.linregress` for slope + R²).
- Files: **openpyxl** (xlsx), **python-docx** (Word notes).
- LLM: an official Python LLM SDK in **structured/JSON-output mode** for the notes +
  pressure parser. Default to the latest capable **Anthropic** model **(assumption —
  confirm provider)**; keep the key in `.env`, never committed.
- Package/deps: **pip** + `requirements.txt` inside a **venv** (or `pyproject.toml`)
  **(assumption)**.
- Test runner: **pytest**.
- Lint/format + types: **ruff** (lint + format) and **mypy** **(assumption)**.

**Database**
- **SQLite**, one file per install (zero setup, travels with the analysis). Tables per
  the brief: `Analysis`, `Spot`, `Reading`, `FluxResult`. Raw uploaded files are also
  saved on disk and referenced by the `Analysis`, so any campaign can be re-run.
  ORM: **SQLModel/SQLAlchemy** **(assumption)**.

**External workflow**
- **n8n** for the on-demand, per-campaign AI quality-check (app → n8n results out, n8n →
  app report back). The app never depends on n8n being up.

## Repository structure
```
frontend/                 self-contained React app
  src/
    components/           shared UI
    pages/                Upload, ConfirmNotes, Results, SpotDetail, ProcessingLog
    api/                  typed client for the backend
    lib/                  helpers, formatting, unit ladder display
  tests/                  Vitest specs (co-located *.test.tsx also fine)
  index.html, vite.config.ts, package.json, tailwind.config.*

backend/                  self-contained FastAPI app
  app/
    main.py               FastAPI entry, route wiring
    api/                  routers (upload, analyses, results, webhooks)
    core/                 config, settings, chamber-constant defaults
    parsing/              LI-7810, temperature, notes, pressure loaders
    llm/                  notes/pressure parser (prompt + schema + validation)
    matching/            time-shift + auto-match by timestamp
    flux/                 regression + closed-chamber flux + unit ladder (pure)
    db/                   SQLite models, session, migrations
    schemas/              Pydantic request/response models
  tests/                  pytest, mirrors app/ layout
  sample_data/            small fixture files for tests
  requirements.txt / pyproject.toml, .env.example

reference/               original R script, cleaned to run on repo sample files;
                         method-of-record for validation. NOT called by the app.
```
Each app is self-contained: its own deps, tests, config, and run commands.

## How we work (engineering rules)
1. **Test-driven.** Write or update a *failing* test first, then the code to pass it.
   Keep tests fast and close to the code.
2. **Green before commit.** Linter, formatter, and type checker (mypy / tsc) must be
   clean on every change.
3. **Small, focused commits**, Conventional Commits style: `feat:`, `fix:`, `chore:`,
   `test:`, `docs:`.
4. **Never commit secrets.** Keep a `.env.example` with empty values; `.env` in
   `.gitignore`. Never print `.env` contents.
5. **Readable over clever.** Match existing patterns; prefer conventional code.
6. **Explain non-obvious decisions** in the commit message or a comment — I am learning.
7. **The flux math is pure code**, validated against the R reference; the LLM only
   normalises input formats, and its output is always human-confirmed before use.
8. **Validate the reference.** On a known campaign (e.g. 2 July 2026 Kampinos), the
   Python fluxes must match the R script; investigate any disagreement.

## Commands
_Fill in as each app is scaffolded._

**Backend** (from `backend/`)
- Install: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Dev: `uvicorn app.main:app --reload`
- Test: `pytest`
- Lint/format/types: `ruff check . && ruff format --check . && mypy .`

**Frontend** (from `frontend/`)
- Install: `npm install`
- Dev: `npm run dev`
- Build: `npm run build`
- Test: `npm test` (watch: `npm run test:watch`)
- Lint/format/types: `npm run lint && npm run format:check && npm run typecheck`
- Runs on **mock data only** this phase (see `src/api/`); real endpoints are
  marked `TODO: connect to API` in `src/api/client.ts`.

## Definition of done
A change is done when: the relevant tests pass, lint/format/type-check are clean, the
app runs, and this `CLAUDE.md` is updated if the workflow or commands changed.

## Open questions to confirm (from the brief)
Chamber constants (0.0625 m² / 15.625 L), IMGW pressure format & units, low-R² flag
threshold (default 0.80), and whether CSV is a third export format — confirm before
building the affected parts.
