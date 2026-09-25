"""H02: does buying pullbacks in an M5 trend beat random timing?

Implements research/H02-trend-pullback.md as pre-registered (commit c1933a0).
  --check   print event counts and sample setups up to the entry bar, no outcomes
  (default) run the study and write research/H02-results.md
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
from xau.features import m5_atr, m5_bars  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

HORIZONS = (30, 60, 120)
PRIMARY = 60
TRIGGER_WINDOW = 15  # minutes after the touch bar closes
SLOPE_BARS = 6       # the 50-EMA must be beyond its value this many M5 bars ago
MAX_WAIT = 5         # minutes; a later reference bar means the market was closed
COST_FIXED = 0.11    # $/oz per round trip: commission 0.09 + slippage 0.02


def load():
    m1 = load_m1("2018-01-01")  # the loader keeps the holdout locked
    bars = Bars(m1)
    m5 = m5_bars(m1)
    ema20 = m5.close.ewm(span=20, adjust=False).mean()
    ema50 = m5.close.ewm(span=50, adjust=False).mean()
    up = (m5.close > ema50) & (ema20 > ema50) & (ema50 > ema50.shift(SLOPE_BARS))
    down = (m5.close < ema50) & (ema20 < ema50) & (ema50 < ema50.shift(SLOPE_BARS))
    m5_tc = (m5.index + pd.Timedelta(minutes=5)).as_unit("ns").asi8
    pos = np.searchsorted(m5_tc, bars.t, side="right") - 1  # last M5 bar closed by each M1 open
    have, pos = pos >= 0, np.clip(pos, 0, None)
    trend = np.where(have & up.to_numpy()[pos], 1, np.where(have & down.to_numpy()[pos], -1, 0))
    return dict(m1=m1, bars=bars, day=trading_day(m1.index).to_numpy(), sess=session(m1.index),
                hour=m1.index.tz_convert(NY).hour.to_numpy(), atr=m5_atr(m1), trend=trend,
                ema20=np.where(have, ema20.to_numpy()[pos], np.nan), m5=m5, ema50=ema50, m5_tc=m5_tc,
                # M5 closes on the wrong side of the 50-EMA for a long (+1) or short (-1)
                m5_against={1: (m5.close < ema50).to_numpy(), -1: (m5.close > ema50).to_numpy()})


def find_setups(d):
    """Touches of the 20-EMA in a trend, each followed by its trigger if any."""
    bars, trend, ema20 = d["bars"], d["trend"], d["ema20"]
    prev_high, prev_low = np.r_[np.nan, bars.high[:-1]], np.r_[np.nan, bars.low[:-1]]
    rows, counts = [], {}
    for s in (1, -1):
        with np.errstate(invalid="ignore"):
            touch = (trend == s) & (s * (ema20 - (bars.low if s == 1 else bars.high)) >= 0)
            rearm = s * (bars.close - ema20) > 0
            fired = s * (bars.close - (prev_high if s == 1 else prev_low)) > 0
        touches, rearms = np.flatnonzero(touch), np.flatnonzero(rearm)
        against = d["m5_against"][s]
        last, counted, triggered = -1, 0, 0
        for i in touches:
            if last >= 0:  # a new pullback needs a re-arming close after the last touch bar
                k = np.searchsorted(rearms, last, side="right")
                if k >= len(rearms) or rearms[k] >= i:
                    continue
            last, counted = i, counted + 1
            end = np.searchsorted(bars.tc, bars.tc[i] + TRIGGER_WINDOW * MIN, side="right")
            a0 = np.searchsorted(d["m5_tc"], bars.t[i], side="right")
            for j in range(i, end):
                a1 = np.searchsorted(d["m5_tc"], bars.tc[j], side="right")
                if against[a0:a1].any():
                    break
                if fired[j] and trend[j] == s:
                    rows.append((i, j, s))
                    triggered += 1
                    break
        counts[s] = {"touch bars": len(touches), "pullbacks": counted, "triggers": triggered}
    ev = pd.DataFrame(rows, columns=["touch", "trigger", "direction"]).sort_values("trigger", kind="stable")
    k = bars.next_bar(bars.tc[ev.trigger.to_numpy()])
    ok = k < len(bars.t)
    k = np.clip(k, 0, len(bars.t) - 1)
    ok &= bars.t[k] <= bars.tc[ev.trigger.to_numpy()] + MAX_WAIT * MIN
    ev["ref"] = np.where(ok, k, -1)
    return ev.reset_index(drop=True), pd.DataFrame(counts).T


def measure(ev, d):
    """Forward moves from the reference bar's open, signed by trade direction."""
    bars = d["bars"]
    ev = ev[ev.ref >= 0].copy()
    k, dirn = ev.ref.to_numpy(), ev.direction.to_numpy()
    r, p_ref = bars.t[k], bars.open[k]
    a = series_at(d["atr"], r)
    ev["atr"], ev["time"] = a, pd.to_datetime(r, utc=True)
    ev["day"] = d["day"][ev.trigger.to_numpy()]
    ev["session"], ev["hour"] = d["sess"][k], d["hour"][k]
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


