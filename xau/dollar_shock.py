"""Dollar-shock momentum: signals and trade simulation (research/H11).

A broad dollar shock is an M1 close where EURUSD and USDJPY have both moved
at least k x their M5 ATR over 5 minutes, in the same dollar direction. Gold
tends to keep moving against the dollar for 15-30 minutes afterwards (H07-H10).
"""
import numpy as np
import pandas as pd

from xau.eventstudy import MIN, Bars, series_at
from xau.features import m5_atr

MOVE_MINUTES = 5
COOLDOWN = 30   # minutes between shocks
MAX_WAIT = 5    # minutes; skip if gold has no bar this soon (closed)
COST_FIXED = 0.11


def z_scores(m1):
    """5-minute move / M5 ATR at each M1 close, indexed by close time (ns)."""
    b = Bars(m1)
    return pd.Series((b.close - b.price_at(b.tc - MOVE_MINUTES * MIN)) / series_at(m5_atr(m1), b.t), index=b.tc)


def gold_direction(z_eur, z_jpy, k):
    """+1 (buy gold) on a broad dollar fall, -1 (sell) on a broad dollar rise, 0 otherwise.

    Works on scalars or arrays. The one definition of a shock, shared by the
    research and the paper-trading bot.
    """
    up = (np.asarray(z_eur) <= -k) & (np.asarray(z_jpy) >= k)    # dollar up against both
    down = (np.asarray(z_eur) >= k) & (np.asarray(z_jpy) <= -k)  # dollar down against both
    return np.where(down, 1, np.where(up, -1, 0))


def shocks(eurusd, usdjpy, k, cooldown=COOLDOWN):
    """Shock times (ns, M1 close) and gold direction (+1 long / -1 short)."""
    z = pd.concat({"EURUSD": z_scores(eurusd), "USDJPY": z_scores(usdjpy)}, axis=1, join="inner").dropna()
    cand = z[gold_direction(z.EURUSD, z.USDJPY, k) != 0]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + cooldown * MIN:
            kept.append(t)
            last = t
    out = cand.loc[kept].reset_index(names="time")
    out["direction"] = np.sign(out.EURUSD).astype(int)  # gold with the euro, against the dollar
    return out


def news_heavy_extra(entry_times):
    """H11's harsh cost add-on: +$0.80/oz for entries 08:30-08:45 New York, +$0.10 otherwise.

    The M1 bar spread field is about the calmest spread in the minute. Real
    entry spreads at big releases were up to $0.90 (H11-news-costs.md).
    """
    ny = pd.DatetimeIndex(entry_times).tz_convert("America/New_York")
    minute = ny.hour * 60 + ny.minute
    return np.where((minute >= 8 * 60 + 30) & (minute < 8 * 60 + 45), 0.80, 0.10)


def simulate(signals, gold, hold, cost_fixed=COST_FIXED):
    """One trade per signal: enter at the next gold M1 open, exit after `hold` minutes.

    Signals arriving while a position is open are skipped. Returns one row per
    trade with prices, cost and net $/oz, plus net_news_heavy under H11's harsh
    news-time cost add-on.
    """
    b = Bars(gold)
    rows, busy_until = [], None
    for s in signals.itertuples():
        k = int(np.searchsorted(b.t, s.time, side="left"))
        if k >= len(b.t) or b.t[k] > s.time + MAX_WAIT * MIN:
            continue
        entry_t = b.t[k]
        if busy_until is not None and entry_t < busy_until:
            continue
        exit_t = entry_t + hold * MIN
        if exit_t > b.tc[-1]:
            break
        entry, exit_ = b.open[k], b.price_at(np.array([exit_t]))[0]
        cost = b.spread[k] + cost_fixed
        rows.append((pd.Timestamp(entry_t, tz="UTC"), pd.Timestamp(exit_t, tz="UTC"), s.direction, entry, exit_,
                     cost, s.direction * (exit_ - entry) - cost))
        busy_until = exit_t
    trades = pd.DataFrame(rows, columns=["entry_time", "exit_time", "direction", "entry", "exit", "cost", "net"])
    trades["net_news_heavy"] = trades.net - news_heavy_extra(trades.entry_time)
    return trades
