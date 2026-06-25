"""
XAUUSD Data Loader
==================
Loads 1-minute histdata.com CSVs (2018-2025), auto-unzips missing files,
resamples to M15 and H1, and computes Wilder ATR, rolling ATR-percentile
rank, and slow EMA for every timeframe.

CSV format (no header):
    YYYYMMDD HHMMSS,open,high,low,close,volume
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR    = Path(__file__).resolve().parent.parent / "data"
ATR_PERIOD  = 14
EMA_PERIOD  = 50      # H1 slow EMA for slope filter
ATR_PCT_LBK = 200     # bars for rolling ATR-percentile window


# ── Data containers ──────────────────────────────────────────────────────────

@dataclass
class BarData:
    """Immutable numpy-backed OHLCV + derived arrays for one timeframe."""
    ts:       np.ndarray   # datetime64[ns] UTC, shape (N,)
    open:     np.ndarray   # float64
    high:     np.ndarray   # float64
    low:      np.ndarray   # float64
    close:    np.ndarray   # float64
    volume:   np.ndarray   # float64
    atr:      np.ndarray   # float64 — Wilder 14-bar ATR
    atr_pct:  np.ndarray   # float64 — 200-bar rolling ATR percentile [0, 100]
    ema_slow: np.ndarray   # float64 — 50-bar EMA of close

    @property
    def n(self) -> int:
        return len(self.ts)

    def idx_at_or_before(self, t: np.datetime64) -> int:
        """Last bar index whose timestamp <= t.  Returns -1 if t is before all bars."""
        return int(np.searchsorted(self.ts, t, side="right")) - 1


@dataclass
class DataStore:
    m1:  BarData
    m5:  BarData
    m15: BarData
    h1:  BarData
    h4:  BarData


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_year(year: int) -> pd.DataFrame:
    csv = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
    zp  = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.zip"

    if not csv.exists() and zp.exists():
        print(f"    auto-unzipping {zp.name} …")
        with zipfile.ZipFile(zp) as z:
            z.extractall(DATA_DIR)

    if not csv.exists():
        raise FileNotFoundError(f"No M1 data for {year}. Expected: {csv}")

    df = pd.read_csv(
        csv,
        sep=";",
        header=None,
        names=["dt", "open", "high", "low", "close", "volume"],
        dtype={"open": float, "high": float, "low": float,
               "close": float, "volume": float},
    )
    df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S", utc=True)
    df.set_index("dt", inplace=True)
    df.dropna(inplace=True)
    return df


def _wilder_atr(high: np.ndarray, low: np.ndarray,
                close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothed ATR.  Returns array of same length; first (period-1) values are NaN."""
    N = len(high)
    prev_close = np.empty(N)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]

    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low  - prev_close)))

    atr = np.full(N, np.nan)
    if N < period:
        return atr
    atr[period - 1] = tr[:period].mean()
    mul = (period - 1) / period
    for i in range(period, N):
        atr[i] = atr[i - 1] * mul + tr[i] / period
    return atr


def _atr_percentile(atr: np.ndarray, lookback: int) -> np.ndarray:
    """Rolling percentile rank of ATR in the range [0, 100]."""
    N   = len(atr)
    pct = np.full(N, np.nan)
    for i in range(lookback - 1, N):
        if np.isnan(atr[i]):
            continue
        window = atr[max(0, i - lookback + 1): i + 1]
        valid  = window[~np.isnan(window)]
        if valid.size > 0:
            pct[i] = float(np.sum(valid <= atr[i])) / valid.size * 100.0
    return pct