def control_keep(d):
    bars = d["bars"]
    atr = series_at(d["atr"], bars.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (bars.t + 120 * MIN <= bars.tc[-1])
    return atr, keep


def trend_controls(d, atr, keep):
    """Diagnostic: moments in a trend, taken in the trend's direction, per cell."""
    bars, trend = d["bars"], d["trend"]
    prior = (bars.open - bars.price_at(bars.t - 15 * MIN)) / atr
    fwd = {h: (bars.price_at(bars.t + h * MIN) - bars.open) / atr for h in HORIZONS}
    ok = keep & (trend != 0) & np.isfinite(prior)
    for h in HORIZONS:
        ok &= np.isfinite(fwd[h])
    s = trend[ok]
    f = pd.DataFrame({"session": d["sess"][ok], "hour": d["hour"][ok], "bin": prior_bin(s * prior[ok])})
    for h in HORIZONS:
        f[h] = s * fwd[h][ok]
    return f.groupby(["session", "hour", "bin"])[list(HORIZONS)].mean(), int(ok.sum())


def add_excess(ev, cm, prefix):
    key = pd.MultiIndex.from_arrays([ev.session, ev.hour, ev.bin])
    for h in HORIZONS:
        ev[f"{prefix}{h}"] = ev[f"atr{h}"].to_numpy() - cm[h].reindex(key).to_numpy()
    return ev


def check(d):
    ev, counts = find_setups(d)
    print(counts, "\nevents with a reference bar:", int((ev.ref >= 0).sum()))
    bars, m5, ema50 = d["bars"], d["m5"], d["ema50"]
    for s in (1, -1):
        for _, e in ev[(ev.direction == s) & (ev.ref >= 0)].sample(3, random_state=7 + s).iterrows():
            i, j, k = int(e.touch), int(e.trigger), int(e.ref)
            print(f"\n{'long' if s == 1 else 'short'}: touch {pd.Timestamp(bars.t[i], tz='UTC')}, "
                  f"trigger {pd.Timestamp(bars.t[j], tz='UTC')}, ref {pd.Timestamp(bars.t[k], tz='UTC')}")
            for n in range(i - 2, j + 1):
                mark = " ".join(x for x, y in (("<touch", i), ("<trigger", j)) if n == y)
                print(f"  {pd.Timestamp(bars.t[n], tz='UTC'):%m-%d %H:%M} o {bars.open[n]:.2f} h {bars.high[n]:.2f} "
                      f"l {bars.low[n]:.2f} c {bars.close[n]:.2f} ema20 {d['ema20'][n]:.2f} trend {d['trend'][n]:+d} {mark}")
            print(f"  {pd.Timestamp(bars.t[k], tz='UTC'):%m-%d %H:%M} o {bars.open[k]:.2f} <ref (entry at this open)")
            lo, hi = pd.Timestamp(bars.t[i], tz="UTC"), pd.Timestamp(bars.tc[j], tz="UTC")
            m5_close_times = m5.index + pd.Timedelta(minutes=5)
            sel = (m5_close_times > lo) & (m5_close_times <= hi)
            for t5, c5, e5 in zip(m5_close_times[sel], m5.close[sel], ema50[sel]):
                print(f"  M5 close {t5:%H:%M}: {c5:.2f} vs 50-EMA {e5:.2f}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    setups, counts = find_setups(d)
    ev = measure(setups, d)
    atr, keep = control_keep(d)
    cm, n_controls = control_means(d["bars"], atr, d["sess"], d["hour"], keep, HORIZONS)
    tcm, n_trend = trend_controls(d, atr, keep)
    ev = add_excess(ev, cm, "exc")
    ev = add_excess(ev, tcm, "trendexc")
    ev = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
    verdict = pd.DataFrame({"all": evaluate(ev, HORIZONS, PRIMARY)}).T

    out = [f"# H02 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars "
           f"2018-01-01 to 2025-09-30, as pre-registered in `H02-trend-pullback.md` (commit c1933a0).\n",
           "## Verdict\n", md(verdict[["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in "
           "2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Setups\n", md(counts.rename(index={1: "long", -1: "short"})),
           f"\nEvents measured: {len(ev):,}. Controls: {n_controls:,} M1 moments, each used long and short; "
           f"in-trend controls: {n_trend:,}.\n",
           "## The test in full\n", md(verdict.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T)]
    out.append("\n## Against random in-trend moments (diagnostic)\n")
    out.append(md(pd.DataFrame({h: {"excess (ATR)": ev[f"trendexc{h}"].mean(),
                                    "t": clustered_t(ev[f"trendexc{h}"].dropna(), ev.loc[ev[f"trendexc{h}"].notna(), "day"])}
                                for h in HORIZONS}).T.rename_axis("minutes")))
    for name, col in (("session", "session"), ("side", "direction")):
        by = ev.groupby(col)
        out.append(f"\n## By {name} (diagnostic)\n")
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    out.append("\n## Excursions within 120 minutes, in ATR (diagnostic)\n")
    out.append(md(pd.DataFrame({"median": [ev.mfe.median(), ev.mae.median()], "p75": [ev.mfe.quantile(0.75), ev.mae.quantile(0.75)]},
                               index=pd.Index(["favourable", "adverse"], name="excursion"))))
    (ROOT / "research" / "H02-results.md").write_text("\n".join(out) + "\n")
    print(md(verdict[["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]]))


if __name__ == "__main__":
    main()
