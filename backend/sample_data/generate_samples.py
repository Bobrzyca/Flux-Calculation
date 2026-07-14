"""Generate the small, realistic sample fixtures used by tests and the demo.

Deterministic (seeded) so the committed files are reproducible. Run from the
backend directory with the venv active:

    python sample_data/generate_samples.py

Produces (in this directory):
  - li7810_sample.txt        LI-7810 tab-delimited concentration log
  - temperature_sample.xlsx  temperature series (~30 s spacing)
  - notes_sample.csv         time-window notes (some messy-but-well-formed times)
  - pressure_sample.csv      IMGW-style pressure series (hPa)

The timeline is a fictional 2026-07-02 Kampinos morning campaign. The notes'
spot windows line up with the LI-7810 stream: spot 1 sits in the clean window,
spot 2 in the flat/low-R² window, spot 3's window falls outside the stream (an
empty-window skip), and spot 4 has stop-before-start (a skip + validation flag).
"""

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

# Campaign timeline: a continuous 1 Hz stream covering two spot windows.
BASE = datetime(2026, 7, 2, 9, 37, 0, tzinfo=UTC)
BASE_UNIX = int(BASE.timestamp())
DURATION_S = 20 * 60  # 20 minutes -> 1200 samples
WARMUP_S = 30  # laser stabilising: all-nan rows at the very start

# Spot windows as (start_offset_s, stop_offset_s) relative to BASE.
# Spot 1: clean linear rise (high R²). Spot 2: essentially flat + noise (low R²).
SPOT1 = (60, 60 + 6 * 60)  # 09:38:00 -> 09:44:00
SPOT2 = (13 * 60, 13 * 60 + 6 * 60)  # 09:50:00 -> 09:56:00

# nan rows dropped out mid-measurement (inside spot 1), to exercise nan handling.
MIDSTREAM_NAN_OFFSETS = {60 + 100, 60 + 101, 60 + 102}


def _concentrations(rng: np.random.Generator) -> tuple[list[float], list[float]]:
    """Per-second CO2 (ppm) and CH4 (ppb) for the whole stream."""
    co2: list[float] = []
    ch4: list[float] = []
    for s in range(DURATION_S + 1):
        if s < WARMUP_S or s in MIDSTREAM_NAN_OFFSETS:
            co2.append(float("nan"))
            ch4.append(float("nan"))
            continue
        if SPOT1[0] <= s <= SPOT1[1]:
            # Clean closed-chamber rise: strong linear trend, tiny noise.
            t = s - SPOT1[0]
            co2.append(410.0 + 0.030 * t + rng.normal(0, 0.05))
            ch4.append(1950.0 + 0.080 * t + rng.normal(0, 0.30))
        elif SPOT2[0] <= s <= SPOT2[1]:
            # Flat + noise: no real trend -> low R² (exercises the low_r2 flag).
            co2.append(415.0 + rng.normal(0, 0.8))
            ch4.append(1960.0 + rng.normal(0, 4.0))
        else:
            # Ambient baseline between windows.
            co2.append(410.0 + rng.normal(0, 0.1))
            ch4.append(1950.0 + rng.normal(0, 0.5))
    return co2, ch4


def write_li7810() -> None:
    rng = np.random.default_rng(42)
    co2, ch4 = _concentrations(rng)
    lines = [
        # Header row 1: instrument metadata (skipped by the parser).
        "Model: LI-7810\tSN: TG10-01234\tTimeZone: UTC",
        # Header row 2: column names.
        "SECONDS\tDIAG\tCO2\tCH4\tH2O\tTEMP",
    ]
    for s in range(DURATION_S + 1):
        sec = BASE_UNIX + s
        c = co2[s]
        m = ch4[s]
        h2o = "nan" if np.isnan(c) else f"{15000.0 + rng.normal(0, 5):.2f}"
        co2_s = "nan" if np.isnan(c) else f"{c:.3f}"
        ch4_s = "nan" if np.isnan(m) else f"{m:.3f}"
        lines.append(f"{sec}\t0\t{co2_s}\t{ch4_s}\t{h2o}\t18.20")
    (HERE / "li7810_sample.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_temperature() -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Temperature"
    ws.append(["Date", "Temp"])
    # A reading every 30 s across the campaign, slowly warming.
    n = DURATION_S // 30 + 2
    for i in range(n):
        when = BASE + timedelta(seconds=30 * i)
        # Naive wall-clock datetime matching the UTC stream, so both map to the
        # same unix seconds after parsing.
        temp = 18.0 + 0.01 * i
        ws.append([when.replace(tzinfo=None), round(temp, 3)])
    wb.save(HERE / "temperature_sample.xlsx")


def write_notes() -> None:
    # Columns: Nr, Start, Stop, GPS, light/dark, location. Times deliberately
    # mix clean formats the deterministic parser handles: dot (9.38), colon
    # without seconds (9:50), and full HH:MM:SS.
    rows = [
        ["Nr", "Start", "Stop", "GPS", "light/dark", "location"],
        ["1", "9.38", "9.44", "52.30,20.55", "light", "dam edge"],
        ["2", "9:50", "9:56", "", "dark", "reed bed"],  # blank GPS
        ["3", "10:10:00", "10:16:00", "52.31,20.56", "light", "far plot"],  # no data
        ["4", "09:30:00", "09:25:00", "52.29,20.54", "dark", "ditch"],  # stop<start
    ]
    with open(HERE / "notes_sample.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def write_pressure() -> None:
    # IMGW-style: a timestamp column and a pressure column in hPa, every 30 min.
    rows = [["timestamp", "pressure_hpa"]]
    start = datetime(2026, 7, 2, 8, 30, 0)
    for i in range(6):  # 08:30 .. 11:00
        when = start + timedelta(minutes=30 * i)
        pressure = 1013.0 + 0.1 * i
        rows.append([when.strftime("%Y-%m-%d %H:%M:%S"), f"{pressure:.1f}"])
    with open(HERE / "pressure_sample.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


if __name__ == "__main__":
    write_li7810()
    write_temperature()
    write_notes()
    write_pressure()
    print(f"Wrote fixtures to {HERE}")
