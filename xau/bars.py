"""Load M1 bars saved by mt5/winpy/download_bars.py, indexed by UTC time.

Prices are MT5 chart prices (bid). `spread` is in points ($0.01 for XAUUSD).
Pepperstone's M1 history is real one-minute data only from mid-2017; before
that the series holds hourly (2016) and daily (1998-2015) bars.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from xau import holdout
from xau.servertime import server_to_utc, to_utc

BARS_DIR = Path(__file__).resolve().parent.parent / "data" / "mt5" / "bars"
FIELDS = ("open", "high", "low", "close", "tick_volume", "spread")


def load_m1(start=None, end=None, server="Pepperstone-Demo", symbol="XAUUSD", allow_holdout=False):
    """M1 bars with start <= UTC bar open < end.

    start=None means from the first bar. end=None means up to the holdout, or
    to the last bar with allow_holdout=True. An end inside the holdout raises
    unless allow_holdout=True (see xau/holdout.py).
    """
    if end is None and not allow_holdout:
        end = holdout.HOLDOUT_START
    if end is not None:
        holdout.check(to_utc(end), allow_holdout)
    root = BARS_DIR / server / symbol / "M1"
    parts = []
    for path in sorted(root.glob("*.npz")):
        with np.load(path) as z:
            parts.append({k: z[k] for k in ("time",) + FIELDS})
    if not parts:
        raise FileNotFoundError(f"no bars in {root}")
    cols = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    df = pd.DataFrame({k: cols[k] for k in FIELDS},
                      index=server_to_utc(cols["time"] * 1000).rename("time"))
    if start is not None:
        df = df[df.index >= to_utc(start)]
    if end is not None:
        df = df[df.index < to_utc(end)]
    return df
