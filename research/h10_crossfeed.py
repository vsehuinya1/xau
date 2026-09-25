"""H10 diagnostic: the same dollar-shock definition on histdata and on Pepperstone, 2018-2024.

If histdata shows a much larger effect than Pepperstone over the same years,
histdata inflates it (for example a stale gold feed) and H10's 2009-2017
magnitude should be discounted. This is a data comparison, not a new test.
Writes research/H10-crossfeed.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import h10_dollar_shock_oos as h10  # noqa: E402
from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, Bars, add_excess, clustered_t, control_means, measure, series_at  # noqa: E402
from xau.features import m5_atr  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

START, END = "2018-01-01", "2025-01-01"


def build(gold, eur, jpy):
    z = pd.concat({"EURUSD": h10.z_scores(eur), "USDJPY": h10.z_scores(jpy)}, axis=1, join="inner").dropna()
    return dict(gold=gold, bars=Bars(gold), day=trading_day(gold.index).to_numpy(), sess=session(gold.index),
                hour=gold.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(gold), z=z)


def run(d):
    gold = d["bars"]
    atr = series_at(d["atr"], gold.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (gold.t + 30 * MIN <= gold.tc[-1])
    cm, _ = control_means(gold, atr, d["sess"], d["hour"], keep, h10.HORIZONS)
    rows = {}
    for k in h10.LEVELS:
        ev, _ = h10.shocks(d, k)
        g_move = gold.price_at(ev.decided.to_numpy()) - gold.price_at(ev.decided.to_numpy() - 5 * MIN)
        followed = ev.direction * g_move / series_at(d["atr"], ev.decided.to_numpy()) >= 1
        ev = add_excess(measure(ev, gold, d["atr"], d["sess"], d["hour"], d["day"], h10.HORIZONS, 30), cm, h10.HORIZONS)
        row = {"events": len(ev), "gold already followed": followed.mean(), "gold M5 ATR median $": ev.atr.median()}
        for h in h10.HORIZONS:
            row[f"excess {h}m (ATR)"] = ev[f"exc{h}"].mean()
            row[f"move {h}m $"] = ev[f"move{h}"].mean()
            row[f"t {h}m"] = clustered_t(ev[f"exc{h}"], ev.day)
        rows[f"k={k:g}"] = row
    return rows


def main():
    years = range(2018, 2025)
    hist = build(load_histdata("xauusd", years), load_histdata("eurusd", years), load_histdata("usdjpy", years))
    pep = build(*(load_m1(START, END, symbol=s) for s in ("XAUUSD", "EURUSD", "USDJPY")))
    res = {("histdata", k): v for k, v in run(hist).items()}
    res.update({("Pepperstone", k): v for k, v in run(pep).items()})
    table = pd.DataFrame(res)
    out = [f"# H10 diagnostic: histdata vs Pepperstone, 2018-2024\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
           "The H10 definition (EURUSD and USDJPY both >= k ATR in 5 minutes, gold against the dollar) on both feeds "
           "over the same years.\n", md(table.rename_axis(""))]
    (ROOT / "research" / "H10-crossfeed.md").write_text("\n".join(out) + "\n")
    print(md(table.rename_axis("")))


if __name__ == "__main__":
    main()
