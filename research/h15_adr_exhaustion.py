"""H15: average-daily-range exhaustion, faded, with a dollar-shock filter for gold.

Implements research/H15-adr-exhaustion.md as pre-registered (commit 2a70adf).
Writes research/H15-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import gold_direction, z_scores  # noqa: E402
from xau.eventstudy import MIN, clustered_t  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, trading_day  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

ADR_DAYS = 14
STOP_ADR, TARGET_ADR = 0.25, 0.50
LAST_ENTRY_NY, CLOSE_NY = 16, 17
SHOCK_K, SHOCK_LOOKBACK = 2.0, 60
MAX_WAIT = 5
FLAT_COST = 0.51


def shock_times(eur, jpy):
    z = pd.concat({"E": z_scores(eur), "J": z_scores(jpy)}, axis=1, join="inner").dropna()
    return np.sort(z.index[gold_direction(z.E, z.J, SHOCK_K) != 0].to_numpy())


def simulate(gold, flat_cost, shocks=None):
    day = trading_day(gold.index)
    by_day = gold.groupby(day)
    adr = (by_day.high.max() - by_day.low.min()).rolling(ADR_DAYS).mean().shift(1)
    adr_bar = adr.reindex(day).to_numpy()
    run_hi = by_day.high.cummax().to_numpy()
    run_lo = by_day.low.cummin().to_numpy()
    t = gold.index.as_unit("ns").asi8
    o, h, l, c = (gold[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    spread = gold["spread"].to_numpy(float) * 0.01
    ny = gold.index.tz_convert(NY)
    m5_end = (ny.minute % 5 == 4)
    days = day.to_numpy()
    rows, busy_until, done = [], -1, set()
    for i in np.flatnonzero(m5_end & np.isfinite(adr_bar)):
        side = -1 if c[i] >= run_lo[i] + adr_bar[i] else 1 if c[i] <= run_hi[i] - adr_bar[i] else 0
        if side == 0 or (days[i], side) in done:
            continue
        trig = t[i] + MIN  # the M5 close
        k = i + 1
        if k >= len(t) or t[k] > trig + MAX_WAIT * MIN or k <= busy_until:
            continue
        if ny[k].hour >= LAST_ENTRY_NY and ny[k].hour < 18:
            continue
        done.add((days[i], side))
        if shocks is not None:
            j = np.searchsorted(shocks, trig, side="right")
            if j > 0 and shocks[j - 1] > trig - SHOCK_LOOKBACK * MIN:
                continue
        end_t = pd.Timestamp(days[i]).tz_localize(NY) + pd.Timedelta(hours=CLOSE_NY)
        end = int(np.searchsorted(t, end_t.value, side="left"))  # bars before 17:00 NY
        if end <= k + 1:
            continue
        entry, a = o[k], adr_bar[i]
        stop, target = entry - side * STOP_ADR * a, entry + side * TARGET_ADR * a
        hh, ll, oo = h[k:end], l[k:end], o[k:end]
        hit_stop = (ll <= stop) if side > 0 else (hh >= stop)
        hit_tgt = (hh >= target) if side > 0 else (ll <= target)
        n = len(hh)
        js = int(np.argmax(hit_stop)) if hit_stop.any() else n
        jt = int(np.argmax(hit_tgt)) if hit_tgt.any() else n
        if js <= jt and js < n:
            j, exit_ = js, (oo[js] if side * (oo[js] - stop) < 0 else stop)
        elif jt < n:
            j, exit_ = jt, (oo[jt] if side * (oo[jt] - target) > 0 else target)
        else:
            j, exit_ = n - 1, c[end - 1]
        cost = flat_cost if flat_cost is not None else spread[k] + 0.11
        rows.append((pd.Timestamp(t[k], tz="UTC"), days[i], side, entry, exit_, a, side * (exit_ - entry) - cost, cost))
        busy_until = k + j
    return pd.DataFrame(rows, columns=["entry_time", "day", "side", "entry", "exit", "adr", "net", "cost"])


def summarize(f, years):
    wins, losses = f.net[f.net > 0].sum(), -f.net[f.net < 0].sum()
    return {"trades": len(f), "trades/yr": len(f) / years, "mean net $/oz": f.net.mean(), "t (by day)": clustered_t(f.net, f.day),
            "win rate %": (f.net > 0).mean() * 100, "profit factor": wins / losses if losses else np.nan,
            "mean net in ADR units": (f.net / f.adr).mean(), "total net $/oz": f.net.sum(),
            "max drawdown $/oz": max_drawdown(f.net), "mean cost $/oz": f.cost.mean(), "short share %": (f.side < 0).mean() * 100}


def main():
    yrs_h, yrs_p = range(2009, 2018), 7.75
    hist = (load_histdata("xauusd", yrs_h), load_histdata("eurusd", yrs_h), load_histdata("usdjpy", yrs_h))
    pep = tuple(load_m1("2018-01-01", symbol=s) for s in ("XAUUSD", "EURUSD", "USDJPY"))
    samples = {"histdata 2009-2017": (hist, FLAT_COST, 9.0), "Pepperstone 2018-Sep 2025": (pep, None, yrs_p)}
    table, verdict = {}, {}
    for test, use_filter in (("T1 ADR exhaustion", False), ("T2 + dollar-shock filter", True)):
        for name, ((g, e, j), cost, yrs) in samples.items():
            table[(test, name)] = summarize(simulate(g, cost, shock_times(e, j) if use_filter else None), yrs)
        verdict[test] = all(table[(test, n)]["mean net $/oz"] > 0 and table[(test, n)]["t (by day)"] >= 2 for n in samples)
    rec = tuple(load_m1("2025-08-01", None, symbol=s, allow_holdout=True) for s in ("XAUUSD", "EURUSD", "USDJPY"))
    for test, use_filter in (("T1 ADR exhaustion", False), ("T2 + dollar-shock filter", True)):
        r = simulate(rec[0], None, shock_times(rec[1], rec[2]) if use_filter else None)
        table[(test, "Oct 2025-Sep 2026 (diagnostic)")] = summarize(r[r.entry_time >= pd.Timestamp("2025-10-01", tz="UTC")], 1.0)
    out = [f"# H15 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in "
           "`H15-adr-exhaustion.md` (commit 2a70adf). Net $/oz per trade.\n", "## Verdict (both samples: net > 0 with t >= 2)\n",
           md(pd.DataFrame({k: {"PASS": v} for k, v in verdict.items()}).T.rename_axis("test")),
           "\n## Results\n", md(pd.DataFrame(table).T.rename_axis(["test", "sample"]))]
    (ROOT / "research" / "H15-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
