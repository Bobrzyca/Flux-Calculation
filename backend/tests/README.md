# Backend tests

Run everything from `backend/` with the venv active: `pytest`.

## Layout

pytest discovers tests recursively under `tests/` (`testpaths = ["tests"]`), so
files at the top level and in subdirectories all run together.

| Location | Kind | Status |
|---|---|---|
| `tests/*.py` (top level) | unit + integration (parsing, flux math, matching, API via `TestClient`) | **current** — the existing, green suite |
| `tests/security/` | security baseline (debug off, CORS, error hygiene, correlation id) | **current** |
| `tests/unit/` | pure-unit tests, once split out of the flat files | *placeholder — later* |
| `tests/integration/` | end-to-end API/pipeline integration | *placeholder — later; `test_e2e.py` + `test_api_*.py` are the de-facto integration suite today* |

**Why the existing tests weren't moved:** the flat suite is green and covered by
CI as-is. The `unit/` and `integration/` subdirs mirror the target repo tree; we
add depth there incrementally rather than restructuring a passing suite in one go.
Shared fixtures live in `tests/conftest.py` and apply to every subdirectory.
