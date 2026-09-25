"""H11 cost check: real spreads at the 08:30 New York release minute, from recorded ticks.

Uses spreads only (ask - bid), which the holdout rules allow for the cost
model; no price moves are looked at. Compares tick spreads at the release
minute and at the strategy's entry moment (08:31:00-08:31:10) with a calm
baseline (10:31) and with the M1 bar's recorded `spread` field, which the
cost model uses. Writes research/H11-news-costs.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.report import md  # noqa: E402
from xau.ticks import load_ticks  # noqa: E402

NY = "America/New_York"


def at(day, hhmmss):
    return pd.Timestamp(f"{day:%Y-%m-%d} {hhmmss}").tz_localize(NY).tz_convert("UTC")


def main():
    first, last = pd.Timestamp("2026-08-31"), pd.Timestamp("2026-09-24")
    days = pd.bdate_range(first, last)
    ticks = load_ticks(at(first, "08:00:00"), at(last, "11:00:00"), allow_holdout=True)
    spread = (ticks.ask - ticks.bid)
    bar_spread = load_m1(at(first, "08:00:00"), at(last, "11:00:00"), allow_holdout=True)["spread"] * 0.01
    rows = {}
    for day in days:
        win = lambda a, b: spread[(spread.index >= at(day, a)) & (spread.index < at(day, b))]  # noqa: E731
        release, entry, calm = win("08:30:00", "08:31:00"), win("08:31:00", "08:31:10"), win("10:31:00", "10:31:10")
        if release.empty:
            continue
        bar = bar_spread.get(at(day, "08:31:00"), np.nan)
        rows[f"{day:%a %m-%d}"] = {"release min: median": release.median(), "release min: max": release.max(),
                                   "entry 08:31:00-10s: first tick": entry.iloc[0] if len(entry) else np.nan,
                                   "entry: median": entry.median(), "entry: max": entry.max(),
                                   "calm 10:31: median": calm.median(), "M1 bar spread field (08:31)": bar}
    table = pd.DataFrame(rows).T
    summary = table.agg(["median", "mean", "max"])
    out = [f"# H11 cost check: spreads at the 08:30 New York release\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC "
           f"on recorded Pepperstone-Demo ticks, {first:%Y-%m-%d} to {last:%Y-%m-%d}. $/oz, ask minus bid.\n",
           md(table.rename_axis("day")), "\n## Summary\n", md(summary.rename_axis(""))]
    (ROOT / "research" / "H11-news-costs.md").write_text("\n".join(out) + "\n")
    print(md(table.rename_axis("day")))
    print(md(summary.rename_axis("")))


if __name__ == "__main__":
    main()
