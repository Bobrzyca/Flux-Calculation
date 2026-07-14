# Chunk 7 — Time-shift correction + auto-match by timestamp

**Description:** The matching core (brief Features 2 & 3), pure code. Apply the
instrument-clock offset to the LI-7810 timestamps, slice the continuous stream
into per-spot windows from the confirmed notes, and attach the nearest-in-time
temperature and pressure to each spot.

## Exactly what to do
1. **`app/matching/timeshift.py`** — `apply_offset(readings, offset_seconds)`
   that adds the (possibly negative) offset to every LI-7810 timestamp. Empty/0
   offset = no shift. Return a new series; record the applied offset for the log.
2. **`app/matching/match.py`**:
   - `slice_spot(readings, start, stop, work_date, offset)` → the readings whose
     (offset-corrected) timestamp falls in `[start, stop]` for that spot. Convert
     the note's `HH:MM:SS` on `work_date` to unix to compare.
   - `nearest_temperature(temp_series, t)` and `nearest_pressure(press_series,
     t)` → nearest-in-time value (temperature "nearest ≤ ~30 s" per the brief;
     pressure nearest-in-time).
   - `match_spot(...)` → readings annotated with `temperature_used` and
     `pressure_used`, plus flags: empty window → mark spot to skip; stop ≤ start
     (missed by validation) → skip; missing pressure → `no_pressure` flag.
   - Preserve repeated GPS (redo `3!`, paired light/dark sharing a GPS) — never
     merge a light and a dark measurement.
3. Emit structured log messages (return them; persistence happens in the match
   endpoint chunk): e.g. "Applied time-offset +N s to M rows", "Spot 7: 12 of 300
   readings dropped (nan)", "Spot 14 skipped: stop before start".

## Files created / changed
- New: `app/matching/timeshift.py`, `app/matching/match.py`.
- New tests: `tests/test_timeshift.py`, `tests/test_match.py`.

## How to verify
- Time-shift test: offset applied correctly for positive, negative and zero.
- Match test (using the chunk-4/5 fixtures or synthetic series): a spot window
  selects exactly the in-range readings; nearest temp/pressure chosen correctly;
  empty window flags a skip; stop-before-start flags a skip; a spot missing
  pressure gets `no_pressure`; two spots sharing a GPS stay distinct.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunks 1 and 4 (LI-7810/temperature parser output shapes); consumes chunk-5
notes/pressure shapes.

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`).

Commit and push.
