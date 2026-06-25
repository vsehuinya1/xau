"""
Regime Filter
=============
Determines which M1 bars are valid for trade entry based on three
orthogonal filters.  All filters are pre-computed into arrays so that
the simulation hot loop performs only O(1) array lookups.

Filter 1 — Volatility (15m ATR percentile)
-------------------------------------------
Kills Asian session chop (low ATR pct) and NFP spike extremes (high ATR pct).
The ATR percentile is computed on the M15 timeframe using a 200-bar rolling
window, then mapped to each M1 bar via a binary search.

    tradeable  iff  min_atr_pct ≤ ATR_pct_15m ≤ max_atr_pct

Filter 2 — Trend (H1 EMA slope)
---------------------------------
Prevents longs in a downtrend and shorts in an uptrend.
Slope = EMA_H1[j] − EMA_H1[j − slope_lookback]  where j is the current H1 bar.
This is direction-dependent and is therefore checked per-signal in the
simulation loop, not as a blanket boolean here.

    long  allowed  iff  slope ≥ 0
    short allowed  iff  slope ≤ 0

The ``h1_ema_slope`` array is returned for the simulation to consume.

Filter 3 — Session (UTC clock)
--------------------------------
Restricts entries to London and NY open windows by default.

    London:   07:00 – 12:00 UTC
    NY open:  13:00 – 17:00 UTC
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Tradeable sessions: (start_hour, start_min, end_hour, end_min) UTC
_SESSIONS: dict[str, tuple[int, int, int, int]] = {
    "london":  (7,  0, 12,  0),
    "ny_open": (13, 0, 17,  0),
}


# ── Parameter container ───────────────────────────────────────────────────────

@dataclass
class RegimeParams:
    min_atr_pct:    float = 20.0   # lower ATR-pct bound
    max_atr_pct:    float = 85.0   # upper ATR-pct bound
    slope_filter:   bool  = True   # enable H1 EMA-slope gate
    slope_lookback: int   = 4      # H1 bars used for slope delta
    session_filter: bool  = True   # restrict to London + NY


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class RegimeArrays:
    """Per-M1-bar regime arrays consumed by the simulation loop."""
    in_session:   np.ndarray   # bool (N,)    — bar inside a tradeable session
    vol_ok:       np.ndarray   # bool (N,)    — ATR percentile in range
    h1_ema_slope: np.ndarray   # float64 (N,) — H1 EMA slope (sign = bias)
    h4_adx:       np.ndarray   # float64 (N,) — H4 ADX mapped to each M1 bar
    # Composite pre-filter (session AND vol).  Slope/ADX checked per-signal.
    is_tradeable: np.ndarray   # bool (N,)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_mask(ts_m1: np.ndarray, enabled: bool) -> np.ndarray:
    """Boolean mask: True if the M1 bar falls inside a tradeable UTC session."""
    if not enabled:
        return np.ones(len(ts_m1), dtype=bool)
    idx     = pd.DatetimeIndex(ts_m1)
    minutes = idx.hour * 60 + idx.minute
    mask    = np.zeros(len(ts_m1), dtype=bool)
    for (sh, sm, eh, em) in _SESSIONS.values():
        mask |= (minutes >= sh * 60 + sm) & (minutes < eh * 60 + em)
    return mask


def _m15_atr_pct_at_m1(
    ts_m1:      np.ndarray,
    ts_m15:     np.ndarray,
    atr_pct_m15: np.ndarray,
) -> np.ndarray:
    """For each M1 bar, return the ATR percentile of the containing M15 bar."""
    # searchsorted gives the first M15 bar index AFTER ts_m1[i];
    # subtract 1 for the bar that started at or before ts_m1[i].
    idx = np.searchsorted(ts_m15, ts_m1, side="right") - 1
    idx = np.clip(idx, 0, len(atr_pct_m15) - 1)
    result = atr_pct_m15[idx]
    # Mark bars before the first valid M15 ATR-pct as NaN
    result[idx < 0] = np.nan
    return result


def _h1_slope_at_m1(
    ts_m1:    np.ndarray,
    ts_h1:    np.ndarray,
    ema_h1:   np.ndarray,
    lookback: int,
    enabled:  bool,
) -> np.ndarray:
    """
    For each M1 bar, compute the H1 EMA slope:
        slope = ema_h1[j] − ema_h1[j − lookback]
    Fully vectorised using numpy advanced indexing.
    """
    N = len(ts_m1)
    if not enabled:
        return np.zeros(N, dtype=np.float64)

    h1_idx  = np.searchsorted(ts_h1, ts_m1, side="right") - 1
    h1_idx  = np.clip(h1_idx, 0, len(ema_h1) - 1)
    prev_idx = np.clip(h1_idx - lookback, 0, len(ema_h1) - 1)

    slopes = ema_h1[h1_idx] - ema_h1[prev_idx]

    # Mask bars with insufficient history or NaN EMAs
    slopes[h1_idx < lookback] = np.nan
    nan_mask = np.isnan(ema_h1[h1_idx]) | np.isnan(ema_h1[prev_idx])
    slopes[nan_mask] = np.nan

    return slopes


def _wilder_adx(
    high:   np.ndarray,
    low:    np.ndarray,
    close:  np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Wilder's Average Directional Index (ADX) on a bar series.
    Returns array of same length; first (2×period−2) values are NaN.
    A rising ADX > threshold signals a trending regime regardless of direction.
    """
    N = len(high)
    adx = np.full(N, np.nan)
    if N < 2 * period:
        return adx

    # True Range
    prev_close = np.empty(N)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low  - prev_close)))

    # Directional Movement
    plus_dm  = np.zeros(N)
    minus_dm = np.zeros(N)
    for i in range(1, N):
        up   = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        if up > down and up > 0:
            plus_dm[i] = up
        elif down > up and down > 0:
            minus_dm[i] = down

    # Wilder smoothed totals (seed = sum of first period bars)
    s_tr   = np.full(N, np.nan)
    s_pdm  = np.full(N, np.nan)
    s_mdm  = np.full(N, np.nan)
    s_tr[period - 1]  = tr[:period].sum()
    s_pdm[period - 1] = plus_dm[:period].sum()
    s_mdm[period - 1] = minus_dm[:period].sum()
    for i in range(period, N):
        s_tr[i]  = s_tr[i-1]  - s_tr[i-1]  / period + tr[i]
        s_pdm[i] = s_pdm[i-1] - s_pdm[i-1] / period + plus_dm[i]
        s_mdm[i] = s_mdm[i-1] - s_mdm[i-1] / period + minus_dm[i]

    # +DI / −DI / DX
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di  = np.where(s_tr > 0, 100.0 * s_pdm / s_tr, 0.0)
        minus_di = np.where(s_tr > 0, 100.0 * s_mdm / s_tr, 0.0)
        di_sum   = plus_di + minus_di
        dx       = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

    # ADX = Wilder EMA of DX, seeded at bar (2×period−2)
    start = 2 * period - 2
    if N <= start:
        return adx
    adx[start] = dx[period - 1: start + 1].mean()
    for i in range(start + 1, N):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return adx


