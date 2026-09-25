"""H09: do sharp gold moves reverse when the dollar is quiet?

Implements research/H09-quiet-dollar-shocks.md as pre-registered (commit 2b63dab).
  --check   print event counts and sample shocks up to entry, no outcomes
  (default) run the study and write research/H09-results.md
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

GOLD_SHOCK = 3.0
DOLLAR_QUIET = 1.0
HORIZONS = (5, 15, 30)
PRIMARY = 15
MOVE_MINUTES = 5
COOLDOWN = 30
MAX_WAIT = 5


def z_scores(m1):
    """5-minute move / M5 ATR at each M1 close, indexed by close time (ns)."""
    b = Bars(m1)
    return pd.Series((b.close - b.price_at(b.tc - MOVE_MINUTES * MIN)) / series_at(m5_atr(m1), b.t), index=b.tc)


def load():
    gold = load_m1("2018-01-01")  # the loader keeps the holdout locked
    z = pd.concat({"gold": z_scores(gold), "USDX": z_scores(load_m1("2018-01-01", symbol="USDX")),
                   "USDJPY": z_scores(load_m1("2018-01-01", symbol="USDJPY"))}, axis=1, join="inner").dropna()
    return dict(bars=Bars(gold), day=trading_day(gold.index).to_numpy(), sess=session(gold.index),
                hour=gold.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(gold), z=z)


def shocks(d, which):
    """which='quiet': the dollar was quiet (the test); 'confirmed': the dollar moved with gold (diagnostic)."""
    z = d["z"]
    big = z.gold.abs() >= GOLD_SHOCK
    if which == "quiet":
        cond = big & (z.USDX.abs() < DOLLAR_QUIET) & (z.USDJPY.abs() < DOLLAR_QUIET)
    else:  # gold up with the dollar down in both, or gold down with the dollar up in both
        s = np.sign(z.gold)
        cond = big & (-s * z.USDX >= DOLLAR_QUIET) & (-s * z.USDJPY >= DOLLAR_QUIET)
    cand = z[cond]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + COOLDOWN * MIN:
            kept.append(t)
            last = t
    ev = cand.loc[kept].reset_index(names="decided")
    ev["direction"] = -np.sign(ev.gold).astype(int)  # fade the gold move
    gold = d["bars"]
    ref = gold.next_bar(ev.decided.to_numpy())
    ok = ref < len(gold.t)
    ref = np.clip(ref, 0, len(gold.t) - 1)
    ev["ref"] = np.where(ok & (gold.t[ref] <= ev.decided.to_numpy() + MAX_WAIT * MIN), ref, -1)
    return ev, len(cand)


def check(d):
    gold = d["bars"]
    print(f"paired minutes: {len(d['z']):,}; gold |z| >= {GOLD_SHOCK}: {int((d['z'].gold.abs() >= GOLD_SHOCK).sum()):,}")
    for which in ("quiet", "confirmed"):
        ev, n = shocks(d, which)
        print(f"\n== dollar {which}: {n} shock minutes, {len(ev)} events after cooldown, {int((ev.ref >= 0).sum())} with entry")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=9).iterrows():
            t = int(e.decided)
            print(f"  {pd.Timestamp(t, tz='UTC'):%Y-%m-%d %H:%M} UTC: z gold {e.gold:+.2f}, USDX {e.USDX:+.2f}, USDJPY {e.USDJPY:+.2f}"
                  f" -> {'long' if e.direction > 0 else 'short'} (fade); gold 5 min before "
                  f"{gold.price_at(np.array([t - 5 * MIN]))[0]:.2f}, at shock {gold.price_at(np.array([t]))[0]:.2f}, "
                  f"entry open {gold.open[int(e.ref)]:.2f}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    gold = d["bars"]
    atr = series_at(d["atr"], gold.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (gold.t + 30 * MIN <= gold.tc[-1])
    cm, n_controls = control_means(gold, atr, d["sess"], d["hour"], keep, HORIZONS)
    tests = {}
    for which in ("quiet", "confirmed"):
        ev, _ = shocks(d, which)
        ev = add_excess(measure(ev, gold, d["atr"], d["sess"], d["hour"], d["day"], HORIZONS, 30), cm, HORIZONS)
        tests[f"dollar {which}"] = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
    cells = pd.DataFrame({n: evaluate(ev, HORIZONS, PRIMARY) for n, ev in tests.items()}).T
    cells.index.name = "gold shock, fade"
    cols = ["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]
    out = [f"# H09 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars 2018-01-01 to "
           f"2025-09-30, as pre-registered in `H09-quiet-dollar-shocks.md` (commit 2b63dab). The test is "
           "'dollar quiet'; 'dollar confirmed' is a diagnostic contrast.\n",
           "## Verdict\n", md(cells[cols]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in 2024-Sep 2025. "
           "C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Each in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T),
           f"\nControls: {n_controls:,} gold M1 moments, each used long and short.\n"]
    q = tests["dollar quiet"]
    by = q.groupby("session")
    out.append("\n## Dollar quiet, by session (diagnostic)\n")
    out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                f"move {PRIMARY}m (ATR)": by[f"atr{PRIMARY}"].mean(),
                                f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    (ROOT / "research" / "H09-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[cols]))


if __name__ == "__main__":
    main()
