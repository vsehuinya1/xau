"""H07: do the dollar, EURUSD, USDJPY or silver move before gold?

Implements research/H07-leading-markets.md as pre-registered (commit 47d6e22).
  --check   print event counts and sample triggers up to gold's entry, no outcomes
  (default) run the study and write research/H07-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import (MIN, Bars, add_excess, clustered_t, control_means, evaluate,  # noqa: E402
                            measure, series_at)
from xau.features import m5_atr  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

LEADERS = {"USDX": -1, "EURUSD": 1, "USDJPY": -1, "XAGUSD": 1}  # sign of gold's expected response
HORIZONS = (5, 15, 30)
PRIMARY = 15
MOVE_MINUTES = 5
TRIGGER_ATR = 2.0
COOLDOWN = 30  # minutes between a leader's events
MAX_WAIT = 5   # minutes; a later gold bar means gold was closed


def load():
    gold = load_m1("2018-01-01")  # the loader keeps the holdout locked
    d = dict(bars=Bars(gold), day=trading_day(gold.index).to_numpy(), sess=session(gold.index),
             hour=gold.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(gold), leaders={})
    for sym in LEADERS:
        m1 = load_m1("2018-01-01", symbol=sym)
        d["leaders"][sym] = dict(bars=Bars(m1), atr=m5_atr(m1))
    return d


def leader_events(d, sym):
    lb = d["leaders"][sym]["bars"]
    move = lb.close - lb.price_at(lb.tc - MOVE_MINUTES * MIN)
    z = move / series_at(d["leaders"][sym]["atr"], lb.t)  # leader M5 ATR from bars closed by this bar's open
    cand = np.flatnonzero(np.abs(np.nan_to_num(z)) >= TRIGGER_ATR)
    kept, last = [], None
    for i in cand:
        if last is None or lb.tc[i] >= last + COOLDOWN * MIN:
            kept.append(i)
            last = lb.tc[i]
    i = np.array(kept, dtype=int)
    ev = pd.DataFrame({"leader": sym, "i": i, "z": z[i], "decided": lb.tc[i],
                       "direction": (np.sign(z[i]) * LEADERS[sym]).astype(int)})
    gold = d["bars"]
    k = gold.next_bar(ev.decided.to_numpy())
    ok = k < len(gold.t)
    k = np.clip(k, 0, len(gold.t) - 1)
    ev["ref"] = np.where(ok & (gold.t[k] <= ev.decided.to_numpy() + MAX_WAIT * MIN), k, -1)
    # diagnostic: had gold already moved >= 1 ATR in the implied direction over the same 5 minutes?
    g_atr = series_at(d["atr"], ev.decided.to_numpy())
    g_move = gold.price_at(ev.decided.to_numpy()) - gold.price_at(ev.decided.to_numpy() - MOVE_MINUTES * MIN)
    ev["gold_followed"] = ev.direction * g_move / g_atr >= 1
    return ev, len(cand)


def check(d):
    gold = d["bars"]
    for sym in LEADERS:
        ev, n_cand = leader_events(d, sym)
        print(f"\n== {sym}: {n_cand} bars with |z| >= {TRIGGER_ATR}, {len(ev)} events after cooldown, "
              f"{int((ev.ref >= 0).sum())} with a gold entry bar; gold already followed: {ev.gold_followed.mean():.1%}")
        lb = d["leaders"][sym]["bars"]
        for _, e in ev[ev.ref >= 0].sample(2, random_state=11).iterrows():
            i, k = int(e.i), int(e.ref)
            print(f"  trigger {pd.Timestamp(int(e.decided), tz='UTC'):%Y-%m-%d %H:%M} UTC  z {e.z:+.2f}  gold direction {e.direction:+d}")
            print(f"    {sym} closes: " + " ".join(f"{lb.close[j]:.5g}" for j in range(i - MOVE_MINUTES, i + 1)))
            print(f"    gold closes:  " + " ".join(f"{gold.price_at(np.array([int(e.decided) - m * MIN]))[0]:.2f}"
                                           for m in range(MOVE_MINUTES, -1, -1))
                  + f" -> entry at open {gold.open[k]:.2f} ({pd.Timestamp(gold.t[k], tz='UTC'):%H:%M})")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    gold = d["bars"]
    atr = series_at(d["atr"], gold.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (gold.t + 30 * MIN <= gold.tc[-1])
    cm, n_controls = control_means(gold, atr, d["sess"], d["hour"], keep, HORIZONS)
    tests, counts = {}, {}
    for sym in LEADERS:
        ev, n_cand = leader_events(d, sym)
        ev = measure(ev, gold, d["atr"], d["sess"], d["hour"], d["day"], HORIZONS, excursion_minutes=30)
        ev = add_excess(ev, cm, HORIZONS)
        tests[sym] = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
        counts[sym] = {"trigger bars": n_cand, "events": len(tests[sym])}
    cells = pd.DataFrame({s: evaluate(ev, HORIZONS, PRIMARY) for s, ev in tests.items()}).T
    cells.index.name = "leader"
    cols = ["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]
    out = [f"# H07 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars 2018-01-01 to "
           f"2025-09-30, as pre-registered in `H07-leading-markets.md` (commit 47d6e22).\n",
           "## Verdict\n", md(cells[cols]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in 2024-Sep 2025. "
           "C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Each test in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T),
           f"\nControls: {n_controls:,} gold M1 moments, each used long and short.\n"]
    both = pd.concat(tests.values(), ignore_index=True)  # events carry their leader column
    for name, col in (("session", "session"), ("whether gold had already followed", "gold_followed")):
        by = both.groupby(["leader", col])
        out.append(f"\n## By {name} (diagnostic)\n")
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    by = both.groupby("leader")
    out.append("\n## Excursions within 30 minutes, in gold ATR (diagnostic)\n")
    out.append(md(pd.DataFrame({"MFE median": by.mfe.median(), "MAE median": by.mae.median()})))
    (ROOT / "research" / "H07-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[cols]))


if __name__ == "__main__":
    main()
