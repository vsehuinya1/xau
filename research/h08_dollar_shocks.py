"""H08: do broad dollar shocks move gold enough to trade?

Implements research/H08-dollar-shocks.md as pre-registered (commit 1a28112).
  --check   print event counts and sample shocks up to gold's entry, no outcomes
  (default) run the study and write research/H08-results.md
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

LEVELS = (2.0, 3.0)
HORIZONS = (5, 15, 30)
PRIMARY = 15
MOVE_MINUTES = 5
COOLDOWN = 30
MAX_WAIT = 5


def z_scores(sym):
    """5-minute move / M5 ATR at each M1 close, indexed by close time (ns)."""
    m1 = load_m1("2018-01-01", symbol=sym)
    b = Bars(m1)
    z = (b.close - b.price_at(b.tc - MOVE_MINUTES * MIN)) / series_at(m5_atr(m1), b.t)
    return pd.Series(z, index=b.tc, name=sym)


def load():
    gold = load_m1("2018-01-01")  # the loader keeps the holdout locked
    z = pd.concat([z_scores("USDX"), z_scores("USDJPY")], axis=1, join="inner").dropna()
    return dict(bars=Bars(gold), day=trading_day(gold.index).to_numpy(), sess=session(gold.index),
                hour=gold.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(gold), z=z)


def shocks(d, k):
    z = d["z"]
    up = (z.USDX >= k) & (z.USDJPY >= k)
    down = (z.USDX <= -k) & (z.USDJPY <= -k)
    cand = z[up | down]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + COOLDOWN * MIN:
            kept.append(t)
            last = t
    ev = cand.loc[kept].reset_index(names="decided")
    ev["direction"] = -np.sign(ev.USDX).astype(int)  # gold against the dollar
    gold = d["bars"]
    ref = gold.next_bar(ev.decided.to_numpy())
    ok = ref < len(gold.t)
    ref = np.clip(ref, 0, len(gold.t) - 1)
    ev["ref"] = np.where(ok & (gold.t[ref] <= ev.decided.to_numpy() + MAX_WAIT * MIN), ref, -1)
    g_move = gold.price_at(ev.decided.to_numpy()) - gold.price_at(ev.decided.to_numpy() - MOVE_MINUTES * MIN)
    ev["gold_followed"] = ev.direction * g_move / series_at(d["atr"], ev.decided.to_numpy()) >= 1
    ev["shock"] = np.minimum(ev.USDX.abs(), ev.USDJPY.abs())
    return ev, len(cand)


def check(d):
    gold = d["bars"]
    print(f"paired minutes: {len(d['z']):,}")
    for k in LEVELS:
        ev, n = shocks(d, k)
        print(f"\n== k={k}: {n} shock minutes, {len(ev)} events after cooldown, {int((ev.ref >= 0).sum())} with a gold entry; "
              f"gold already followed {ev.gold_followed.mean():.1%}; dollar up {np.mean(ev.USDX > 0):.1%}")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=5).iterrows():
            t = int(e.decided)
            print(f"  {pd.Timestamp(t, tz='UTC'):%Y-%m-%d %H:%M} UTC: z USDX {e.USDX:+.2f}, z USDJPY {e.USDJPY:+.2f} -> gold "
                  f"{'long' if e.direction > 0 else 'short'}; gold 5 min before {gold.price_at(np.array([t - 5 * MIN]))[0]:.2f}, "
                  f"at shock {gold.price_at(np.array([t]))[0]:.2f}, entry open {gold.open[int(e.ref)]:.2f}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    gold = d["bars"]
    atr = series_at(d["atr"], gold.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (gold.t + 30 * MIN <= gold.tc[-1])
    cm, n_controls = control_means(gold, atr, d["sess"], d["hour"], keep, HORIZONS)
    tests = {}
    for k in LEVELS:
        ev, _ = shocks(d, k)
        ev = add_excess(measure(ev, gold, d["atr"], d["sess"], d["hour"], d["day"], HORIZONS, 30), cm, HORIZONS)
        tests[f"k={k:g}"] = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
    cells = pd.DataFrame({name: evaluate(ev, HORIZONS, PRIMARY) for name, ev in tests.items()}).T
    cells.index.name = "test"
    cols = ["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]
    out = [f"# H08 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars 2018-01-01 to "
           f"2025-09-30, as pre-registered in `H08-dollar-shocks.md` (commit 1a28112). A pass is provisional "
           "until confirmed on the holdout.\n",
           "## Verdict\n", md(cells[cols]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in 2024-Sep 2025. "
           "C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Each test in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T),
           f"\nControls: {n_controls:,} gold M1 moments, each used long and short.\n"]
    both = pd.concat({n: ev for n, ev in tests.items()}, names=["test"]).reset_index(level=0)
    both["shock size"] = pd.cut(both.shock, [2, 2.5, 3, 4, np.inf], right=False)
    for name, col in (("session", "session"), ("whether gold had already followed", "gold_followed"),
                      ("shock size (smaller of the two z)", "shock size")):
        by = both.groupby(["test", col], observed=True)
        out.append(f"\n## By {name} (diagnostic)\n")
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"net {PRIMARY}m $ (all years)": by[f"net{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    (ROOT / "research" / "H08-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[cols]))


if __name__ == "__main__":
    main()
