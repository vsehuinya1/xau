"""Daily closes from Pepperstone's bars.

Uses every bar type in the M1 series (daily bars 1998-2015, hourly 2016, M1
from 2017). The close is the last price of each Monday-Friday trading day,
before the 17:00 New York rollover.
"""
from xau.bars import load_m1
from xau.sessions import trading_day


def daily_closes(allow_holdout=False):
    """Series of daily closes indexed by trading day (naive date)."""
    bars = load_m1(allow_holdout=allow_holdout)
    closes = bars.close.groupby(trading_day(bars.index)).last()
    return closes[closes.index.dayofweek < 5].rename("close")
