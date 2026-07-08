#!/usr/bin/env python3
"""
verify_d09.py - Independent Verification of D09: Asian Range as Day Direction Predictor
========================================================================================

Reimplements D09 entirely from the written specification.
No code from research/ is imported or used.

Published findings to verify (2018-01-01 to 2025-12-31, 2,063 qualifying days):
  A | Asian close pos > 0.6 | 52.9% bullish  -> 68.6% bullish  | +15.6 pp | d=+0.59 | n=916
  B | Asian close pos < 0.4 | 52.9% bullish  -> 34.1% bullish  | -18.8 pp | d=-0.62 | n=750
  C | Asian range < 25th pct| 68.7% expansive-> 93.9% expansive| +25.2 pp | d=+0.61 | n=541

TIMEZONE FINDING (critical):
  histdata.com XAUUSD M1 timestamps are in Eastern Time (ET = EST/EDT), NOT UTC.
  Proof: every weekday has a ~61-min gap at 17:00->18:01 in the file
         (NY CME Gold session close/reopen).  The original loader applies
         `pd.to_datetime(..., utc=True)`, which MISLABELS ET timestamps as UTC.
         This introduces a 5h (winter) / 4h (summer) offset in all session windows.

  Consequence for D09:
    Original "Asian" = file 00:00-07:00 ET = REAL 05:00-12:00 UTC (winter)
                     = the London MORNING session in real UTC.
    Spec "Asian"     = real 00:00-07:00 UTC.

This script runs TWO modes:
  spec : parse ET -> convert to UTC correctly; simple day range; >=60/>=20 filter
  orig : treat ET timestamps as UTC (replicating original loader); ATR true range;
         NaN-only filter (matching original D09 dropna)
"""
from __future__ import annotations
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).parent / "data"

PUBLISHED = {
    "A":      dict(pp=+15.6, d=+0.59, n=916,  base_pct=52.9, obs_pct=68.6),
    "B":      dict(pp=-18.8, d=-0.62, n=750,  base_pct=52.9, obs_pct=34.1),
    "C":      dict(pp=+25.2, d=+0.61, n=541,  base_pct=68.7, obs_pct=93.9),
    "n_days": 2063,
}

# =============================================================================
# 1. DATA LOADING
# =============================================================================

def load_year(year: int, tz_mode: str) -> pd.DataFrame:
    """
    Load one year of M1 OHLCV from histdata.com CSV.
    Format: YYYYMMDD HHMMSS;open;high;low;close;volume  (no header, semicolon sep)

    tz_mode='spec': parse as US/Eastern with DST -> convert to UTC (correct)
    tz_mode='orig': label ET timestamps as UTC (replicates original loader bug)
    """
    path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
    df = pd.read_csv(
        path, sep=";", header=None,
        names=["dt", "open", "high", "low", "close", "volume"],
        dtype={"open": "float64", "high": "float64", "low": "float64",
               "close": "float64", "volume": "float64"},
    )
    if tz_mode == "spec":
        naive = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S")
        et    = naive.dt.tz_localize("US/Eastern", ambiguous="NaT", nonexistent="NaT")
        df["dt"] = et.dt.tz_convert("UTC").dt.tz_localize(None)
    else:
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S")

    df = df.dropna(subset=["dt"]).set_index("dt").sort_index()
    return df[~df.index.duplicated(keep="first")]


def load_data(start: int, end: int, tz_mode: str) -> pd.DataFrame:
    print(f"    Loading {start}-{end} [{tz_mode}]: ", end="", flush=True)
    frames = [load_year(yr, tz_mode) for yr in range(start, end + 1)
              if print(f"{yr}", end=" ", flush=True) or True]
    print()
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    print(f"    Total M1 bars: {len(df):,}")
    return df


# =============================================================================
# 2. DAILY FEATURE COMPUTATION
# =============================================================================

