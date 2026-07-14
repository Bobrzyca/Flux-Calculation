# Chunk 13 — Connect the frontend to the backend

**Description:** Replace the frontend's in-memory mock at every
`TODO: connect to API` marker with real HTTP calls to the FastAPI backend. After
this chunk the app runs on live data end-to-end (minus the deferred LLM/n8n
pieces, which keep their placeholders).

## Exactly what to do
1. **API base URL:** add `VITE_API_BASE_URL` (default `http://localhost:8000/api`)
   via a `frontend/.env` / `.env.example`; read it in the client. Keep CORS in
   sync with chunk 1.
2. **Rewrite `frontend/src/api/client.ts`** — keep the exact same function
   signatures and return types (the rest of the app depends on them); swap each
   mock body for a `fetch` call. Replace these markers:
   - `GET /analyses`, `GET /analyses/{id}`, `DELETE /analyses/{id}`
   - `POST /analyses` (build `FormData` with the four files + fields;
     multipart). Map backend **409** → the duplicate-name error and **422** →
     the missing-file / bad-LI-7810 error, preserving `ApiError { code, field }`
     so the Upload screen keeps highlighting the right field.
   - `GET/PUT /analyses/{id}/notes`, `POST /analyses/{id}/match`
   - `GET /analyses/{id}/results`, `GET /analyses/{id}/spots/{nr}`,
     `GET /analyses/{id}/log`
   - `GET /analyses/{id}/export?format=…` → fetch the blob and trigger download
     (the pages already call `exportResults` and create the object URL).
3. **Keep deferred placeholders:** the Results screen already handles
   `quality_check.available === false` → keep showing "quality check unavailable"
   with a `TODO: n8n (later seminar)` note; the Confirm screen keeps its
   `parse_failed` fallback path with a `TODO: LLM parser (seminar 6)` note. Do
   not build either.
4. Delete or clearly quarantine `src/api/mocks/` (move the fixtures to test-only
   usage if any test needs them). Ensure nothing in the app imports mocks at
   runtime.
5. Update the frontend tests that relied on the mock client: switch the
   integration tests (Home, Results) to mock `fetch` (e.g. with a small MSW-style
   handler or `vi.fn()` stubs) so they don't need a live backend.

## Files created / changed
- Changed: `frontend/src/api/client.ts`, `frontend/.env.example` (new),
  affected tests.
- Removed/quarantined: `frontend/src/api/mocks/`.

## How to verify
- Run the backend (`uvicorn app.main:app --reload`) and the frontend
  (`npm run dev`) together. Walk the full flow in the browser: Home lists real
  analyses → New analysis, upload the four `sample_data` files, Run → Confirm
  shows real parsed notes → Approve → Results shows computed fluxes → open a spot
  (real regression plot) → open the processing log → export a file that
  downloads and opens.
- Error branches: uploading a non-LI-7810 file shows the format error on the
  right dropzone; a duplicate name warns.
- `npm run lint && npm run format:check && npm run typecheck && npm test` clean;
  backend `pytest`/`ruff`/`mypy` still clean.

## Dependencies
Chunks 8–12 (all backend endpoints must exist). Backend must be runnable.

## Reminder
Follow the repo `CLAUDE.md` rules: keep the client's types stable, tests updated,
lint/format/type-check clean, Conventional Commits (`feat:`/`refactor:`). Update
`frontend/CLAUDE.md` (now talks to a real API) and the root `CLAUDE.md` if the
run instructions change.

Commit and push.
