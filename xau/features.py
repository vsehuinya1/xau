"""Bars and indicators derived from M1 bars."""
import numpy as np
import pandas as pd


def m5_bars(m1):
    """M5 bars indexed by bin start. UTC 5-minute bins are also New York
    5-minute bins, since the offset is a whole number of hours."""
    return m1.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def m5_atr(m1, n=14):
    """Mean of the last n M5 true ranges, indexed by each M5 bar's close time."""
    m5 = m5_bars(m1)
    prev = m5.close.shift(1).fillna(m5.open)
    tr = np.maximum(m5.high, prev) - np.minimum(m5.low, prev)
    atr = tr.rolling(n).mean()
    atr.index = atr.index + pd.Timedelta(minutes=5)
    return atr.dropna()
