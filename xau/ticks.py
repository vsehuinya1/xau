"""Load ticks archived by mt5/winpy/recorder.py.

MT5 stamps ticks in the broker's server time. Pepperstone runs its server
clock at New York time + 7 hours, so the daily rollover (17:00 New York) lands
at 00:00: UTC+3 during US daylight saving, UTC+2 otherwise. Checked: +3 on
2026-09-25. The +2 still needs confirming in offset_log.csv after the US clock
change on 2026-11-01.
"""
from pathlib import Path

import numpy as np
import pandas as pd

TICKS_DIR = Path(__file__).resolve().parent.parent / "data" / "ticks"
HOUR = pd.Timedelta(hours=1)


def server_to_utc(server_ms):
    """MT5 server-time milliseconds -> UTC DatetimeIndex."""
    new_york = pd.to_datetime(np.asarray(server_ms), unit="ms") - pd.Timedelta(hours=7)
    return new_york.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise").tz_convert("UTC")


def load_ticks(start, end, server="Pepperstone-Demo", symbol="XAUUSD"):
    """Ticks with start <= UTC time < end, as a DataFrame of bid, ask and flags.

    start and end are UTC (naive values are taken as UTC). Raises if any
    server-time hour in the range hasn't been archived. An archived hour with
    no ticks means the market was closed.
    """
    start, end = (pd.Timestamp(t).tz_localize("UTC") if pd.Timestamp(t).tzinfo is None
                  else pd.Timestamp(t).tz_convert("UTC") for t in (start, end))
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
