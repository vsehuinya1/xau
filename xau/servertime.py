"""MT5 server time -> UTC.

MT5 stamps ticks and bars in the broker's server time. Pepperstone runs its
server clock at New York time + 7 hours, so the daily rollover (17:00 New York)
lands at 00:00: UTC+3 during US daylight saving, UTC+2 otherwise.

Checked against the live clock (+3 on 2026-09-25) and, over 2017-07..2026-09,
against the market-driven daily reopen at 18:00 New York: 96% of 2,390
reopens land at 18:00-18:05 under the rule. The exception is winter 2017/18,
when the server stayed on UTC+3: reopens and the 08:30 NFP spike sit an hour
late under the rule from the US clock change on 2017-11-05 until the daily
break before 2018-02-27 (server time). Note that Pepperstone's closes are set
in server time, so they look right whatever the clock does; only market-driven
times can show an offset error.
"""
import numpy as np
import pandas as pd

# Server-time window in which the server clock was UTC+3 instead of the rule.
STUCK_ON_UTC3 = (pd.Timestamp("2017-11-04"), pd.Timestamp("2018-02-27 00:30"))


def to_utc(t):
    """Timestamp-like -> UTC Timestamp (naive values are taken as UTC)."""
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def server_to_utc(server_ms):
    """MT5 server-time milliseconds -> UTC DatetimeIndex."""
    server = pd.to_datetime(np.asarray(server_ms), unit="ms")
    stuck = (server >= STUCK_ON_UTC3[0]) & (server < STUCK_ON_UTC3[1])
    rule = (server[~stuck] - pd.Timedelta(hours=7)).tz_localize(
        "America/New_York", ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    fixed = (server[stuck] - pd.Timedelta(hours=3)).tz_localize("UTC")
    out = np.empty(len(server), dtype="int64")
    out[~stuck] = rule.as_unit("ns").asi8
    out[stuck] = fixed.as_unit("ns").asi8
    return pd.DatetimeIndex(out.astype("datetime64[ns]")).tz_localize("UTC")
