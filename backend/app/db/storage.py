"""On-disk storage for raw uploaded files.

Each analysis keeps its four raw inputs under ``data/<analysis_id>/`` named by
role (``concentration``, ``notes``, ``temperature``, ``pressure``), preserving
the original file extension. Keeping the raw bytes lets any campaign be re-run
later (per the brief). Kept free of FastAPI types so routers stay thin.
"""

import shutil
from pathlib import Path

from app.core.config import settings

# The four raw inputs a campaign is built from.
ALLOWED_ROLES = frozenset({"concentration", "notes", "temperature", "pressure"})


def analysis_dir(analysis_id: str) -> Path:
    """Directory holding one analysis's raw files (not created here)."""
    return Path(settings.data_dir) / analysis_id


def save_upload(analysis_id: str, role: str, filename: str, content: bytes) -> Path:
    """Save ``content`` as ``data/<analysis_id>/<role><ext>`` and return the path.

    ``ext`` is taken from ``filename`` (e.g. ``.txt``, ``.xlsx``). Raises
    ``ValueError`` for an unknown role.
    """
    if role not in ALLOWED_ROLES:
        raise ValueError(
            f"Unknown file role {role!r}; expected one of {sorted(ALLOWED_ROLES)}"
        )
    ext = Path(filename).suffix
    dest_dir = analysis_dir(analysis_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{role}{ext}"
    dest.write_bytes(content)
    return dest


def read_stored(path: Path) -> bytes:
    """Read a previously stored file back as raw bytes."""
    return Path(path).read_bytes()


def delete_analysis_files(analysis_id: str) -> None:
    """Remove an analysis's stored-files directory (no-op if it doesn't exist)."""
    directory = analysis_dir(analysis_id)
    if directory.is_dir():
        shutil.rmtree(directory)


def remove_stored(analysis_id: str, role: str) -> None:
    """Delete any stored file(s) for a role (all extensions), if present.

    Used when replacing a file so a new upload with a different extension can't
    leave the old one behind (``find_stored`` globs ``<role>.*``).
    """
    if role not in ALLOWED_ROLES:
        raise ValueError(
            f"Unknown file role {role!r}; expected one of {sorted(ALLOWED_ROLES)}"
        )
    directory = analysis_dir(analysis_id)
    if not directory.is_dir():
        return
    for existing in directory.glob(f"{role}.*"):
        existing.unlink()


def find_stored(analysis_id: str, role: str) -> Path | None:
    """Return the stored file for a role (any extension), or None if absent."""
    if role not in ALLOWED_ROLES:
        raise ValueError(
            f"Unknown file role {role!r}; expected one of {sorted(ALLOWED_ROLES)}"
        )
    directory = analysis_dir(analysis_id)
    if not directory.is_dir():
        return None
    matches = sorted(directory.glob(f"{role}.*"))
    return matches[0] if matches else None
