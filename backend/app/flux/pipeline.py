"""Per-spot fit orchestration: window selection, nan handling, fit + flux (pure).

Given a spot's readings and conditions:

1. **Despike** — drop isolated single-point sensor spikes (a lone value far off
   its two agreeing neighbours), counted separately from ``nan`` gaps.
2. **Choose the window** — slide a ``FIT_WINDOW_SECONDS`` window to the most-linear
   position (max CO₂ R², tie-broken toward the +30 s skip so clean spots are
   unchanged). If that best 5-min fit is still below ``LOW_R2_THRESHOLD``, try
   *shortening* the window down to ``FIT_SHORTEN_MIN_SECONDS`` (4 min) and adopt a
   shorter length only if it raises R² by ``FIT_SHORTEN_MIN_GAIN`` — a low-R² fix
   that never touches a clean spot.
3. **Fit + flux** — apply that one window to both gases, fit each, compute the flux
   ladder, and raise ``low_r2`` / ``short_window`` flags.

The chosen offset, window length, whether it was shortened, and the spike count are
all reported so every transformation stays visible.

``mode="full"`` skips the window search entirely and fits the **whole recorded
window** as-is (offset 0, full span) — the "use the file's time series without
fitting" option. Despiking still applies (a lone sensor spike is always bad data).
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.flux import constants as C
from app.flux.flux import FluxLadder, compute_flux
from app.flux.regression import FitResult, fit_slope

# Per-spot flag values (mirrors the frontend SpotFlag union subset set here).
LOW_R2 = "low_r2"
SHORT_WINDOW = "short_window"

# Gas -> concentration column in the readings frame.
GAS_COLUMN = {"CO2": "co2_ppm", "CH4": "ch4_ppb"}


@dataclass
class GasResult:
    """Fit + flux outcome for one gas of one spot."""

    gas: str
    fit: FitResult | None
    ladder: FluxLadder | None
    n_points: int
    n_dropped_nan: int
    flags: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    # Chosen fit window, seconds relative to the spot's first reading (t0). Both
    # gases share one window per spot (chosen by CO₂), so the closure period is
    # consistent; ``fit_offset_s`` is how far it sits after the recorded start and
    # ``fit_window_s`` is its length (``FIT_WINDOW_SECONDS`` unless shortened).
    fit_offset_s: float = float(C.FIT_SKIP_SECONDS)
    fit_start_s: float = float(C.FIT_SKIP_SECONDS)
    fit_stop_s: float = float(C.FIT_SKIP_SECONDS + C.FIT_WINDOW_SECONDS)
    fit_window_s: float = float(C.FIT_WINDOW_SECONDS)
    window_shortened: bool = False
    # The actual fit-window bounds in **seconds from the first reading** (t0),
    # i.e. the same frame as a plotted point's ``timestamp - t0``. Unlike
    # ``fit_start_s``/``fit_stop_s`` (reported relative to the recorded start and
    # possibly negative), these are what ``in_window`` shading and the fit-line
    # endpoints must use, so a lead margin doesn't shift them.
    window_lo_s: float = float(C.FIT_SKIP_SECONDS)
    window_hi_s: float = float(C.FIT_SKIP_SECONDS + C.FIT_WINDOW_SECONDS)
    # Isolated single-point spikes dropped from this gas within the fit window.
    n_spikes: int = 0
    # Temperature over the fit window: mean is used in the flux formula; min/max
    # give the range (the logger samples ~every 30 s, so several values fall in
    # the window).
    temp_mean_c: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None


def _despike_mask(values: np.ndarray) -> np.ndarray:
    """Boolean mask of **isolated single-point spikes** in ``values``.

    A spike is a finite sample that deviates from both of its immediate finite
    neighbours *in the same direction* (a lone peak or trough) by more than
    ``DESPIKE_K`` × the robust step scale (median absolute step of the series),
    while those neighbours stay consistent with each other. Runs of consecutive
    off values are never flagged (they are real signal or a genuine gap), so only
    the occasional lone bad reading among hundreds is removed.
    """
    mask = np.zeros(values.size, dtype=bool)
    idx = np.flatnonzero(np.isfinite(values))
    if idx.size < 3:
        return mask
    v = values[idx]
    steps = np.abs(np.diff(v))
    scale = float(np.median(steps))
    if scale <= 0.0:  # near-constant series -> fall back to the mean step
        scale = float(np.mean(steps))
    if scale <= 0.0:
        return mask
    threshold = C.DESPIKE_K * scale
    for j in range(1, v.size - 1):
        left = v[j] - v[j - 1]
        right = v[j] - v[j + 1]
        if left == 0.0 or right == 0.0 or (left > 0) != (right > 0):
            continue  # not a lone peak/trough (or sits on a plateau/slope)
        smaller = min(abs(left), abs(right))
        neighbours_consistent = abs(v[j - 1] - v[j + 1]) <= 0.5 * smaller
        if smaller > threshold and neighbours_consistent:
            mask[idx[j]] = True
    return mask


def _r2_over(
    readings: pd.DataFrame, rel: pd.Series, t0: float, column: str, lo: float, hi: float
) -> float | None:
    """R² of a linear fit of ``column`` over the window ``[lo, hi)`` (rel seconds)."""
    mask = (rel >= lo) & (rel < hi)
    values = readings.loc[mask, column]
    valid = values.notna()
    if int(valid.sum()) < C.MIN_FIT_POINTS:
        return None
    y = values[valid].astype(float).to_numpy()
    x = (readings["timestamp"][mask][valid].astype(float) - t0).to_numpy()
    r2 = fit_slope(x, y).r2
    return r2 if r2 == r2 else None  # drop NaN (flat/zero-variance window)


def _search_bounds(anchor_rel: float, span: float, win: float) -> tuple[int, int, int]:
    """``(lo_off, hi_off, skip_target)`` for a ``win``-long window (rel to t0).

    The search is centred on the recorded start (``anchor_rel`` seconds after the
    first reading): it may look ``FIT_SEARCH_BACK_SECONDS`` earlier and
    ``FIT_SEARCH_MAX_OFFSET_SECONDS`` later, clamped to the data. ``skip_target``
    is the tie-break/default position — ``FIT_SKIP_SECONDS`` after the recorded
    start — so a clean measurement is unchanged and only a lagged one shifts.
    """
    a = int(round(anchor_rel))
    lo_off = max(0, a - C.FIT_SEARCH_BACK_SECONDS)
    hi_off = min(int(span - win), a + C.FIT_SEARCH_MAX_OFFSET_SECONDS)
    return lo_off, hi_off, a + C.FIT_SKIP_SECONDS


def _best_offset(
    readings: pd.DataFrame,
    rel: pd.Series,
    t0: float,
    win: float,
    lo_off: int,
    hi_off: int,
    skip_target: int,
) -> tuple[float, float | None]:
    """Best start offset for a ``win``-long window and the R² there.

    Slides the window over ``[lo_off, hi_off]`` and picks the most-linear start —
    judged by CO₂ (the primary signal), else CH₄. Among windows within 0.02 R² of
    the best, chooses the one closest to ``skip_target`` (``FIT_SKIP_SECONDS``
    after the recorded start) so clean measurements are unchanged and only lagged
    ones shift. Returns ``(offset, r2_at_offset)``; R² is ``None`` when neither gas
    could be fit.
    """
    for column in ("co2_ppm", "ch4_ppb"):
        scored = [
            (off, r2)
            for off in range(lo_off, hi_off + 1, 10)
            if (r2 := _r2_over(readings, rel, t0, column, off, off + win)) is not None
        ]
        if scored:
            best = max(r2 for _, r2 in scored)
            near = [off for off, r2 in scored if r2 >= best - 0.02]
            offset = float(min(near, key=lambda o: abs(o - skip_target)))
            return offset, _r2_over(readings, rel, t0, column, offset, offset + win)
    return float(skip_target), None


def _choose_window(
    readings: pd.DataFrame, rel: pd.Series, t0: float, span: float, anchor_rel: float
) -> tuple[float, float, bool]:
    """Pick ``(offset, length, shortened)`` for the fit window (offset rel to t0).

    Starts from the best full-length (``FIT_WINDOW_SECONDS``) window, searched
    around the recorded start (see ``_search_bounds``). If that fit is already
    trustworthy (R² ≥ ``LOW_R2_THRESHOLD``) it is kept untouched. Only a low-R²
    spot is a candidate for shortening: shorter windows (down to
    ``FIT_SHORTEN_MIN_SECONDS``) are tried and the best is adopted if it lifts R²
    by at least ``FIT_SHORTEN_MIN_GAIN``.
    """
    win = float(C.FIT_WINDOW_SECONDS)
    lo_off, hi_off, skip_target = _search_bounds(anchor_rel, span, win)
    if hi_off < lo_off:  # less than a full window of data — keep prior behaviour
        return float(skip_target), win, False

    offset, r2 = _best_offset(readings, rel, t0, win, lo_off, hi_off, skip_target)
    if r2 is None or r2 >= C.LOW_R2_THRESHOLD:
        return offset, win, False  # clean enough — never shorten

    best_off, best_len, best_r2 = offset, win, r2
    length = win - C.FIT_SHORTEN_STEP_SECONDS
    while length >= C.FIT_SHORTEN_MIN_SECONDS:
        lo_l, hi_l, skip_l = _search_bounds(anchor_rel, span, length)
        if hi_l < lo_l:
            break
        off_l, r2_l = _best_offset(readings, rel, t0, length, lo_l, hi_l, skip_l)
        if r2_l is not None and r2_l > best_r2:
            best_off, best_len, best_r2 = off_l, length, r2_l
        length -= C.FIT_SHORTEN_STEP_SECONDS

    if best_len < win and best_r2 >= r2 + C.FIT_SHORTEN_MIN_GAIN:
        return best_off, best_len, True
    return offset, win, False


def fit_spot(
    readings: pd.DataFrame,
    area_m2: float,
    volume_l: float,
    temp_c: float,
    pressure_hpa: float,
    mode: str = "auto",
    manual_offset_s: float | None = None,
    anchor_ts: float | None = None,
) -> dict[str, GasResult]:
    """Fit both gases for a spot.

    ``mode="auto"`` (default) despikes, then fits over the best (most-linear,
    possibly shortened) window. ``mode="full"`` despikes, then fits the **whole
    recorded window** as-is (no window search) — the "use the file's series without
    fitting" option. When ``manual_offset_s`` is given it **overrides** both: the
    fit uses a fixed ``FIT_WINDOW_SECONDS`` window starting that many seconds
    **relative to the recorded start** — positive = later, **negative = earlier**
    (the manual per-spot correction). ``readings`` needs ``timestamp``, ``co2_ppm``
    and ``ch4_ppb``.

    ``anchor_ts`` is the recorded-start unix timestamp; all offsets (auto search,
    reported ``fit_offset_s``, and the manual shift) are measured from it, so a
    lead margin of data before the recorded start lets the window move earlier.
    When ``None`` the anchor is the first reading (offsets measured from t0) —
    the behaviour before the lead margin existed.
    """
    if readings.empty:
        return {
            gas: GasResult(
                gas, None, None, 0, 0, skipped=True, skip_reason="no readings"
            )
            for gas in GAS_COLUMN
        }

    # 1) Despike each gas up front so a lone sensor spike distorts neither the
    #    window search nor the fit. Spikes become nan in a working copy; the
    #    original nan positions are remembered so the two are counted separately.
    work = readings.copy()
    original_nan: dict[str, np.ndarray] = {}
    spike_mask: dict[str, np.ndarray] = {}
    for column in GAS_COLUMN.values():
        raw = readings[column].to_numpy(dtype=float)
        original_nan[column] = np.isnan(raw)
        spikes = _despike_mask(raw)
        spike_mask[column] = spikes
        if spikes.any():
            cleaned = raw.copy()
            cleaned[spikes] = np.nan
            work[column] = cleaned

    t0 = float(work["timestamp"].min())
    rel = work["timestamp"].astype(float) - t0
    span = float(rel.max())
    # Where the recorded start sits within the readings (0 when no anchor / no
    # lead data). Offsets are reported relative to this, so the window can move
    # earlier (negative) into the lead margin.
    anchor_rel = 0.0
    if anchor_ts is not None:
        anchor_rel = min(max(0.0, float(anchor_ts) - t0), span)

    # 2) Choose the window (lo/hi are rel to t0 for masking; offset/start/stop are
    #    reported rel to the recorded start). A manual offset wins over auto/full;
    #    otherwise the page mode decides (whole recording vs best/shortened window).
    if manual_offset_s is not None:
        win = float(C.FIT_WINDOW_SECONDS)
        lo = anchor_rel + float(manual_offset_s)
        hi = lo + win
        shortened = False
        offset = float(manual_offset_s)
        start_report, stop_report = offset, offset + win
    elif mode == "full":
        win, shortened = span, False
        lo, hi = 0.0, span + 1.0  # include the last sample
        offset = 0.0
        start_report, stop_report = -anchor_rel, span - anchor_rel
    else:
        start_rel, win, shortened = _choose_window(work, rel, t0, span, anchor_rel)
        lo, hi = start_rel, start_rel + win
        offset = start_rel - anchor_rel
        start_report, stop_report = offset, offset + win

    window_mask = ((rel >= lo) & (rel < hi)).to_numpy()
    window = work[window_mask]

    # Temperature over the window: use the mean in the flux formula and report
    # the range. Fall back to the scalar ``temp_c`` if no per-reading column.
    temp_mean, temp_min, temp_max = temp_c, temp_c, temp_c
    if "temperature_used" in window.columns:
        wt = window["temperature_used"].dropna()
        if not wt.empty:
            temp_mean = float(wt.mean())
            temp_min, temp_max = float(wt.min()), float(wt.max())

    timestamps = work["timestamp"].astype(float).to_numpy()
    results: dict[str, GasResult] = {}
    for gas, column in GAS_COLUMN.items():
        cleaned = work[column].to_numpy(dtype=float)
        in_window = window_mask
        n_dropped = int(original_nan[column][in_window].sum())
        n_spikes = int((spike_mask[column] & in_window).sum())
        valid = in_window & ~np.isnan(cleaned)
        y = cleaned[valid]
        x = timestamps[valid] - t0
        n_points = int(y.size)
        # "Short" means less than FIT_MIN_WINDOW_SECONDS of *usable* data.
        short = n_points < C.FIT_MIN_WINDOW_SECONDS

        flags: list[str] = [SHORT_WINDOW] if short else []
        common: dict[str, Any] = dict(
            fit_offset_s=offset,
            fit_start_s=start_report,
            fit_stop_s=stop_report,
            fit_window_s=win,
            window_lo_s=lo,
            window_hi_s=hi,
            window_shortened=shortened,
            n_spikes=n_spikes,
            temp_mean_c=temp_mean,
            temp_min_c=temp_min,
            temp_max_c=temp_max,
        )
        if n_points < C.MIN_FIT_POINTS:
            results[gas] = GasResult(
                gas,
                None,
                None,
                n_points,
                n_dropped,
                flags=flags,
                skipped=True,
                skip_reason="too few points",
                **common,
            )
            continue

        fit = fit_slope(x, y)
        ladder = compute_flux(
            fit.slope, area_m2, volume_l, temp_mean, pressure_hpa, gas
        )
        if fit.r2 < C.LOW_R2_THRESHOLD:
            flags.append(LOW_R2)
        results[gas] = GasResult(
            gas,
            fit,
            ladder,
            n_points,
            n_dropped,
            flags=flags,
            **common,
        )

    return results
