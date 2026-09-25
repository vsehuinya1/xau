"""Volume profiles per trading day, from M1 bars' tick volume.

Each bar's tick volume is split equally among the price rows its low-high
range touches; rows are equal-width and span the day's low to high. POC is the
middle of the busiest row (lowest on ties). The value area grows from the POC
row by adding whichever neighbouring row holds more volume (above on ties)
until it holds VALUE_AREA of the day's volume.
"""
import numpy as np
import pandas as pd

from xau.sessions import trading_day

ROWS = 100
VALUE_AREA = 0.70


def value_area(volume, edges, share=VALUE_AREA):
    """(POC, VAH, VAL, volume share inside) from row volumes and row edges."""
    poc = int(np.argmax(volume))
    lo = hi = poc
    inside, total, n = volume[poc], volume.sum(), len(volume)
    while inside < share * total and (hi + 1 < n or lo > 0):
        up = volume[hi + 1] if hi + 1 < n else -np.inf
        down = volume[lo - 1] if lo > 0 else -np.inf
        if up >= down:
            hi, inside = hi + 1, inside + up
        else:
            lo, inside = lo - 1, inside + down
    return (edges[poc] + edges[poc + 1]) / 2, edges[hi + 1], edges[lo], inside / total


def profile(low, high, volume, rows=ROWS):
    """Row volumes and row edges for one day's bars."""
    lo, hi = low.min(), high.max()
    edges = np.linspace(lo, hi, rows + 1)
    width = (hi - lo) / rows
    first = np.clip(((low - lo) / width).astype(int), 0, rows - 1)
    last = np.clip(((high - lo) / width).astype(int), 0, rows - 1)
    share = volume / (last - first + 1)
    diff = np.zeros(rows + 1)
    np.add.at(diff, first, share)
    np.add.at(diff, last + 1, -share)
    return np.maximum(np.cumsum(diff)[:rows], 0), edges  # clip floating-point noise below zero


def daily_profiles(m1, rows=ROWS):
    """POC, VAH, VAL (and value-area share) of each trading day's profile,
    labelled with the next trading day in the data, the day they apply to."""
    out = {}
    for day, g in m1.groupby(trading_day(m1.index)):
        low, high = g.low.to_numpy(float), g.high.to_numpy(float)
        if high.max() <= low.min() or g.tick_volume.sum() <= 0:
            continue
        vol, edges = profile(low, high, g.tick_volume.to_numpy(float), rows)
        out[day] = value_area(vol, edges)
    days = pd.DataFrame.from_dict(out, orient="index", columns=["poc", "vah", "val", "va_share"]).sort_index()
    return days.shift(1).dropna()