def _ema(close: np.ndarray, period: int) -> np.ndarray:
    """Standard exponential moving average."""
    N = len(close)
    k = 2.0 / (period + 1)
    e = np.full(N, np.nan)
    # Seed from the first non-NaN value
    start = int(np.argmax(~np.isnan(close))) if not np.all(np.isnan(close)) else N
    if start >= N:
        return e
    e[start] = close[start]
    for i in range(start + 1, N):
        prev = e[i - 1] if not np.isnan(e[i - 1]) else close[i]
        e[i] = close[i] * k + prev * (1.0 - k)
    return e


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    out = df.resample(rule).agg(
        open   = ("open",   "first"),
        high   = ("high",   "max"),
        low    = ("low",    "min"),
        close  = ("close",  "last"),
        volume = ("volume", "sum"),
    ).dropna(subset=["open"])
    return out


def _to_bar_data(
    df: pd.DataFrame,
    compute_atr_pct: bool = False,
    compute_ema: bool = False,
) -> BarData:
    """
    Build a BarData from a resampled DataFrame.

    Only compute the derived series that are actually used downstream:
      - atr_pct  → only needed on M15  (regime volatility filter)
      - ema_slow → only needed on H1   (regime slope filter)
    Skipping unused computations saves ~60 s per year on M1.
    """
    h  = df["high"].to_numpy(np.float64)
    lo = df["low"].to_numpy(np.float64)
    c  = df["close"].to_numpy(np.float64)
    atr     = _wilder_atr(h, lo, c, ATR_PERIOD)
    atr_pct = _atr_percentile(atr, ATR_PCT_LBK) if compute_atr_pct else np.full(len(c), np.nan)
    ema     = _ema(c, EMA_PERIOD)               if compute_ema      else np.full(len(c), np.nan)
    return BarData(
        ts       = df.index.to_numpy(),
        open     = df["open"].to_numpy(np.float64),
        high     = h,
        low      = lo,
        close    = c,
        volume   = df["volume"].to_numpy(np.float64),
        atr      = atr,
        atr_pct  = atr_pct,
        ema_slow = ema,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def load(start_year: int = 2018, end_year: int = 2025) -> DataStore:
    """
    Load all M1 histdata CSVs and return a DataStore.

    - Auto-unzips any .zip that has no matching .csv.
    - Resamples M1 → M15 and M1 → H1.
    - Computes Wilder ATR, 200-bar ATR percentile, 50-bar EMA for all TFs.
    """
    frames = []
    for yr in range(start_year, end_year + 1):
        print(f"  loading {yr} …")
        frames.append(_load_year(yr))

    m1_df = pd.concat(frames).sort_index()
    m1_df = m1_df[~m1_df.index.duplicated(keep="first")]
    print(f"  M1 bars loaded: {len(m1_df):,}")

    print("  resampling → M5 …")
    m5_df  = _resample(m1_df, "5min")

    print("  resampling → M15 …")
    m15_df = _resample(m1_df, "15min")

    print("  resampling → H1 …")
    h1_df  = _resample(m1_df, "1h")

    print("  resampling → H4 …")
    h4_df  = _resample(m1_df, "4h")

    print("  computing ATR / derived series …")
    # M1  : only ATR needed
    # M5  : ATR only (structure detection)
    # M15 : ATR + ATR-percentile (regime volatility filter)
    # H1  : ATR + slow EMA       (regime slope filter)
    # H4  : ATR only             (ADX regime filter)
    m1  = _to_bar_data(m1_df,  compute_atr_pct=False, compute_ema=False)
    m5  = _to_bar_data(m5_df,  compute_atr_pct=False, compute_ema=False)
    m15 = _to_bar_data(m15_df, compute_atr_pct=True,  compute_ema=False)
    h1  = _to_bar_data(h1_df,  compute_atr_pct=False, compute_ema=True)
    h4  = _to_bar_data(h4_df,  compute_atr_pct=False, compute_ema=False)

    print(f"  done — M1={m1.n:,}  M5={m5.n:,}  M15={m15.n:,}  H1={h1.n:,}  H4={h4.n:,}")
    return DataStore(m1=m1, m5=m5, m15=m15, h1=h1, h4=h4)
