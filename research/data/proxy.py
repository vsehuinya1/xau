"""
research/data/proxy.py — DataProxy: enriched wrapper over DataStore.

Pre-computes shared derived arrays once at construction.
All diagnostics read from DataProxy; none touch DataStore directly.

Pre-computed arrays (all aligned to M1 bars unless noted)
----------------------------------------------------------
  session        int8  — 0=Asian 1=London 2=NY 3=Off
  weekday        int8  — 0=Mon 4=Fri
  hour_utc       int8  — UTC hour of bar open
  day_idx        int64 — index into daily_df for each M1 bar
  daily_df       DataFrame — one row per calendar day (see daily.py)
  nd_high / nd_low — {N: bool array} for N in {5, 10, 20, 60}
  data_fp        str   — fingerprint for cache keys
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from smc.loader import DataStore
from research.utils import label_sessions, forward_returns
from research.data.daily import build_daily_df


_ND_LOOKBACKS = (5, 10, 20, 60)   # N-day high/low lookbacks in trading days


@dataclass
class DataProxy:
    # Source
    ds: DataStore

    # Per-M1-bar context arrays
    session:   np.ndarray   # int8
    weekday:   np.ndarray   # int8
    hour_utc:  np.ndarray   # int8
    day_idx:   np.ndarray   # int64 — row index into daily_df

    # Per-day data
    daily_df:  pd.DataFrame

    # N-day high/low flags (per M1 bar) — values are bool arrays
    nd_high:   dict[int, np.ndarray]
    nd_low:    dict[int, np.ndarray]

    # Forward returns (per M1 bar): +15, +60, +240, +390 bars
    fwd_ret:   dict[int, np.ndarray]

    # Cache key
    data_fp:   str


def build_data_proxy(ds: DataStore) -> DataProxy:
    """
    Construct a fully-populated DataProxy from a DataStore.
    Typically takes 5–15s for 8yr / 2.79M bars.
    """
    m1 = ds.m1
    ts = pd.DatetimeIndex(m1.ts)
    if ts.tz is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    N  = len(m1.ts)

    print("  DataProxy: labelling sessions …", flush=True)
    session = label_sessions(m1.ts)

    hours   = ts.hour.to_numpy(dtype=np.int8)
    weekday = ts.dayofweek.to_numpy(dtype=np.int8)   # 0=Mon

    print("  DataProxy: building daily frame …", flush=True)
    daily_df = build_daily_df(m1, session)

    # Map each M1 bar to its day index
    dates_d  = ts.normalize().values                  # datetime64[ns] per bar
    u_dates  = daily_df["date"].values                # unique sorted dates
    day_idx  = np.searchsorted(u_dates, dates_d, side="left").astype(np.int64)
    day_idx  = np.clip(day_idx, 0, len(u_dates) - 1)

    print("  DataProxy: computing N-day highs/lows …", flush=True)
    nd_high: dict[int, np.ndarray] = {}
    nd_low:  dict[int, np.ndarray] = {}
    daily_close = daily_df["close"].values.astype(np.float64)
    n_days      = len(daily_close)
    for n in _ND_LOOKBACKS:
        # Vectorised rolling max/min over the PRIOR n days (exclude today)
        flag_h = np.zeros(n_days, dtype=bool)
        flag_l = np.zeros(n_days, dtype=bool)
        if n_days > n:
            # Build (n_days, n) view via stride_tricks then reduce
            roll_max = pd.Series(daily_close).shift(1).rolling(n, min_periods=1).max().values
            roll_min = pd.Series(daily_close).shift(1).rolling(n, min_periods=1).min().values
            flag_h = daily_close > roll_max
            flag_l = daily_close < roll_min
            flag_h[:n] = False
            flag_l[:n] = False
        nd_high[n] = flag_h[day_idx]
        nd_low[n]  = flag_l[day_idx]

    print("  DataProxy: computing forward returns …", flush=True)
    fwd_ret = forward_returns(m1.close, horizons=[15, 60, 240, 390])

    data_fp = f"{N}:{m1.ts[0]}:{m1.ts[-1]}"

    print("  DataProxy: ready.", flush=True)
    return DataProxy(
        ds       = ds,
        session  = session,
        weekday  = weekday,
        hour_utc = hours,
        day_idx  = day_idx,
        daily_df = daily_df,
        nd_high  = nd_high,
        nd_low   = nd_low,
        fwd_ret  = fwd_ret,
        data_fp  = data_fp,
    )
