"""Bars and indicators derived from M1 bars."""
import numpy as np
import pandas as pd


def tf_bars(m1, minutes):
    """Bars of the given length, indexed by bin start. UTC bins are also New
    York bins for 5, 15 and 30 minutes, since the offset is whole hours."""
    return m1.resample(f"{minutes}min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def tf_atr(m1, minutes, n=14):
    """Mean of the last n true ranges on the timeframe, indexed by each bar's close time."""
    bars = tf_bars(m1, minutes)
    prev = bars.close.shift(1).fillna(bars.open)
    tr = np.maximum(bars.high, prev) - np.minimum(bars.low, prev)
    atr = tr.rolling(n).mean()
    atr.index = atr.index + pd.Timedelta(minutes=minutes)
    return atr.dropna()


def m5_bars(m1):
    return tf_bars(m1, 5)


def m5_atr(m1, n=14):
    return tf_atr(m1, 5, n)
