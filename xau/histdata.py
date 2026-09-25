"""histdata.com generic ASCII M1 bars (bid prices), cached in data/histdata/.

Files are DAT_ASCII_<PAIR>_M1_<YEAR>.zip, each holding a ';'-separated CSV of
"YYYYMMDD HHMMSS;open;high;low;close;volume". There are no spreads, so
`spread` is 0.

The timestamps are **New York local time, including daylight saving**. That
contradicts histdata's "EST without DST" label. It was checked on 2012-2017 US
jobs reports for XAUUSD, EURUSD and USDJPY: the 08:30 New York spike sits at
08:30 in winter and 09:30 in summer if the times are read as fixed EST.

Download with the `histdata` package, e.g. from data/histdata/:
  download_hist_data(year="2012", pair="xauusd", platform=Platform.GENERIC_ASCII,
                     time_frame=TimeFrame.ONE_MINUTE)
"""
import zipfile
from pathlib import Path

import pandas as pd

from xau import holdout

HISTDATA_DIR = Path(__file__).resolve().parent.parent / "data" / "histdata"


def load_histdata(pair, years, allow_holdout=False):
    """M1 bars for the pair and years, indexed by UTC bar open time."""
    frames = []
    for year in years:
        with zipfile.ZipFile(HISTDATA_DIR / f"DAT_ASCII_{pair.upper()}_M1_{year}.zip") as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(name) as f:
                frames.append(pd.read_csv(f, sep=";", header=None,
                                          names=["time", "open", "high", "low", "close", "volume"]))
    df = pd.concat(frames, ignore_index=True)
    local = pd.DatetimeIndex(pd.to_datetime(df.time, format="%Y%m%d %H%M%S"))
    df.index = local.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise").tz_convert("UTC").rename("time")
    df = df[~df.index.duplicated()].sort_index()
    holdout.check(df.index[-1] + pd.Timedelta(minutes=1), allow_holdout)
    return pd.DataFrame({"open": df.open, "high": df.high, "low": df.low, "close": df.close,
                         "tick_volume": df.volume, "spread": 0.0})
