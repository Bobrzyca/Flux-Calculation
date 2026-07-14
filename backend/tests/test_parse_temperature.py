"""Temperature parser: columns, monotonic timestamps, numeric values."""

from pathlib import Path

from app.parsing.temperature import parse_temperature

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE = SAMPLE_DIR / "temperature_sample.xlsx"


def test_parse_temperature_shape_and_order() -> None:
    df = parse_temperature(SAMPLE)
    assert list(df.columns) == ["timestamp", "temperature_c"]
    assert len(df) > 1
    # Sorted by time and every temperature is a real number.
    assert df["timestamp"].is_monotonic_increasing
    assert df["temperature_c"].notna().all()


def test_timestamps_are_unix_seconds() -> None:
    df = parse_temperature(SAMPLE)
    # 2026-07-02 morning -> ~1.78e9 unix seconds; spacing ~30 s.
    assert 1_780_000_000 < df["timestamp"].iloc[0] < 1_790_000_000
    diffs = df["timestamp"].diff().dropna()
    assert (diffs == 30.0).all()
