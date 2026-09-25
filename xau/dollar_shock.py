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


def shocks(eurusd, usdjpy, k, cooldown=COOLDOWN):
    """Shock times (ns, M1 close) and gold direction (+1 long / -1 short)."""
    z = pd.concat({"EURUSD": z_scores(eurusd), "USDJPY": z_scores(usdjpy)}, axis=1, join="inner").dropna()
    up = (z.EURUSD <= -k) & (z.USDJPY >= k)    # dollar up against both
    down = (z.EURUSD >= k) & (z.USDJPY <= -k)  # dollar down against both
    cand = z[up | down]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + cooldown * MIN:
            kept.append(t)
            last = t
    out = cand.loc[kept].reset_index(names="time")
    out["direction"] = np.sign(out.EURUSD).astype(int)  # gold with the euro, against the dollar
    return out


def simulate(signals, gold, hold, cost_fixed=COST_FIXED):
    """One trade per signal: enter at the next gold M1 open, exit after `hold` minutes.

    Signals arriving while a position is open are skipped. Returns one row per
    trade with prices, cost and net $/oz.
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
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "direction", "entry", "exit", "cost", "net"])
