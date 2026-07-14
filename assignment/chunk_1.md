# Chunk 1 — Backend initialisation

**Description:** Stand up the `backend/` Python + FastAPI project: directory
structure, dependency manifest, a runnable base server with a health endpoint
and CORS for the frontend, plus `.env.example` and a `.gitignore` that excludes
`.env`. No business logic yet — just a server that boots and a test that proves
it.

## Exactly what to do
1. Create the `backend/` tree from `CLAUDE.md` "Repository structure":
   ```
   backend/
     app/
       __init__.py
       main.py            # FastAPI entry, route wiring
       core/
         __init__.py
         config.py        # settings loaded from env (pydantic-settings)
       api/__init__.py
       db/__init__.py
       parsing/__init__.py
       matching/__init__.py
       flux/__init__.py
       schemas/__init__.py
       llm/__init__.py    # placeholder only — see note below
     tests/
       __init__.py
       test_health.py
     sample_data/         # empty for now; fixtures arrive in later chunks
     pyproject.toml
     .env.example
     .gitignore
   ```
2. **Dependency manifest** — use `pyproject.toml` (PEP 621). Runtime deps:
   `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `pandas`,
   `numpy`, `scipy`, `openpyxl`, `python-docx`, `sqlmodel`, `python-multipart`
   (needed for file uploads). Dev deps: `pytest`, `httpx` (for the test client),
   `ruff`, `mypy`. Pin sensible current versions.
3. **`app/core/config.py`** — a `Settings` class (pydantic-settings) with:
   `app_name="Flux Calculation API"`, `data_dir` (default `./data`, where
   uploaded files + the SQLite file will live), `database_url`
   (default `sqlite:///./data/flux.db`), `cors_origins`
   (default `["http://localhost:5173"]` — the Vite dev server), and a placeholder
   `llm_api_key: str | None = None`. Read from `.env`.
4. **`app/main.py`** — create the FastAPI app, add `CORSMiddleware` using
   `settings.cors_origins`, and expose `GET /api/health` returning
   `{"status": "ok", "app": settings.app_name}`. Mount everything under an
   `/api` prefix (the frontend calls `/analyses`, `/analyses/{id}/...`; decide
   the prefix now and record it in `backend/CLAUDE.md` in chunk 2 — recommended:
   serve routes at `/api/analyses` and set the frontend base URL accordingly).
5. **`.env.example`** — every key from `Settings` with empty/placeholder values
   (`LLM_API_KEY=`). **`.gitignore`** — ignore `.env`, `data/`, `__pycache__/`,
   `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `*.db`.
6. **`app/llm/__init__.py`** — leave a one-line module docstring:
   `# TODO: LLM abstraction + field-notes/pressure parser (seminar 6).` Do not
   implement anything here.
7. **`tests/test_health.py`** — use FastAPI `TestClient` to assert
   `GET /api/health` returns 200 and the expected JSON.
8. Configure `ruff` and `mypy` in `pyproject.toml` (line length, target version
   3.14, `mypy` strict-ish on `app/`).

## Files created / changed
- New: everything under `backend/` listed above.
- Changed: none in `frontend/`.

## How to verify
- `cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
  (or `pip install -r` if you prefer a requirements file — but pyproject is the
  spec here).
- `uvicorn app.main:app --reload` boots with no errors; `curl localhost:8000/api/health`
  returns `{"status":"ok","app":"Flux Calculation API"}`.
- `pytest` passes (the health test).
- `ruff check . && ruff format --check . && mypy .` are clean.
- Confirm `.env` is git-ignored (`git status` shows no `.env`).

## Dependencies
None — this is the first backend chunk.

## Reminder
Follow the repo `CLAUDE.md` rules: test-driven (write the failing health test
first), keep lint/format/type-check clean, small Conventional Commits
(`chore:`/`feat:` as appropriate).

Commit and push.
