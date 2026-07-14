"""Pressure parser: sorted unix timestamps + hPa values, with unit handling."""

from pathlib import Path

from app.parsing.pressure import parse_pressure

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "pressure_sample.csv"


def test_parse_pressure_sample() -> None:
    readings = parse_pressure(SAMPLE)
    assert len(readings) == 6
    # Sorted by time.
    timestamps = [r.timestamp for r in readings]
    assert timestamps == sorted(timestamps)
    # hPa values in a sane atmospheric range; datetime strings -> unix seconds.
    assert all(950 < r.pressure_hpa < 1050 for r in readings)
    assert 1_780_000_000 < timestamps[0] < 1_790_000_000


def test_unix_timestamps_and_kpa_conversion(tmp_path: Path) -> None:
    csv = tmp_path / "press.csv"
    csv.write_text(
        "time,pressure\n1782985020,101.3\n1782985080,101.4\n",
        encoding="utf-8",
    )
    readings = parse_pressure(csv, assume_unit="kPa")
    assert readings[0].timestamp == 1782985020.0
    # 101.3 kPa -> 1013 hPa.
    assert abs(readings[0].pressure_hpa - 1013.0) < 1e-6
