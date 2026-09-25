"""H06: do volume-profile levels (prior-day POC, VAH, VAL) give gold an edge on M5/M15?

Implements research/H06-volume-profile.md as pre-registered (commit 41465d9).
  --check   print profile checks, counts and sample setups up to entry, no outcomes
  (default) run the study and write research/H06-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, Bars, clustered_t, control_means, evaluate, prior_bin, series_at  # noqa: E402
from xau.features import tf_atr, tf_bars  # noqa: E402
from xau.profile import daily_profiles  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

TIMEFRAMES = (5, 15)
HORIZONS = (30, 60, 120)
PRIMARY = 60
DECIDE_BARS = 3       # the push bar's close and the next 2
ACCEPT_ATR = 0.1
MAX_WAIT = 5          # minutes; a later reference bar means the market was closed
COST_FIXED = 0.11     # $/oz per round trip: commission 0.09 + slippage 0.02
NEAR_LEVEL_ATR = 0.5
ACCEPT_MINUTES = 60   # Part B: closes inside the value area for this long
LONDON = "Europe/London"
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
LEVEL_KINDS = (("value-area edge", ("vah", "val")), ("POC", ("poc",)))


def load():
    m1 = load_m1("2018-01-01")  # the loader keeps the holdout locked
    prof = daily_profiles(m1)
    day = trading_day(m1.index)
    lv = prof.reindex(day)
    d = dict(m1=m1, bars=Bars(m1), day=day.to_numpy(), sess=session(m1.index),
             hour=m1.index.tz_convert(NY).hour.to_numpy(), prof=prof,
             levels={k: lv[k].to_numpy() for k in ("poc", "vah", "val")})
    for tf in TIMEFRAMES:
        b = tf_bars(m1, tf)
        tday = trading_day(b.index)
        tlv = prof.reindex(tday)
        d[tf] = dict(bars=b, t=b.index.as_unit("ns").asi8, tc=(b.index + pd.Timedelta(minutes=tf)).as_unit("ns").asi8,
                     close=b.close.to_numpy(float), day=tday.to_numpy(), atr=tf_atr(m1, tf),
                     levels={k: tlv[k].to_numpy() for k in ("poc", "vah", "val")})
    return d


def reference(bars, decided):
    """First M1 bar opening at or after each decision time, within MAX_WAIT; else -1."""
    k = bars.next_bar(decided)
    ok = k < len(bars.t)
    k = np.clip(k, 0, len(bars.t) - 1)
    return np.where(ok & (bars.t[k] <= decided + MAX_WAIT * MIN), k, -1)


# ---- Part A: level reactions ------------------------------------------------

def part_a_events(d, tf):
    t = d[tf]
    b = t["bars"]
    high, low, close = b.high.to_numpy(float), b.low.to_numpy(float), t["close"]
    prev = np.r_[np.nan, close[:-1]]
    found = []
    for kind, names in LEVEL_KINDS:
        for name in names:
            level = t["levels"][name]
            with np.errstate(invalid="ignore"):
                up = (level > prev) & (high > level)
                down = (level < prev) & (low < level)
            for side, mask in ((1, up), (-1, down)):
                i = np.flatnonzero(mask)
                found.append(pd.DataFrame({"i": i, "kind": kind, "level": level[i], "side": side}))
    ev = pd.concat(found, ignore_index=True)
    ev["day"] = t["day"][ev.i]
    ev = ev.sort_values("i", kind="stable").drop_duplicates(["day", "kind", "level", "side"]).reset_index(drop=True)

    atr = series_at(t["atr"], t["t"][ev.i.to_numpy()])  # bars closed by the push bar's open
    paths, decided = [], []
    for i, level, side, a in zip(ev.i.to_numpy(), ev.level.to_numpy(), ev.side.to_numpy(), atr):
        path, when = "neither", 0
        for j in range(i, min(i + DECIDE_BARS, len(close))):
            if side * (close[j] - level) < 0:
                path, when = "reclaim", t["tc"][j]
                break
            if np.isfinite(a) and side * (close[j] - level) >= ACCEPT_ATR * a:
                path, when = "acceptance", t["tc"][j]
                break
        paths.append(path)
        decided.append(when)
    ev = ev.assign(atr=atr, path=paths, decided=np.array(decided, dtype=np.int64))
    ev["direction"] = np.where(ev.path == "reclaim", -ev.side, ev.side)
    ev["ref"] = np.where(ev.path != "neither", reference(d["bars"], ev.decided.to_numpy()), -1)
    return ev


# ---- Part B: the 80% rule ---------------------------------------------------

def part_b_events(d, tf):
    bars, t = d["bars"], d[tf]
    need = ACCEPT_MINUTES // tf
    rows, counts = [], {"days with levels": 0, "London open bar": 0, "opened outside value": 0, "accepted back inside": 0}
    for day, lv in d["prof"].iterrows():
        counts["days with levels"] += 1
        open_t = pd.Timestamp(day + pd.Timedelta(hours=8)).tz_localize(LONDON).tz_convert("UTC").value
        end_t = pd.Timestamp(day + pd.Timedelta(hours=12)).tz_localize(NY).tz_convert("UTC").value
        k0 = bars.next_bar(open_t)
        if k0 >= len(bars.t) or bars.t[k0] > open_t + MAX_WAIT * MIN:
            continue
        counts["London open bar"] += 1
        px = bars.open[k0]
        side = -1 if px > lv.vah else 1 if px < lv.val else 0
        if side == 0:
            continue
        counts["opened outside value"] += 1
        a0 = np.searchsorted(t["tc"], open_t, side="right")
        a1 = np.searchsorted(t["tc"], end_t, side="right")
        run, confirmed = 0, None
        for j in range(a0, a1):
            run = run + 1 if lv.val <= t["close"][j] <= lv.vah else 0
            if run == need:
                confirmed = t["tc"][j]
                break
        if confirmed is None:
            continue
        counts["accepted back inside"] += 1
        rows.append((day, side, confirmed, lv.vah, lv.val, px))
    ev = pd.DataFrame(rows, columns=["day", "direction", "decided", "vah", "val", "london_open"])
    ev["ref"] = reference(bars, ev.decided.to_numpy())
    ev["atr"] = series_at(t["atr"], bars.t[np.clip(ev.ref.to_numpy(), 0, None)])  # as of the reference open
    return ev, counts


def hit_rate(ev, d, tf):
    """Far edge touched (M1 high/low) before a timeframe close back outside on the entry side, by 17:00 NY."""
    bars, t = d["bars"], d[tf]
    out = []
    for e in ev.itertuples():
        r = bars.t[e.ref]
        stop_t = pd.Timestamp(e.day + pd.Timedelta(hours=17)).tz_localize(NY).tz_convert("UTC").value
        k1 = np.searchsorted(bars.t, stop_t, side="left")
        far, entry_edge = (e.val, e.vah) if e.direction < 0 else (e.vah, e.val)
        touched = (bars.low[e.ref:k1] <= far) if e.direction < 0 else (bars.high[e.ref:k1] >= far)
        t_hit = bars.tc[e.ref + np.argmax(touched)] if touched.any() else None
        a0, a1 = np.searchsorted(t["tc"], r, side="right"), np.searchsorted(t["tc"], stop_t, side="right")
        outside = -e.direction * (t["close"][a0:a1] - entry_edge) > 0
        t_stop = t["tc"][a0 + np.argmax(outside)] if outside.any() else None
        if t_hit is not None and (t_stop is None or t_hit <= t_stop):
            out.append("far edge first")
        elif t_stop is not None:
            out.append("closed back outside first")
        else:
            out.append("neither by 17:00 NY")
    return pd.Series(out, index=ev.index)


# ---- measurement, controls, excess ------------------------------------------

def measure(ev, d):
    bars = d["bars"]
    ev = ev[ev.ref >= 0].copy()
    k, dirn, a = ev.ref.to_numpy(), ev.direction.to_numpy(), ev.atr.to_numpy()
    r, p_ref = bars.t[k], bars.open[k]
    ev["time"] = pd.to_datetime(r, utc=True)
    ev["session"], ev["hour"] = d["sess"][k], d["hour"][k]
    ev["weekday"] = [WEEKDAYS[x] if x < 5 else "Sun" for x in pd.DatetimeIndex(ev.day).dayofweek]
    ev["prior"] = dirn * (p_ref - bars.price_at(r - 15 * MIN)) / a
    ev["cost"] = bars.spread[k] + COST_FIXED
    for h in HORIZONS:
        ev[f"move{h}"] = dirn * (bars.price_at(r + h * MIN) - p_ref)
        ev[f"atr{h}"] = ev[f"move{h}"] / a
        ev[f"net{h}"] = ev[f"move{h}"] - ev.cost
    mfe, mae = bars.excursions(k, dirn, minutes=120)
    ev["mfe"], ev["mae"] = mfe / a, mae / a
    ev["bin"] = prior_bin(ev.prior.to_numpy())
    keep = np.isfinite(ev.prior.to_numpy()) & np.isfinite(a) & (r + 120 * MIN <= bars.tc[-1])
    return ev[keep]


def controls(d, tf, exclude_levels):
    bars = d["bars"]
    atr = series_at(d[tf]["atr"], bars.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (bars.t + 120 * MIN <= bars.tc[-1])
    if exclude_levels:
        dist = np.fmin.reduce(np.vstack([np.abs(bars.open - d["levels"][x]) for x in ("poc", "vah", "val")]), axis=0)
        keep &= dist >= NEAR_LEVEL_ATR * atr
    return control_means(bars, atr, d["sess"], d["hour"], keep, HORIZONS)


def add_excess(ev, cm):
    key = pd.MultiIndex.from_arrays([ev.session, ev.hour, ev.bin])
    for h in HORIZONS:
        ev[f"exc{h}"] = ev[f"atr{h}"].to_numpy() - cm[h].reindex(key).to_numpy()
    return ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]


# ---- check mode ---------------------------------------------------------------

def check(d):
    prof = d["prof"]
    width = prof.vah - prof.val
    print(f"profiles: {len(prof)} days; value-area share min {prof.va_share.min():.3f}; "
          f"POC inside value area on all days: {bool(((prof.poc >= prof.val) & (prof.poc <= prof.vah)).all())}")
    print(f"value-area width median ${width.median():.2f}; sample:\n{prof.loc['2024-06-10':'2024-06-12'].round(2)}")
    bars = d["bars"]
    for tf in TIMEFRAMES:
        t = d[tf]
        ev = part_a_events(d, tf)
        print(f"\n== M{tf} Part A ==\n{pd.crosstab(ev.kind, ev.path, margins=True)}")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=tf).iterrows():
            i = int(e.i)
            print(f"{e.kind} level {e.level:.2f} side {e.side:+d} path {e.path} atr {e.atr:.2f} "
                  f"decided {pd.Timestamp(int(e.decided), tz='UTC'):%Y-%m-%d %H:%M} UTC, entry at M1 open {bars.open[int(e.ref)]:.2f}")
            for j in range(i - 1, min(i + DECIDE_BARS, len(t["close"]))):
                print(f"   M{tf} {pd.Timestamp(int(t['t'][j]), tz='UTC'):%H:%M} h {t['bars'].high.iloc[j]:.2f} "
                      f"l {t['bars'].low.iloc[j]:.2f} c {t['close'][j]:.2f}{' <push' if j == i else ''}")
        ev, counts = part_b_events(d, tf)
        print(f"== M{tf} Part B == {counts}, with a reference bar: {int((ev.ref >= 0).sum())}")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=tf).iterrows():
            print(f"  {e.day:%Y-%m-%d}: London open {e.london_open:.2f} vs value area {e.val:.2f}-{e.vah:.2f} -> "
                  f"{'short' if e.direction < 0 else 'long'}, accepted at {pd.Timestamp(int(e.decided), tz='UTC'):%H:%M} UTC")


# ---- main -----------------------------------------------------------------------

def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    tests, extra = {}, {}
    for tf in TIMEFRAMES:
        cm_a, _ = controls(d, tf, exclude_levels=True)
        cm_b, _ = controls(d, tf, exclude_levels=False)
        a = add_excess(measure(part_a_events(d, tf), d), cm_a)
        for (kind, path), g in a.groupby(["kind", "path"]):
            tests[("A", f"M{tf}", kind, path)] = (g, "session")
        ev, counts = part_b_events(d, tf)
        b = add_excess(measure(ev, d), cm_b)
        b["outcome"] = hit_rate(b, d, tf)
        tests[("B", f"M{tf}", "80% rule", "re-entry")] = (b, "weekday")
        extra[f"M{tf}"] = (a, b, counts)

    cells = pd.DataFrame({key: evaluate(g, HORIZONS, PRIMARY, split=split,
                                        groups=SESSIONS if split == "session" else WEEKDAYS)
                          for key, (g, split) in tests.items()}).T
    cells.index.names = ["part", "timeframe", "level", "path"]
    cols = ["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]
    out = [f"# H06 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars 2018-01-01 to "
           f"2025-09-30, as pre-registered in `H06-volume-profile.md` (commit 41465d9).\n",
           "## Verdict\n", md(cells[cols]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in 2024-Sep 2025. "
           "C3: positive excess in all three sub-periods. C4: t >= 2 without the best session (Part A) or weekday "
           "(Part B). C5: C2 holds without the top 1% of events.\n",
           "## Each test in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T)]
    for tf, (a, b, counts) in extra.items():
        out.append(f"\n## {tf}: Part B setup counts and hit rate (diagnostic)\n")
        out.append(md(pd.Series(counts).to_frame("days").rename_axis("")))
        out.append("")
        out.append(md(b.outcome.value_counts(normalize=True).mul(100).round(1).to_frame("% of trades").rename_axis("outcome")))
        out.append(f"\n## {tf}: Part A by session (diagnostic)\n")
        by = a.groupby(["kind", "path", "session"])
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
        out.append(f"\n## {tf}: excursions within 120 minutes, in ATR (diagnostic)\n")
        both = pd.concat([a.assign(test=a.kind + " / " + a.path), b.assign(test="80% rule")])
        by = both.groupby("test")
        out.append(md(pd.DataFrame({"MFE median": by.mfe.median(), "MAE median": by.mae.median(),
                                    "MFE p75": by.mfe.quantile(0.75), "MAE p75": by.mae.quantile(0.75)})))
    (ROOT / "research" / "H06-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[cols]))


if __name__ == "__main__":
    main()