def _h4_adx_at_m1(
    ts_m1:   np.ndarray,
    ts_h4:   np.ndarray,
    adx_h4:  np.ndarray,
) -> np.ndarray:
    """Forward-fill H4 ADX values onto every M1 bar."""
    idx = np.searchsorted(ts_h4, ts_m1, side="right") - 1
    idx = np.clip(idx, 0, len(adx_h4) - 1)
    return adx_h4[idx]


# ── Public API ────────────────────────────────────────────────────────────────

def compute_regime(
    ts_m1:       np.ndarray,
    ts_m15:      np.ndarray,
    atr_pct_m15: np.ndarray,
    ts_h1:       np.ndarray,
    ema_h1:      np.ndarray,
    ts_h4:       np.ndarray,
    high_h4:     np.ndarray,
    low_h4:      np.ndarray,
    close_h4:    np.ndarray,
    params:      RegimeParams,
) -> RegimeArrays:
    """
    Pre-compute all regime filter arrays for the M1 simulation.

    Parameters
    ----------
    ts_m1        : M1 bar timestamps (datetime64[ns] UTC)
    ts_m15       : M15 bar timestamps
    atr_pct_m15  : 200-bar rolling ATR percentile on M15
    ts_h1        : H1 bar timestamps
    ema_h1       : 50-bar EMA of H1 close
    ts_h4        : H4 bar timestamps
    high_h4      : H4 high prices
    low_h4       : H4 low prices
    close_h4     : H4 close prices
    params       : RegimeParams

    Returns
    -------
    RegimeArrays  — consumed by the simulation hot loop via O(1) index lookups.
    ADX is always computed; the threshold gate is applied in the sim loop
    via StrategyParams.adx_filter / adx_threshold.
    """
    in_session = _session_mask(ts_m1, params.session_filter)

    m15_pct_for_m1 = _m15_atr_pct_at_m1(ts_m1, ts_m15, atr_pct_m15)
    vol_ok = (
        (m15_pct_for_m1 >= params.min_atr_pct) &
        (m15_pct_for_m1 <= params.max_atr_pct)
    )
    vol_ok[np.isnan(m15_pct_for_m1)] = False

    slope = _h1_slope_at_m1(
        ts_m1, ts_h1, ema_h1, params.slope_lookback, params.slope_filter
    )

    # H4 ADX — always computed, threshold applied in simulation loop
    adx_h4 = _wilder_adx(high_h4, low_h4, close_h4, period=14)
    h4_adx  = _h4_adx_at_m1(ts_m1, ts_h4, adx_h4)

    is_tradeable = in_session & vol_ok

    return RegimeArrays(
        in_session   = in_session,
        vol_ok       = vol_ok,
        h1_ema_slope = slope,
        h4_adx       = h4_adx,
        is_tradeable = is_tradeable,
    )
