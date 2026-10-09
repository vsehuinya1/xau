"""H16: two enhancements to dollar-shock momentum.

Implements research/H16-dollar-enhancements.md as pre-registered (commit 690ced3).
Writes research/H16-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import COOLDOWN, shocks, simulate, z_scores  # noqa: E402
from xau.eventstudy import MIN, Bars, clustered_t, series_at  # noqa: E402
from xau.features import m5_atr  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402

PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCAD": 1, "USDCHF": 1}  # dollar-z = sign * z
K, MIN_PAIRS, AGAINST = 3.0, 4, -1.0
HOLD = 30


def broad_shocks(fx):
    z = pd.concat({p: s * z_scores(fx[p]) for p, s in PAIRS.items()}, axis=1, join="inner").dropna()
    up = ((z >= K).sum(axis=1) >= MIN_PAIRS) & (z.min(axis=1) > AGAINST)
    down = ((z <= -K).sum(axis=1) >= MIN_PAIRS) & (z.max(axis=1) < -AGAINST)
    cand = z[up | down]
    kept, last = [], None
    for t in cand.index:
        if last is None or t >= last + COOLDOWN * MIN:
            kept.append(t)
            last = t
    return pd.DataFrame({"time": kept, "direction": np.where(up[kept], -1, 1)})  # gold against the dollar


def followed(sig, gold):
    """Gold already moved >= 1 ATR(M5) in the implied direction over the shock's 5 minutes."""
    b = Bars(gold)
    t = sig.time.to_numpy()
    move = b.price_at(t) - b.price_at(t - 5 * MIN)
    return sig.direction.to_numpy() * move / series_at(m5_atr(gold), t) >= 1


def stats(tr):
    day = trading_day(pd.DatetimeIndex(tr.entry_time))
    return {"trades": len(tr), "mean net (news-heavy) $/oz": tr.net_news_heavy.mean(),
            "t (news-heavy)": clustered_t(tr.net_news_heavy, day), "mean net (base) $/oz": tr.net.mean(),
            "win rate %": (tr.net_news_heavy > 0).mean() * 100, "total (news-heavy) $/oz": tr.net_news_heavy.sum()}


def main():
    years = range(2009, 2018)
    hist = {p.upper(): load_histdata(p.lower(), years) for p in PAIRS} | {"XAUUSD": load_histdata("xauusd", years)}
    pep = {p: load_m1("2018-01-01", symbol=p) for p in list(PAIRS) + ["XAUUSD"]}
    samples = {"histdata 2009-2017": (hist, 0.51), "Pepperstone 2018-Sep 2025": (pep, 0.11)}
    table = {}
    for name, (d, base_cost) in samples.items():
        gold = d["XAUUSD"]
        base_sig = shocks(d["EURUSD"], d["USDJPY"], 3.0)
        table[("baseline (EUR+JPY)", name)] = stats(simulate(base_sig, gold, HOLD, cost_fixed=base_cost))
        table[("T1 six-currency broad shock", name)] = stats(simulate(broad_shocks(d), gold, HOLD, cost_fixed=base_cost))
        table[("T2 baseline, gold already followed", name)] = stats(simulate(base_sig[followed(base_sig, gold)], gold, HOLD, cost_fixed=base_cost))
        table[("(diagnostic) baseline, gold not yet followed", name)] = stats(simulate(base_sig[~followed(base_sig, gold)], gold, HOLD, cost_fixed=base_cost))
    T = pd.DataFrame(table).T
    m, t = "mean net (news-heavy) $/oz", "t (news-heavy)"
    h, p = "histdata 2009-2017", "Pepperstone 2018-Sep 2025"
    b = lambda s: T.loc[("baseline (EUR+JPY)", s), m]  # noqa: E731
    t1 = all(T.loc[("T1 six-currency broad shock", s), m] > 0 and T.loc[("T1 six-currency broad shock", s), t] >= 2
             and T.loc[("T1 six-currency broad shock", s), m] >= b(s) for s in (h, p))
    k2 = ("T2 baseline, gold already followed", h)
    t2 = T.loc[k2, m] > 0 and T.loc[k2, t] >= 2 and T.loc[k2, m] >= b(h)
    out = [f"# H16 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in "
           "`H16-dollar-enhancements.md` (commit 690ced3). Hold 30 min; costs include H11's news-heavy add-on.\n",
           "## Verdict\n", md(pd.DataFrame({"T1 six-currency broad shock": {"PASS": bool(t1)},
                                           "T2 gold already followed (judged on 2009-2017)": {"PASS": bool(t2)}}).T.rename_axis("test")),
           "\n## Results\n", md(T.rename_axis(["strategy", "sample"]))]
    (ROOT / "research" / "H16-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
