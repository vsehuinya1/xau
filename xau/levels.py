"""Price levels that can be computed without hindsight, per trading day."""
import pandas as pd

from xau.sessions import session, trading_day


def daily_levels(m1):
    """Per trading day: prior-day high/low and the Asia-session high/low.

    pdh/pdl come from the previous trading day in the data and are known from
    the start of the day. asia_hi/asia_lo are known from 03:00 New York time.
    """
    day = trading_day(m1.index)
    asia = session(m1.index) == "Asia"
    by_day = m1.groupby(day)
    levels = pd.DataFrame({"pdh": by_day.high.max().shift(1), "pdl": by_day.low.min().shift(1)})
    by_asia = m1[asia].groupby(day[asia])
    levels["asia_hi"] = by_asia.high.max()
    levels["asia_lo"] = by_asia.low.min()
    return levels
