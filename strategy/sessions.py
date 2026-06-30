"""
Session Feature Computation
============================
Produces per-day arrays of Asian and London session statistics from raw M1
bars.  A single O(N) pass builds everything; the output arrays are indexed
by day number and consumed directly by the simulation hot-loop.

Key features per day
--------------------
  asian_high / asian_low / asian_range
      Raw price extremes of the Asian session.

  asian_range_pct
      Rolling percentile of asian_range over the last N trading days.
      Values < 25 → compressed (quiet) Asian session.

  asian_mean_atr
      Mean M1 Wilder ATR during the Asian session.

  london_open_atr
      M1 ATR at the first London-session bar (expansion indicator).
      ratio = london_open_atr / asian_mean_atr > threshold → expanding.

  london_bar_start / london_bar_end
      M1 bar indices of the first and last London-session bar.
      -1 signals "no data for this day" (weekends, holidays).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from smc.loader import BarData


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class SessionFeatures:
    """
    Per-day session arrays.  Every array has length n_days.
    Bar-index arrays use -1 for days with no session data.
    """
    dates:            np.ndarray   # datetime64[ns]  — one entry per calendar day
    asian_high:       np.ndarray   # float64
    asian_low:        np.ndarray   # float64
    asian_range:      np.ndarray   # float64  — high − low
    asian_range_pct:  np.ndarray   # float64  — rolling percentile [0, 100]
    asian_mean_atr:   np.ndarray   # float64  — mean M1 ATR in Asian session
    london_open_atr:  np.ndarray   # float64  — M1 ATR at first London bar
    london_bar_start: np.ndarray   # int64    — M1 index of first London bar
    london_bar_end:   np.ndarray   # int64    — M1 index of last London bar
    n_days:           int


# ── Public API ────────────────────────────────────────────────────────────────

def compute_session_features(
    m1:                 BarData,
    asian_start_hour:   int = 0,    # UTC, inclusive
    asian_end_hour:     int = 7,    # UTC, exclusive  (= London open)
    london_start_hour:  int = 7,    # UTC, inclusive
    london_end_hour:    int = 17,   # UTC, exclusive  (London + NY)
    range_pct_lookback: int = 20,   # trading days for rolling percentile
) -> SessionFeatures:
    """
    Single-pass O(N) computation of per-day session statistics.

    Parameters
    ----------
    m1                 : 1-minute BarData (full date range)
    asian_start_hour   : session start (UTC, inclusive)
    asian_end_hour     : session end / London open (UTC, exclusive)
    london_start_hour  : London open (UTC, inclusive)
    london_end_hour    : London + NY close (UTC, exclusive)
    range_pct_lookback : days for rolling Asian-range percentile
    """
    ts_pd  = pd.DatetimeIndex(m1.ts)
    hours  = ts_pd.hour.to_numpy()          # int array, shape (N,)
    dates_d_vals = ts_pd.normalize().values  # datetime64[ns] array, shape (N,)

    unique_dates = np.unique(dates_d_vals)   # sorted calendar days
    n_days       = len(unique_dates)

    # date → day-index lookup (built once, O(n_days))
    date_idx_map: dict = {d: i for i, d in enumerate(unique_dates)}

    # Accumulators
    asian_high       = np.zeros(n_days)
    asian_low        = np.full(n_days, np.inf)
    asian_atr_sum    = np.zeros(n_days)
    asian_bar_count  = np.zeros(n_days, dtype=np.int64)
    london_open_atr  = np.zeros(n_days)
    london_bar_start = np.full(n_days, -1, dtype=np.int64)
    london_bar_end   = np.full(n_days, -1, dtype=np.int64)

    # Single pass over all M1 bars
    for i in range(len(m1.ts)):
        h  = int(hours[i])
        di = date_idx_map.get(dates_d_vals[i], -1)
        if di < 0:
            continue

        # ── Asian session
        if asian_start_hour <= h < asian_end_hour:
            if m1.high[i] > asian_high[di]:
                asian_high[di] = m1.high[i]
            if m1.low[i] < asian_low[di]:
                asian_low[di] = m1.low[i]
            atr_i = m1.atr[i]
            if not np.isnan(atr_i):
                asian_atr_sum[di]   += atr_i
                asian_bar_count[di] += 1

        # ── London (+ NY) session
        if london_start_hour <= h < london_end_hour:
            if london_bar_start[di] < 0:
                london_bar_start[di] = i
                atr_i = m1.atr[i]
                london_open_atr[di] = atr_i if not np.isnan(atr_i) else 0.0
            london_bar_end[di] = i

    # Fix days with no Asian bars (weekends / public holidays)
    no_data = asian_low == np.inf
    asian_low[no_data] = asian_high[no_data]   # range collapses to 0

    # Asian mean ATR
    with np.errstate(invalid="ignore", divide="ignore"):
        asian_mean_atr = np.where(
            asian_bar_count > 0,
            asian_atr_sum / asian_bar_count,
            np.nan,
        )

    asian_range = asian_high - asian_low

    # Rolling percentile of Asian range (over the previous N trading days)
    asian_range_pct = np.full(n_days, np.nan)
    for i in range(range_pct_lookback, n_days):
        window = asian_range[max(0, i - range_pct_lookback): i]
        valid  = window[window > 0]
        r_i    = asian_range[i]
        if len(valid) > 0 and r_i > 0:
            asian_range_pct[i] = float(np.sum(valid <= r_i)) / len(valid) * 100.0

    return SessionFeatures(
        dates            = unique_dates,
        asian_high       = asian_high,
        asian_low        = asian_low,
        asian_range      = asian_range,
        asian_range_pct  = asian_range_pct,
        asian_mean_atr   = asian_mean_atr,
        london_open_atr  = london_open_atr,
        london_bar_start = london_bar_start,
        london_bar_end   = london_bar_end,
        n_days           = n_days,
    )