def _rolling_pct_rank(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling percentile rank matching original research/data/daily.py:
        rank = #{prior window values <= current} / #{prior values} * 100
    Original lambda: float(np.sum(x[:-1] <= x[-1])) / max(len(x)-1,1) * 100.0
    """
    def _rank(x):
        if len(x) < 2:
            return np.nan
        return float(np.sum(x[:-1] <= x[-1])) / max(len(x) - 1, 1) * 100.0
    return series.rolling(window=window, min_periods=5).apply(_rank, raw=True)


def compute_daily(m1: pd.DataFrame, tz_mode: str) -> pd.DataFrame:
    """
    Build per-day features. All session/day definitions follow the mode.

    SPEC: day = UTC calendar date; Asian = UTC hours 0-6; range = H-L
    ORIG: day = file-ts date (ET date); Asian = file hours 0-6 (ET 0-7am);
          range = ATR-style max(H-L, |H-prevC|, |L-prevC|)
    """
    idx  = m1.index
    hour = np.asarray(idx.hour, dtype=np.int32)
    date = idx.normalize().values  # datetime64[ns]

    flat = pd.DataFrame({
        "date":  date,
        "hour":  hour,
        "open":  m1["open"].values,
        "high":  m1["high"].values,
        "low":   m1["low"].values,
        "close": m1["close"].values,
    })

    # Full-day OHLC
    gd = flat.groupby("date", sort=True)
    daily = pd.DataFrame({
        "date":   gd["date"].first(),
        "open":   gd["open"].first(),
        "high":   gd["high"].max(),
        "low":    gd["low"].min(),
        "close":  gd["close"].last(),
        "n_bars": gd["open"].count(),
    }).reset_index(drop=True)

    daily["day_bull"] = (daily["close"] > daily["open"]).astype(np.int8)

    if tz_mode == "orig":
        # ATR-style true range (matching original daily.py)
        pc = daily["close"].shift(1)
        daily["day_range"] = np.maximum(
            daily["high"] - daily["low"],
            np.maximum((daily["high"] - pc).abs(), (daily["low"] - pc).abs()),
        )
    else:
        # Spec: day_true_range = day_high - day_low
        daily["day_range"] = daily["high"] - daily["low"]

    # Asian session: UTC hours 0-6 (spec) or file hours 0-6 (orig)
    af = flat[flat["hour"] < 7]
    ga = af.groupby("date", sort=True)
    asian = pd.DataFrame({
        "date":        ga["date"].first(),
        "asian_high":  ga["high"].max(),
        "asian_low":   ga["low"].min(),
        "asian_close": ga["close"].last(),
        "n_asian":     ga["open"].count(),
    }).reset_index(drop=True)

    asian["asian_range"] = asian["asian_high"] - asian["asian_low"]
    rng = asian["asian_range"].replace(0.0, np.nan)
    asian["asian_close_pos"] = (
        (asian["asian_close"] - asian["asian_low"]) / rng
    ).clip(0.0, 1.0)
    asian["asian_range_pct"] = _rolling_pct_rank(asian["asian_range"], window=20)

    result = daily.merge(asian, on="date", how="left")
    result["london_expansive"] = (
        result["day_range"] > result["asian_range"] * 1.5
    ).astype(np.int8)
    return result.reset_index(drop=True)


# =============================================================================
# 3. QUALIFYING DAY FILTER
# =============================================================================

def qualify(df: pd.DataFrame, tz_mode: str) -> pd.DataFrame:
    """
    SPEC: >=60 total M1 bars AND >=20 Asian M1 bars
    ORIG: drop NaN asian_close_pos or asian_range only (matches original D09 dropna)
    Both: drop NaN asian_range_pct (rolling warm-up)
    """
    if tz_mode == "spec":
        mask = (df["n_bars"].fillna(0) >= 60) & (df["n_asian"].fillna(0) >= 20)
        df = df[mask]
    df = df.dropna(subset=["asian_close_pos", "asian_range", "asian_range_pct"])
    return df.copy().reset_index(drop=True)


# =============================================================================
# 4. STATISTICS
# =============================================================================

def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled Cohen's d (matches research/utils.py)."""
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    b = np.asarray(b, float); b = b[~np.isnan(b)]
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    sp = np.sqrt(((na-1)*np.var(a, ddof=1) + (nb-1)*np.var(b, ddof=1)) / (na+nb-2))
    return float((np.mean(a) - np.mean(b)) / (sp + 1e-12))


def perm_p(a: np.ndarray, b: np.ndarray, n_perm: int = 10_000, seed: int = 42) -> float:
    """
    Two-sided label-shuffle permutation test.
    Uses np.random.default_rng (matches research/utils.py).
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    b = np.asarray(b, float); b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    combined = np.concatenate([a, b])
    n_a  = len(a)
    Tobs = np.mean(a) - np.mean(b)
    null = np.empty(n_perm)
    for i in range(n_perm):
        p = rng.permutation(combined)
        null[i] = np.mean(p[:n_a]) - np.mean(p[n_a:])
    return float(np.mean(np.abs(null) >= abs(Tobs)))


# =============================================================================
# 5. D09 ANALYSIS
# =============================================================================

def run_d09(df: pd.DataFrame) -> dict:
    n = len(df)
    if n < 50:
        return {}

    base_bull = float(df["day_bull"].mean())
    base_exp  = float(df["london_expansive"].mean())

    # Finding A: close_pos > 0.6 -> bullish
    ga  = df[df["asian_close_pos"] > 0.6]
    oa  = df[df["asian_close_pos"] <= 0.6]
    ra  = float(ga["day_bull"].mean()) if len(ga) > 0 else np.nan
    A = dict(n=len(ga), obs=ra, base=base_bull, pp=(ra-base_bull)*100,
             d=cohen_d(ga["day_bull"].values, oa["day_bull"].values),
             p_perm=perm_p(ga["day_bull"].values, oa["day_bull"].values))

    # Finding B: close_pos < 0.4 -> bearish
    gb  = df[df["asian_close_pos"] < 0.4]
    ob  = df[df["asian_close_pos"] >= 0.4]
    rb  = float(gb["day_bull"].mean()) if len(gb) > 0 else np.nan
    B = dict(n=len(gb), obs=rb, base=base_bull, pp=(rb-base_bull)*100,
             d=cohen_d(gb["day_bull"].values, ob["day_bull"].values),
             p_perm=perm_p(gb["day_bull"].values, ob["day_bull"].values))

    # Finding C: asian_range < 25th pct -> london expansive
    # Original code baseline = rate_w (wide days), not overall rate.
    gc  = df[df["asian_range_pct"] < 25.0]
    oc  = df[df["asian_range_pct"] >= 25.0]
    rc  = float(gc["london_expansive"].mean()) if len(gc) > 0 else np.nan
    rw  = float(oc["london_expansive"].mean()) if len(oc) > 0 else np.nan
    ok_c = len(gc) >= 20 and len(oc) >= 20
    C = dict(n=len(gc), obs=rc, base=rw, base_all=base_exp,
             pp=(rc-rw)*100 if not (np.isnan(rc) or np.isnan(rw)) else np.nan,
             pp_vs_all=(rc-base_exp)*100 if not np.isnan(rc) else np.nan,
             d=cohen_d(gc["london_expansive"].values, oc["london_expansive"].values) if ok_c else np.nan,
             p_perm=perm_p(gc["london_expansive"].values, oc["london_expansive"].values) if ok_c else np.nan)

    return dict(n=n, base_bull=base_bull, base_exp=base_exp, A=A, B=B, C=C)


# =============================================================================
# 6. REPORTING
# =============================================================================

def status(delta: float) -> str:
    if abs(delta) <= 1.0:
        return "VERIFIED"
    if abs(delta) <= 2.0:
        return "CLOSE   "
    return "FALSIFIED"


def print_block(res: dict, period: str, mode: str) -> None:
    if not res:
        print("  (no data)")
        return
    print(f"\n  Period: {period} | Mode: {mode}")
    print(f"  Qualifying days : {res['n']:,}  (published: {PUBLISHED['n_days']:,})")
    print(f"  Baseline bull   : {res['base_bull']:.1%}  (published: 52.9%)")
    print(f"  Baseline exp    : {res['base_exp']:.1%}")
    print()
    print(f"  {'Find':<5} {'Pub pp':>8} {'My pp':>8} {'Delta':>7} {'Pub n':>7} {'My n':>7} {'d':>7} {'p_perm':>9}  Status")
    print(f"  {'-'*75}")
    for k in ("A", "B", "C"):
        r   = res[k]
        pub = PUBLISHED[k]
        pp  = r["pp"]
        d   = r["pp"] - pub["pp"]
        ds  = f"{r['d']:+.2f}" if not np.isnan(r['d']) else "  n/a"
        ps  = f"{r['p_perm']:.4f}" if not np.isnan(r.get('p_perm', np.nan)) else "   n/a"
        print(f"  {k:<5} {pub['pp']:>+8.1f} {pp:>+8.1f} {d:>+7.1f} {pub['n']:>7,} {r['n']:>7,} {ds:>7} {ps:>9}  {status(d)}")
        if k == "C":
            print(f"        [C baseline: wide={r['base']:.1%} | all-days={r['base_all']:.1%}"
                  f" | effect vs all={r['pp_vs_all']:+.1f}pp]")
    print()


def print_stability(r1: dict, r2: dict, mode: str) -> None:
    print(f"  Stability [{mode}]:")
    print(f"  {'Find':<6}  2018-2021    2022-2025   Stable?")
    print(f"  {'-'*48}")
    for k in ("A", "B", "C"):
        pa = r1.get(k, {}).get("pp", np.nan)
        pb = r2.get(k, {}).get("pp", np.nan)
        if np.isnan(pa) or np.isnan(pb):
            print(f"  {k:<6}  n/a")
            continue
        ok = np.sign(pa) == np.sign(pb) and min(abs(pa), abs(pb)) > 5.0
        print(f"  {k:<6}  {pa:>+8.1f} pp   {pb:>+8.1f} pp   {'STABLE' if ok else 'UNSTABLE'}")
    print()


# =============================================================================
# 7. MAIN
# =============================================================================

def run_mode(tz_mode: str) -> dict:
    mode_lbl = ("SPEC-CORRECT [ET->UTC, H-L range, >=60/>=20 bars]"
                if tz_mode == "spec" else
                "AS-IMPLEMENTED [ET as UTC, ATR range, NaN-only filter]")

    print(f"\n{'='*78}")
    print(f"  MODE: {mode_lbl}")
    print(f"{'='*78}")

    print("\n  [2018-2025]")
    m1f   = load_data(2018, 2025, tz_mode)
    dff   = qualify(compute_daily(m1f, tz_mode), tz_mode)
    resf  = run_d09(dff)
    print_block(resf, "2018-2025", mode_lbl)

    print("\n  [2018-2021] stability check")
    m1a   = load_data(2018, 2021, tz_mode)
    dfa   = qualify(compute_daily(m1a, tz_mode), tz_mode)
    resa  = run_d09(dfa)
    print_block(resa, "2018-2021", mode_lbl)

    print("\n  [2022-2025] stability check")
    m1b   = load_data(2022, 2025, tz_mode)
    dfb   = qualify(compute_daily(m1b, tz_mode), tz_mode)
    resb  = run_d09(dfb)
    print_block(resb, "2022-2025", mode_lbl)

    print_stability(resa, resb, mode_lbl)
    return resf


def main() -> None:
    print("\n" + "="*78)
    print("  D09 ASIAN RANGE PREDICTOR -- INDEPENDENT VERIFICATION")
    print("  XAUUSD M1 2018-2025  |  10,000 permutations  |  seed=42")
    print("="*78)

    print("""
  TIMEZONE NOTE
  =============
  histdata.com XAUUSD timestamps are in Eastern Time (ET), NOT UTC.
  Evidence from DAT_ASCII_XAUUSD_M1_2018.txt:
    "Gap of 3654s between 20180102170000 and 20180102180100"
    This 61-min gap repeats every weekday at 17:00->18:01 in file time
    = NY CME Gold session close (5pm ET) and reopen (6pm ET).
  The original smc/loader.py uses `pd.to_datetime(..., utc=True)`,
  mislabeling ET timestamps as UTC.
  Impact (winter EST = UTC-5):
    Original "Asian"   = file 00:00-07:00 = REAL 05:00-12:00 UTC (London morning)
    Spec Asian session = REAL 00:00-07:00 UTC = file 19:00-02:00 (previous ET day)
""")

    results = {}
    results["orig"] = run_mode("orig")
    results["spec"] = run_mode("spec")

    # Final deliverable table
    print("\n" + "="*78)
    print("  FINAL COMPARISON TABLE")
    print("="*78)
    print(f"  {'Finding':<8} {'Published':>10} {'Result':>10} {'Delta':>8}  Status")
    print(f"  {'-'*55}")
    for mode_key, mlbl in [("orig", "AS-IMPLEMENTED"), ("spec", "SPEC-CORRECT")]:
        res = results.get(mode_key, {})
        print(f"\n  -- {mlbl} (n={res.get('n','?'):,}) --")
        for k in ("A", "B", "C"):
            r   = res.get(k, {})
            pub = PUBLISHED[k]
            pp  = r.get("pp", np.nan)
            d   = pp - pub["pp"]
            pp_s = f"{pp:>+8.1f} pp" if not np.isnan(pp) else "        n/a"
            print(f"  {k:<8} {pub['pp']:>+8.1f} pp {pp_s}  {d:>+7.1f} pp  {status(d)}")

    print("""
  DISCREPANCY SOURCES (in order of impact if results differ):
    1. Timezone: ET timestamps mislabeled as UTC -> 5h/4h session shift  [PRIMARY]
    2. Day boundary: ET midnight vs UTC midnight
    3. True range: ATR-style (original) vs simple H-L (spec)
    4. Qualifying filter: >=60/>=20 bars (spec) vs NaN-only (original)
    5. Finding C baseline: wide-day rate (original) vs all-days rate (spec text)
""")


if __name__ == "__main__":
    main()
