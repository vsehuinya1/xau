"""Trading days and sessions, in New York time.

A trading day runs from 18:00 to 17:00 New York time and is labelled with the
date it ends on. Sessions: Asia 18:00-03:00, London 03:00-08:00, NY morning
08:00-12:00, NY afternoon 12:00-17:00.

The day rolls over at 17:00 New York (00:00 server time), not 18:00. No M1
bars fall between 17:00 and 18:00 because the market is closed then, but
Pepperstone's daily bars for 1998-2015 open at 17:00 and belong to the day
they start.
"""
import numpy as np
import pandas as pd

NY = "America/New_York"
SESSIONS = ("Asia", "London", "NY am", "NY pm")


def trading_day(index):
    """Trading-day label for each time in a tz-aware DatetimeIndex."""
    local = index.tz_convert(NY).tz_localize(None)
    return (local + pd.Timedelta(hours=7)).normalize()


def session(index):
    """Session name for each time; 'closed' for 17:00-18:00 New York time."""
    hour = index.tz_convert(NY).hour
    return np.select([(hour >= 18) | (hour < 3), (hour >= 3) & (hour < 8),
                      (hour >= 8) & (hour < 12), (hour >= 12) & (hour < 17)],
                     list(SESSIONS), default="closed")
