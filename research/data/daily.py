"""
research/data/daily.py — Per-day OHLC and derived features.

Builds a DataFrame indexed by calendar day from M1 bar data.
One row per trading day with columns:
  date, open, high, low, close, true_range, weekday,
  pdr (previous day range), pdr_pct (rolling 20d percentile of pdr),
  asian_high, asian_low, asian_range, asian_close_pos,
  london_open (first London bar close)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


_ROLLING_PCT_WINDOW = 20   # trading days for PDR percentile


def build_daily_df(m1, session: np.ndarray) -> pd.DataFrame:
    """
    Parameters
    ----------
    m1      : BarData (ts, open, high, low, close, atr)
    session : int8 array per M1 bar (0=Asian 1=London 2=NY 3=Off)

    Returns
    -------
    pd.DataFrame — one row per calendar day, sorted ascending.
    """
    ts_pd  = pd.DatetimeIndex(m1.ts)
    if ts_pd.tz is not None:
        ts_pd = ts_pd.tz_convert("UTC").tz_localize(None)
    dates  = ts_pd.normalize()     # midnight datetime64[ns] per bar (tz-naive)

    # ── Vectorised daily OHLC using groupby
    df_m1 = pd.DataFrame({
        "date":    dates,
        "open":    m1.open,
        "high":    m1.high,
        "low":     m1.low,
        "close":   m1.close,
        "session": session,
    })

    # Full-day OHLC
    grp_daily = df_m1.groupby("date")
    daily = pd.DataFrame({
        "date":  grp_daily["date"].first(),
        "open":  grp_daily["open"].first(),
        "high":  grp_daily["high"].max(),
        "low":   grp_daily["low"].min(),
        "close": grp_daily["close"].last(),
    }).reset_index(drop=True)

    daily["weekday"] = pd.DatetimeIndex(daily["date"]).dayofweek.astype(np.int8)

    # True range (using prev day close for gap)
    prev_close = daily["close"].shift(1)
    daily["true_range"] = np.maximum(
        daily["high"] - daily["low"],
        np.maximum(
            (daily["high"] - prev_close).abs(),
            (daily["low"]  - prev_close).abs(),
        ),
    )

    # PDR = previous day's true range
    daily["pdr"] = daily["true_range"].shift(1)

    # PDR percentile (rolling 20-day)
    daily["pdr_pct"] = (
        daily["pdr"]
        .rolling(window=_ROLLING_PCT_WINDOW, min_periods=5)
        .apply(lambda x: float(np.sum(x[:-1] <= x[-1])) / max(len(x) - 1, 1) * 100.0,
               raw=True)
    ).astype(np.float32)

    # ── Asian session stats per day
    asian_mask = df_m1["session"] == 0
    grp_asian  = df_m1[asian_mask].groupby("date")
    asian = pd.DataFrame({
        "date":         grp_asian["date"].first(),
        "asian_high":   grp_asian["high"].max(),
        "asian_low":    grp_asian["low"].min(),
        "asian_close":  grp_asian["close"].last(),
    }).reset_index(drop=True)
    asian["asian_range"] = asian["asian_high"] - asian["asian_low"]
    rng = asian["asian_range"].replace(0, np.nan)
    asian["asian_close_pos"] = (
        (asian["asian_close"] - asian["asian_low"]) / rng
    ).clip(0, 1).astype(np.float32)

    # Rolling percentile of Asian range
    asian["asian_range_pct"] = (
        asian["asian_range"]
        .rolling(window=_ROLLING_PCT_WINDOW, min_periods=5)
        .apply(lambda x: float(np.sum(x[:-1] <= x[-1])) / max(len(x) - 1, 1) * 100.0,
               raw=True)
    ).astype(np.float32)

    # ── Merge
    daily = daily.merge(asian, on="date", how="left")
    daily["date"] = pd.to_datetime(daily["date"])

    return daily.reset_index(drop=True)
