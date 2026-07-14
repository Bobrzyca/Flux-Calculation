# Chunk 2 — Project context files

**Description:** Make the two-app repo self-documenting. Update the **root**
`CLAUDE.md` to describe both apps and how they fit together, and create
`backend/CLAUDE.md` as the backend's standing instructions. Both must carry the
rule: whenever you add a feature/endpoint or change structure, update the
relevant `CLAUDE.md`.

## Exactly what to do
1. **Update root `/CLAUDE.md`** (it currently only covers the server/ops role).
   Add a short "Project" section describing Flux Calculation as a two-app repo:
   - `frontend/` — React + Vite + TS app (already built, runs on mock data;
     point to `frontend/CLAUDE.md`).
   - `backend/` — Python + FastAPI app (point to `backend/CLAUDE.md`).
   - `reference/` — R script method-of-record (may not exist yet; note it).
   Explain that the frontend talks to the backend over HTTP under `/api`, that
   the backend is local/single-user, and where secrets live (`backend/.env`,
   never committed). Keep the existing server/ops content.
2. **Create `backend/CLAUDE.md`** covering:
   - **Tech stack:** Python 3.14, FastAPI + uvicorn, pandas/numpy/scipy,
     openpyxl, python-docx, SQLModel + SQLite, pytest, ruff + mypy.
   - **How to run:** venv + install, `uvicorn app.main:app --reload`, health URL.
   - **How to test / lint:** `pytest`, `ruff check .`, `ruff format --check .`,
     `mypy .`.
   - **API structure:** route prefix (`/api`), where routers live (`app/api/`),
     request/response models in `app/schemas/`, the pipeline overview
     (upload → parse notes → confirm → match → fit/flux → results/log/export).
   - **Database schema:** the four tables (`Analysis`, `Spot`, `Reading`,
     `FluxResult`) with their columns (copy from `project-brief.md` "Data stored
     by the application"), and that raw files are stored on disk under `data/`
     and referenced by the analysis.
   - **How to add an endpoint:** the recipe — add/extend a router in `app/api/`,
     define Pydantic schemas in `app/schemas/`, wire it in `app/main.py`, write a
     test in `backend/tests/` first, keep pure logic in `parsing/`/`matching/`/
     `flux/` (not in routers).
   - **Deferred features:** note that the LLM field-notes/pressure parser
     (`app/llm/`) is **TODO: seminar 6**, and the n8n quality-check workflow is a
     **TODO: later seminar** — the app must run fully without either.
   - **The update rule (state it explicitly):** "When you add a feature, add or
     change an endpoint, or change the structure/commands, update this file (and
     the root `CLAUDE.md` if the cross-app picture changed) in the same commit."
3. Make sure the same update rule is present (or referenced) in the root
   `CLAUDE.md` too.

## Files created / changed
- Changed: `/CLAUDE.md`.
- New: `backend/CLAUDE.md`.

## How to verify
- Read both files top to bottom: a newcomer can run and test the backend, find
  where endpoints/schemas/logic go, understand the DB schema, and knows the
  update rule and what's deferred.
- Cross-links resolve (paths to `frontend/CLAUDE.md`, `backend/CLAUDE.md` exist).
- No code changes needed; nothing to lint, but keep Markdown tidy.

## Dependencies
Chunk 1 (the backend structure and commands must exist to document them).

## Reminder
Follow the repo `CLAUDE.md` rules: docs-only change, use a `docs:` Conventional
Commit.

Commit and push.
