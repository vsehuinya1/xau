"""Load ticks archived by mt5/winpy/recorder.py, indexed by UTC time."""
from pathlib import Path

import numpy as np
import pandas as pd

from xau.servertime import server_to_utc, to_utc

TICKS_DIR = Path(__file__).resolve().parent.parent / "data" / "mt5" / "ticks"
HOUR = pd.Timedelta(hours=1)


def load_ticks(start, end, server="Pepperstone-Demo", symbol="XAUUSD"):
    """Ticks with start <= UTC time < end, as a DataFrame of bid, ask and flags.

    start and end are UTC (naive values are taken as UTC). Raises if any
    server-time hour in the range hasn't been archived. An archived hour with
    no ticks means the market was closed.
    """
    start, end = to_utc(start), to_utc(end)
    root = TICKS_DIR / server / symbol
    # Server time is UTC+2 or UTC+3, so these server hours cover the range.
    hours = pd.date_range((start + 2 * HOUR).tz_localize(None).floor("h"),
                          (end + 3 * HOUR).tz_localize(None).ceil("h"), freq="h", inclusive="left")
    paths = [root / f"{h:%Y/%m/%d/%H}.npz" for h in hours]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} hours not archived, first {missing[0]}")

    parts = []
    for p in paths:
        with np.load(p) as z:
            if len(z["time_msc"]):
                parts.append({k: z[k] for k in ("time_msc", "bid", "ask", "flags")})
    if not parts:
        return pd.DataFrame({"bid": [], "ask": [], "flags": []},
                            index=pd.DatetimeIndex([], tz="UTC", name="time"))
    cols = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    df = pd.DataFrame({k: cols[k] for k in ("bid", "ask", "flags")},
                      index=server_to_utc(cols["time_msc"]).rename("time"))
    return df[(df.index >= start) & (df.index < end)]
