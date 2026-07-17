#!/usr/bin/env python3
"""Export the backend's OpenAPI schema to ``docs/openapi.json``.

The spec is GENERATED from the live FastAPI app (its route decorators + Pydantic
schemas), never hand-written, so it can't drift from the code. Regenerate after
any endpoint/schema change:

    cd backend && . .venv/bin/activate
    python scripts/export_openapi.py

Or from the repo root:  npm run docs:generate

CI runs the same command and fails if the committed ``docs/openapi.json`` is out
of date (see the ``docs`` job in ``.github/workflows/test.yml``), which keeps the
published spec honest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make ``app`` importable when run as a plain script from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

OUTPUT = BACKEND_DIR.parent / "docs" / "openapi.json"


def main() -> int:
    from app.main import app  # imported here so sys.path is set first

    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys for a stable, diff-friendly file; trailing newline for POSIX tools.
    OUTPUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUTPUT.relative_to(BACKEND_DIR.parent)} "
        f"— {len(schema['paths'])} paths, OpenAPI {schema['openapi']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
