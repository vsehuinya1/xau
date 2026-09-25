"""H10: does dollar-shock momentum hold up out of sample (2009-2017)?

Implements research/H10-dollar-shock-oos.md as pre-registered (commit 2f0522d).
  --check   print data checks (timezone, daily closes vs Pepperstone), counts and
            sample shocks up to entry; no outcomes
  (default) run the confirmation test and write research/H10-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.daily import daily_closes  # noqa: E402
from xau.eventstudy import (MIN, Bars, add_excess, clustered_t, control_means, measure,  # noqa: E402
                            series_at)
from xau.features import m5_atr  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

YEARS = range(2009, 2018)
LEVELS = (2.0, 3.0)
HORIZONS = (5, 15, 30)
PRIMARY = 15
MOVE_MINUTES = 5
COOLDOWN = 30
MAX_WAIT = 5
T_CONFIRM = 2.24
SUBPERIODS = [("2009-11", "2009-01-01", "2012-01-01"), ("2012-14", "2012-01-01", "2015-01-01"),
              ("2015-17", "2015-01-01", "2018-01-01")]


def z_scores(m1):
    b = Bars(m1)
    return pd.Series((b.close - b.price_at(b.tc - MOVE_MINUTES * MIN)) / series_at(m5_atr(m1), b.t), index=b.tc)


def load():
    gold = load_histdata("xauusd", YEARS)
    z = pd.concat({"EURUSD": z_scores(load_histdata("eurusd", YEARS)),
                   "USDJPY": z_scores(load_histdata("usdjpy", YEARS))}, axis=1, join="inner").dropna()
    return dict(gold=gold, bars=Bars(gold), day=trading_day(gold.index).to_numpy(), sess=session(gold.index),
                hour=gold.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(gold), z=z)


def shocks(d, k):
    z = d["z"]
    up = (z.EURUSD <= -k) & (z.USDJPY >= k)    # dollar up against both
    down = (z.EURUSD >= k) & (z.USDJPY <= -k)  # dollar down against both
    cand = z[up | down]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + COOLDOWN * MIN:
            kept.append(t)
            last = t
    ev = cand.loc[kept].reset_index(names="decided")
    ev["direction"] = np.sign(ev.EURUSD).astype(int)  # gold with the euro, against the dollar
    gold = d["bars"]
    ref = gold.next_bar(ev.decided.to_numpy())
    ok = ref < len(gold.t)
    ref = np.clip(ref, 0, len(gold.t) - 1)
    ev["ref"] = np.where(ok & (gold.t[ref] <= ev.decided.to_numpy() + MAX_WAIT * MIN), ref, -1)
    ev["shock"] = np.minimum(ev.EURUSD.abs(), ev.USDJPY.abs())
    return ev, len(cand)


def check(d):
    gold = d["gold"]
    ny_hour = gold.index.tz_convert(NY).hour
    print("gold bars per year:", dict(gold.groupby(gold.index.year).size()))
    print("gold bars by New York hour (17 should be ~empty, the daily break):",
          dict(pd.Series(ny_hour).value_counts().sort_index().loc[[15, 16, 17, 18, 19]]))
    hd = gold.close.groupby(trading_day(gold.index)).last()
    pp = daily_closes()
    both = pd.concat({"histdata": hd, "pepperstone": pp}, axis=1, join="inner").loc["2012":"2015"]
    diff = (both.histdata - both.pepperstone).abs()
    print(f"daily closes 2012-2015 vs Pepperstone: {len(both)} days, median |diff| ${diff.median():.2f}, "
          f"p95 ${diff.quantile(0.95):.2f}, correlation of daily changes {both.diff().corr().iloc[0, 1]:.4f}")
    print(f"paired FX minutes: {len(d['z']):,}")
    for k in LEVELS:
        ev, n = shocks(d, k)
        print(f"\n== k={k}: {n} shock minutes, {len(ev)} events after cooldown, {int((ev.ref >= 0).sum())} with a gold entry")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=3).iterrows():
            t = int(e.decided)
            print(f"  {pd.Timestamp(t, tz='UTC'):%Y-%m-%d %H:%M} UTC ({pd.Timestamp(t, tz='UTC').tz_convert(NY):%H:%M} NY): "
                  f"z EURUSD {e.EURUSD:+.2f}, USDJPY {e.USDJPY:+.2f} -> gold {'long' if e.direction > 0 else 'short'}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    gold = d["bars"]
    atr = series_at(d["atr"], gold.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (gold.t + 30 * MIN <= gold.tc[-1])
    cm, n_controls = control_means(gold, atr, d["sess"], d["hour"], keep, HORIZONS)
    rows, tests = {}, {}
    for k in LEVELS:
        ev, _ = shocks(d, k)
        ev = add_excess(measure(ev, gold, d["atr"], d["sess"], d["hour"], d["day"], HORIZONS, 30), cm, HORIZONS)
        ev = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
        tests[f"k={k:g}"] = ev
        t = clustered_t(ev[f"exc{PRIMARY}"], ev.day)
        subs = {n: ev[(ev.time >= pd.Timestamp(a, tz="UTC")) & (ev.time < pd.Timestamp(b, tz="UTC"))][f"exc{PRIMARY}"].mean()
                for n, a, b in SUBPERIODS}
        row = {"events": len(ev), "days": ev.day.nunique()}
        for h in HORIZONS:
            row[f"excess {h}m (ATR)"] = ev[f"exc{h}"].mean()
            row[f"t {h}m"] = clustered_t(ev[f"exc{h}"], ev.day)
        row.update({f"excess {n}": v for n, v in subs.items()})
        row["real (t >= 2.24)"] = bool(t >= T_CONFIRM)
        row["consistent (all sub-periods > 0)"] = bool(all(v > 0 for v in subs.values()))
        row["CONFIRMED"] = row["real (t >= 2.24)"] and row["consistent (all sub-periods > 0)"]
        rows[f"k={k:g}"] = row
    cells = pd.DataFrame(rows).T.rename_axis("test")
    out = [f"# H10 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on histdata M1 bars 2009-2017, "
           f"as pre-registered in `H10-dollar-shock-oos.md` (commit 2f0522d). Controls: {n_controls:,} gold moments.\n",
           "## Verdict\n", md(cells[["events", f"t {PRIMARY}m", "real (t >= 2.24)", "consistent (all sub-periods > 0)", "CONFIRMED"]]),
           "\n## In full\n", md(cells.T)]
    both = pd.concat(tests, names=["test"]).reset_index(level=0)
    both["shock size"] = pd.cut(both.shock, [2, 2.5, 3, 4, np.inf], right=False)
    for name, col in (("session", "session"), ("shock size (smaller |z|)", "shock size")):
        by = both.groupby(["test", col], observed=True)
        out.append(f"\n## By {name} (diagnostic)\n")
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    (ROOT / "research" / "H10-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[["events", f"t {PRIMARY}m", "real (t >= 2.24)", "consistent (all sub-periods > 0)", "CONFIRMED"]]))


if __name__ == "__main__":
    main()
