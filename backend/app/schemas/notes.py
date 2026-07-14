"""Parsed-notes schemas for the Confirm screen (match the frontend types).

``flags`` values are the frontend ``NoteFlag`` union: ``stop_before_start``,
``gps_missing``, ``unparseable_time``, ``location_missing``. On input (PUT) the
server ignores any supplied ``flags`` and recomputes them.
"""

from pydantic import BaseModel, Field


class NoteRow(BaseModel):
    nr: int
    start_time: str  # "HH:MM:SS"
    stop_time: str  # "HH:MM:SS"
    gps: str = ""
    light_dark: str = ""  # "light" | "dark" | ""
    location: str = ""
    flags: list[str] = Field(default_factory=list)


class ParsedNotes(BaseModel):
    parse_failed: bool
    rows: list[NoteRow]
