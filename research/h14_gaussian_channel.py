"""H14: the Gaussian channel trend system on H1 and H4.

Implements research/H14-gaussian-channel.md as pre-registered.
Writes research/H14-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.rates import fed_funds  # noqa: E402
from xau.report import md  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

POLES, PERIOD, MULT = 4, 144, 1.414
LONG_MARKUP, SHORT_MARKUP = 3.51, 1.18
FLAT_COST = 0.51
NY = "America/New_York"


def gaussian(x, alpha, poles=POLES):
    """N-pole Gaussian filter (Ehlers), recursive, as in DonovanWall's script."""
    from math import comb
    a1 = 1 - alpha
    w = [(-1) ** (k + 1) * comb(poles, k) * a1 ** k for k in range(1, poles + 1)]
    f = np.zeros(len(x))
    for t in range(len(x)):
        acc = alpha ** poles * x[t]
        for k in range(1, poles + 1):
            if t - k >= 0:
                acc += w[k - 1] * f[t - k]
        f[t] = acc
    return f


def channel(bars):
    beta = (1 - np.cos(2 * np.pi / PERIOD)) / (1.414 ** (2 / POLES) - 1)
    alpha = -beta + np.sqrt(beta ** 2 + 2 * beta)
    src = ((bars.high + bars.low + bars.close) / 3).to_numpy()
    prev = bars.close.shift(1).fillna(bars.open)
    tr = (np.maximum(bars.high, prev) - np.minimum(bars.low, prev)).to_numpy()
    f, ftr = gaussian(src, alpha), gaussian(tr, alpha)
    return f, f + MULT * ftr, f - MULT * ftr


def resample(m1, rule):
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "first"}
    return m1.resample(rule).agg(agg).dropna(subset=["close"])


def rollovers(t0, t1):
    """Swap nights between two UTC times: 17:00 New York crossings, Wednesday counting 3."""
    a, b = t0.tz_convert(NY), t1.tz_convert(NY)
    days = pd.date_range(a.normalize(), b.normalize(), freq="D", tz=NY)
    n = 0
    for d in days:
        roll = d + pd.Timedelta(hours=17)
        if a < roll <= b and roll.dayofweek < 5:
            n += 3 if roll.dayofweek == 2 else 1
    return n


def simulate(bars, flat_cost, ff):
    f, up, lo = channel(bars)
    o, c = bars.open.to_numpy(), bars.close.to_numpy()
    spread = bars.spread.to_numpy() * 0.01
    idx = bars.index
    warm = PERIOD * 3
    rows, pos, entry_i = [], 0, None
    for i in range(warm, len(bars) - 1):
        if pos == 0:
            want = 1 if (f[i] > f[i - 1] and c[i] > up[i]) else -1 if (f[i] < f[i - 1] and c[i] < lo[i]) else 0
            if want:
                pos, entry_i = want, i + 1
        else:
            if (pos > 0 and c[i] < up[i]) or (pos < 0 and c[i] > lo[i]):
                k = entry_i
                t0, t1 = idx[k], idx[i + 1]
                entry, exit_ = o[k], o[i + 1]
                rate = ff.asof(t0.tz_localize(None).normalize())
                nights = rollovers(t0, t1)
                yearly = -(rate + LONG_MARKUP) if pos > 0 else (rate - SHORT_MARKUP)
                swap = yearly / 100 / 365 * nights * entry
                cost = flat_cost if flat_cost is not None else spread[k] + 0.11
                gross = pos * (exit_ - entry)
                rows.append((t0, t1, pos, entry, exit_, gross, cost, swap, gross - cost + swap))
                pos = 0
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", "entry", "exit", "gross", "cost", "swap", "net"])


def summarize(t, years):
    n = len(t)
    tstat = t.net.mean() / t.net.std() * np.sqrt(n) if n > 1 else np.nan
    wins, losses = t.net[t.net > 0].sum(), -t.net[t.net < 0].sum()
    return {"trades": n, "trades/yr": n / years, "mean net $/oz": t.net.mean(), "t": tstat,
            "mean gross $/oz": t.gross.mean(), "mean swap $/oz": t.swap.mean(), "win rate %": (t.net > 0).mean() * 100,
            "profit factor": wins / losses if losses else np.nan, "total net $/oz": t.net.sum(),
            "max drawdown $/oz": max_drawdown(t.net), "avg hold h": (t.exit_time - t.entry_time).dt.total_seconds().mean() / 3600,
            "long share %": (t.side > 0).mean() * 100}


def main():
    ff = fed_funds()
    samples = {"histdata 2009-2017": (load_histdata("xauusd", range(2009, 2018)), FLAT_COST, 9.0),
               "Pepperstone 2018-Sep 2025": (load_m1("2018-01-01"), None, 7.75)}
    recent = load_m1("2025-01-01", None, allow_holdout=True)
    table, verdict = {}, {}
    for tf, rule in (("H1", "1h"), ("H4", "4h")):
        for name, (m1, cost, yrs) in samples.items():
            table[(tf, name)] = summarize(simulate(resample(m1, rule), cost, ff), yrs)
        verdict[tf] = all(table[(tf, n)]["mean net $/oz"] > 0 and table[(tf, n)]["t"] >= 2 for n in samples)
        r = simulate(resample(recent, rule), None, ff)
        table[(tf, "Oct 2025-Sep 2026 (diagnostic)")] = summarize(r[r.entry_time >= pd.Timestamp("2025-10-01", tz="UTC")], 1.0)
    out = [f"# H14 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in "
           "`H14-gaussian-channel.md`. Net $/oz per trade after trading costs and swap.\n",
           "## Verdict (both samples: net > 0 with t >= 2)\n",
           md(pd.DataFrame({k: {"PASS": v} for k, v in verdict.items()}).T.rename_axis("timeframe")),
           "\n## Results\n", md(pd.DataFrame(table).T.rename_axis(["timeframe", "sample"]))]
    (ROOT / "research" / "H14-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
