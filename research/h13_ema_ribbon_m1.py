"""H13: the M1 EMA-ribbon pullback system, with and without a Bollinger filter.

Implements research/H13-ema-ribbon-m1.md as pre-registered (commit f50269a).
Writes research/H13-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, clustered_t  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import session, trading_day  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

TARGET_R = 1.5
MAX_BARS = 120
SWING = 10
MIN_STOP_ATR = 0.5
MAX_WAIT = 5
FLAT_COST = 0.51


def signals(m1):
    c, h, l = m1.close, m1.high, m1.low
    e20, e50, e200 = (c.ewm(span=n, adjust=False).mean() for n in (20, 50, 200))
    mid, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    below_bb = (c < mid - 2 * sd).astype(float).rolling(20).max().shift(1) == 1
    above_bb = (c > mid + 2 * sd).astype(float).rolling(20).max().shift(1) == 1
    prev = c.shift(1)
    atr = (np.maximum(h, prev) - np.minimum(l, prev)).rolling(14).mean()
    short = (c < e200) & (e20 < e50) & (h >= e20) & (c < e20)
    long_ = (c > e200) & (e20 > e50) & (l <= e20) & (c > e20)
    side = np.where(short, -1, np.where(long_, 1, 0))
    impulse = np.where(short, below_bb, np.where(long_, above_bb, False))
    return side, impulse.astype(bool), atr.to_numpy()


def simulate(m1, flat_cost, sessions_allowed=("Asia",), use_bb=False):
    side, impulse, atr = signals(m1)
    t = m1.index.as_unit("ns").asi8
    o, h, l, c = (m1[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    spread = m1["spread"].to_numpy(float) * 0.01
    sess, day = session(m1.index), trading_day(m1.index)
    rows, free_from = [], 0
    for i in np.flatnonzero(side != 0):
        k = i + 1
        if i < free_from or k >= len(t) - MAX_BARS or i < SWING or not np.isfinite(atr[i]):
            continue
        if use_bb and not impulse[i]:
            continue
        if t[k] - (t[i] + MIN) > MAX_WAIT * MIN or sess[k] not in sessions_allowed:
            continue
        s, entry = int(side[i]), o[k]
        swing = h[i - SWING + 1:i + 1].max() if s < 0 else l[i - SWING + 1:i + 1].min()
        risk = max(s * (entry - swing), MIN_STOP_ATR * atr[i])
        stop, target = entry - s * risk, entry + s * TARGET_R * risk
        hh, ll, oo = h[k:k + MAX_BARS], l[k:k + MAX_BARS], o[k:k + MAX_BARS]
        hit_stop = (ll <= stop) if s > 0 else (hh >= stop)
        hit_tgt = (hh >= target) if s > 0 else (ll <= target)
        js = np.argmax(hit_stop) if hit_stop.any() else MAX_BARS
        jt = np.argmax(hit_tgt) if hit_tgt.any() else MAX_BARS
        if js <= jt and js < MAX_BARS:  # stop first, also when both in one bar
            j, exit_ = js, (oo[js] if s * (oo[js] - stop) < 0 else stop)
        elif jt < MAX_BARS:
            j, exit_ = jt, (oo[jt] if s * (oo[jt] - target) > 0 else target)
        else:
            j, exit_ = MAX_BARS - 1, c[k + MAX_BARS - 1]
        cost = flat_cost if flat_cost is not None else spread[k] + 0.11
        gross = s * (exit_ - entry)
        rows.append((pd.Timestamp(t[k], tz="UTC"), day[k], sess[k], s, entry, stop, target, exit_, gross / risk, gross - cost, cost))
        free_from = k + j + 1
    return pd.DataFrame(rows, columns=["entry_time", "day", "session", "side", "entry", "stop", "target", "exit",
                                       "R", "net", "cost"])


def summarize(f, years):
    wins, losses = f.net[f.net > 0].sum(), -f.net[f.net < 0].sum()
    return {"trades": len(f), "trades/yr": len(f) / years, "mean net $/oz": f.net.mean(),
            "t (by day)": clustered_t(f.net, f.day), "win rate %": (f.net > 0).mean() * 100,
            "mean R (gross)": f.R.mean(), "profit factor": wins / losses if losses else np.nan,
            "total net $/oz": f.net.sum(), "max drawdown $/oz": max_drawdown(f.net), "mean cost $/oz": f.cost.mean()}


def main():
    samples = {"histdata 2009-2017": (load_histdata("xauusd", range(2009, 2018)), FLAT_COST, 9.0),
               "Pepperstone 2018-Sep 2025": (load_m1("2018-01-01"), None, 7.75)}
    table, verdict = {}, {}
    for test, bb in (("T1 EMA system", False), ("T2 + Bollinger impulse", True)):
        for name, (m1, cost, yrs) in samples.items():
            table[(test, name)] = summarize(simulate(m1, cost, use_bb=bb), yrs)
        verdict[test] = all(table[(test, n)]["mean net $/oz"] > 0 and table[(test, n)]["t (by day)"] >= 2 for n in samples)
    diag = {}
    pep = samples["Pepperstone 2018-Sep 2025"][0]
    for sess in ("London", "NY am", "NY pm"):
        diag[("T1, other session", sess)] = summarize(simulate(pep, None, sessions_allowed=(sess,)), 7.75)
    recent = load_m1("2025-09-01", None, allow_holdout=True)
    for test, bb in (("T1", False), ("T2", True)):
        r = simulate(recent, None, use_bb=bb)
        diag[(test, "Oct 2025-Sep 2026 (seen)")] = summarize(r[r.entry_time >= pd.Timestamp("2025-10-01", tz="UTC")], 1.0)
    evening = pd.concat([simulate(recent, None, use_bb=bb).assign(test=name) for name, bb in (("T1", False), ("T2", True))])
    ny = evening.entry_time.dt.tz_convert("America/New_York")
    evening = evening[(ny >= pd.Timestamp("2026-09-27 18:00", tz="America/New_York")) & (ny < pd.Timestamp("2026-09-27 22:00", tz="America/New_York"))]
    evening = evening.assign(entry_ny=ny[evening.index].dt.strftime("%H:%M"))[["test", "entry_ny", "side", "entry", "stop", "target", "exit", "R", "net"]]
    out = [f"# H13 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in `H13-ema-ribbon-m1.md` "
           "(commit f50269a). Asia session, M1, net $/oz per trade.\n", "## Verdict (both samples: net > 0 with t >= 2)\n",
           md(pd.DataFrame({k: {"PASS": v} for k, v in verdict.items()}).T.rename_axis("test")),
           "\n## Tests\n", md(pd.DataFrame(table).T.rename_axis(["test", "sample"])),
           "\n## Diagnostics\n", md(pd.DataFrame(diag).T.rename_axis(["test", "sample"])),
           "\n## The post's evening, 2026-09-27 18:00-22:00 New York (illustration only)\n",
           md(evening.set_index("test")) if len(evening) else "No trades."]
    (ROOT / "research" / "H13-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
