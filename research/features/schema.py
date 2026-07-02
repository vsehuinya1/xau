"""
research/features/schema.py — Master feature column definitions.

Every column that any diagnostic can contribute to the feature table is
defined here. This is the single source of truth for column names, dtypes,
and documentation. Diagnostics only contribute columns listed here.
"""
from __future__ import annotations

# {column_name: (dtype_str, description)}
FEATURE_SCHEMA: dict[str, tuple[str, str]] = {
    # ── Identity (always present, from DataProxy)
    "timestamp":           ("datetime64[ns]", "M1 bar open timestamp (UTC)"),
    "bar_idx":             ("int64",          "Sequential M1 bar index"),

    # ── Context
    "session":             ("int8",    "0=Asian 1=London 2=NY 3=Off"),
    "weekday":             ("int8",    "0=Mon 4=Fri"),
    "hour_utc":            ("int8",    "UTC hour of bar open"),
    "atr_pct_m15":         ("float32", "M15 ATR percentile [0,100], 200-bar window"),
    "bar_range_z":         ("float32", "M1 bar range z-score vs trailing 1440-bar mean"),

    # ── Daily context  (D03, D09)
    "pdr":                 ("float32", "Previous day true range (USD)"),
    "pdr_pct":             ("float32", "PDR rolling percentile [0,100] over 20 days"),
    "asian_range":         ("float32", "Asian session high − low (USD)"),
    "asian_range_pct":     ("float32", "Asian range rolling percentile [0,100]"),
    "asian_close_pos":     ("float32", "Asian close position in Asian range [0,1]"),

    # ── Session context  (D01)
    "session_de":          ("float32", "Directional efficiency of current session so far [0,1]"),
    "session_return":      ("float32", "Signed return from session open to this bar (USD)"),
    "prior_session_de":    ("float32", "DE of the prior completed session"),
    "prior_session_dir":   ("int8",    "+1 bullish / -1 bearish prior session"),

    # ── Trend / momentum  (D05)
    "new_high_5d":         ("bool",    "Daily close makes new 5-day high"),
    "new_high_20d":        ("bool",    "Daily close makes new 20-day high"),
    "new_low_5d":          ("bool",    "Daily close makes new 5-day low"),
    "new_low_20d":         ("bool",    "Daily close makes new 20-day low"),
    "bars_since_high_20d": ("int16",   "M1 bars since last 20-day high event"),

    # ── Volatility  (D04)
    "vol_spike":           ("bool",    "bar_range > 2× trailing 14-bar mean"),
    "vol_z":               ("float32", "Bar range z-score (see bar_range_z)"),
    "vol_regime":          ("int8",    "0=low 1=normal 2=high ATR-pct tercile"),

    # ── Impulse / pullback  (D02)
    "impulse_5bar_atr":    ("float32", "5-bar signed cumulative M5 move / ATR"),
    "impulse_8bar_atr":    ("float32", "8-bar signed cumulative M5 move / ATR"),
    "post_impulse_bars":   ("int16",   "M1 bars elapsed since last N=5 impulse end"),
    "pullback_depth":      ("float32", "Retracement fraction from impulse [0,1]"),

    # ── FVG proximity  (D06)
    "fvg_active_bull":     ("bool",    "Unfilled bullish M1 FVG within 60 bars"),
    "fvg_active_bear":     ("bool",    "Unfilled bearish M1 FVG within 60 bars"),
    "fvg_dist_atr_bull":   ("float32", "Distance to nearest bullish FVG / M1 ATR"),
    "fvg_dist_atr_bear":   ("float32", "Distance to nearest bearish FVG / M1 ATR"),

    # ── M15 structure  (D07)
    "m15_bo_bull":         ("bool",    "M15 bullish breakout within last 10 bars"),
    "m15_bo_bear":         ("bool",    "M15 bearish breakout within last 10 bars"),
    "m15_bo_age":          ("int16",   "M1 bars since last M15 breakout (any dir)"),

    # ── Forward returns (written last by D11)
    "fwd_ret_15m":         ("float32", "+15 M1 bar forward return (fraction)"),
    "fwd_ret_60m":         ("float32", "+60 M1 bar forward return (fraction)"),
    "fwd_ret_4h":          ("float32", "+240 M1 bar forward return (fraction)"),
    "fwd_ret_1d":          ("float32", "+390 M1 bar forward return (fraction)"),
    "fwd_ret_2d":          ("float32", "+780 M1 bar forward return (fraction)"),
}

# Ordered list of identity columns always present
IDENTITY_COLS = ["bar_idx", "timestamp"]
