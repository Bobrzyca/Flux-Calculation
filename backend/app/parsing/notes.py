"""Time-window notes parser + validation (deterministic; no LLM).

Handles well-formed CSV / XLSX / DOCX notes with the columns Nr, Start, Stop,
GPS, light/dark, location (common English + simple Polish header spellings). It
normalises clean time formats (``9.38``, ``9:38``, ``09:38:00`` → ``HH:MM:SS``)
but does **not** try to repair genuinely messy handwriting — that is the smart
feature's job. Unparseable values are left blank and surfaced by ``validate_notes``.

# TODO: LLM tolerant parsing of messy field notes (seminar 6). This
# deterministic parser covers well-formed files.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Flag values mirror the frontend's NoteFlag union.
STOP_BEFORE_START = "stop_before_start"
GPS_MISSING = "gps_missing"
UNPARSEABLE_TIME = "unparseable_time"
LOCATION_MISSING = "location_missing"

# Canonical column -> accepted header spellings (lower-cased, stripped).
_HEADER_ALIASES: dict[str, set[str]] = {
    "nr": {"nr", "no", "no.", "lp", "lp.", "spot", "numer"},
    "start": {"start", "start_time", "poczatek", "początek", "od"},
    "stop": {"stop", "stop_time", "end", "koniec", "do"},
    "gps": {"gps", "coords", "coordinates", "wspolrzedne", "współrzędne"},
    "light_dark": {"light/dark", "light_dark", "light-dark", "type", "l/d"},
    "location": {"location", "opis", "miejsce", "lokalizacja", "description"},
}


@dataclass
class NoteRow:
    """One parsed notes row. ``flags`` is filled by ``validate_notes``."""

    nr: int
    start_time: str  # "HH:MM:SS", or "" if unparseable
    stop_time: str
    gps: str
    light_dark: str  # "light" | "dark" | ""
    location: str
    flags: list[str] = field(default_factory=list)


def _normalize_time(raw: str) -> str:
    """Normalise a clean time to ``HH:MM:SS``; return ``""`` if unparseable."""
    s = raw.strip().replace(".", ":")
    if not s:
        return ""
    parts = s.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return ""
    if len(nums) == 2:
        hour, minute, second = nums[0], nums[1], 0
    elif len(nums) == 3:
        hour, minute, second = nums
    else:
        return ""
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        return ""
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _normalize_light_dark(raw: str) -> str:
    s = raw.strip().lower()
    if not s:
        return ""
    if s[0] in {"l", "j"}:  # light / jasny
        return "light"
    if s[0] in {"d", "c"}:  # dark / ciemny
        return "dark"
    return ""


def _parse_nr(raw: str) -> int:
    """Leading integer of the Nr cell (tolerates a trailing redo marker like ``3!``)."""
    match = re.match(r"\s*(\d+)", raw)
    return int(match.group(1)) if match else 0


def _read_table(path: str | Path) -> list[dict[str, str]]:
    """Read the notes file into a list of string-keyed/valued row dicts."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str, engine="openpyxl").fillna("")
    elif suffix == ".docx":
        return _read_docx_table(path)
    else:
        raise ValueError(f"Unsupported notes format: {suffix!r}")
    return [
        {str(k): "" if v is None else str(v) for k, v in record.items()}
        for record in frame.to_dict("records")
    ]


def _read_docx_table(path: str | Path) -> list[dict[str, str]]:
    """Read the first table of a Word document into row dicts (header = row 0)."""
    from docx import Document

    document = Document(str(path))
    if not document.tables:
        return []
    table = document.tables[0]
    header = [cell.text.strip() for cell in table.rows[0].cells]
    rows: list[dict[str, str]] = []
    for row in table.rows[1:]:
        values = [cell.text.strip() for cell in row.cells]
        rows.append(dict(zip(header, values, strict=False)))
    return rows


def _resolve_columns(headers: list[str]) -> dict[str, str]:
    """Map each canonical field to the actual header present in the file."""
    resolved: dict[str, str] = {}
    for header in headers:
        key = header.strip().lower()
        for canonical, aliases in _HEADER_ALIASES.items():
            if key in aliases:
                resolved[canonical] = header
    return resolved


def parse_notes(path: str | Path) -> list[NoteRow]:
    """Parse a notes file into ``NoteRow``s (flags empty — call ``validate_notes``)."""
    records = _read_table(path)
    if not records:
        return []
    columns = _resolve_columns(list(records[0].keys()))

    def cell(record: dict[str, str], canonical: str) -> str:
        source = columns.get(canonical)
        return record.get(source, "").strip() if source else ""

    rows: list[NoteRow] = []
    for record in records:
        rows.append(
            NoteRow(
                nr=_parse_nr(cell(record, "nr")),
                start_time=_normalize_time(cell(record, "start")),
                stop_time=_normalize_time(cell(record, "stop")),
                gps=cell(record, "gps"),
                light_dark=_normalize_light_dark(cell(record, "light_dark")),
                location=cell(record, "location"),
            )
        )
    return rows


def validate_notes(rows: list[NoteRow]) -> list[NoteRow]:
    """Set each row's ``flags`` in place (and return the list) for the Confirm step."""
    for row in rows:
        flags: list[str] = []
        if not row.start_time or not row.stop_time:
            flags.append(UNPARSEABLE_TIME)
        elif row.stop_time <= row.start_time:
            # "HH:MM:SS" strings compare chronologically within a day.
            flags.append(STOP_BEFORE_START)
        if not row.gps.strip():
            flags.append(GPS_MISSING)
        if not row.location.strip():
            flags.append(LOCATION_MISSING)
        row.flags = flags
    return rows
