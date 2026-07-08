"""D06 — FVG Fill Rate Analysis"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import ts_as_i64, bootstrap_proportion_ci, cohen_d
from research.reports.effect_report import build_effect_report, EffectReport
from research.data.cache import disk_cached

_FILL_HORIZONS = [30, 60, 120, 240, 1440]   # M1 bars


@disk_cached(fmt="feather")
def _detect_fvgs(open_, high, low, close, atr, ts, data_fp: str = "") -> pd.DataFrame:
    """
    Detect all 3-bar Fair Value Gaps on M1.
    Bullish FVG: bar[i].low > bar[i-2].high  (gap up)
    Bearish FVG: bar[i].high < bar[i-2].low  (gap down)
    Cached on disk.
    """
    open_ = np.asarray(open_)
    high  = np.asarray(high)
    low   = np.asarray(low)
    close = np.asarray(close)
    atr   = np.asarray(atr)
    ts    = np.asarray(ts)
    N = len(close)
    records = []
    for i in range(2, N):
        if low[i] > high[i - 2]:        # bullish gap
            records.append({
                "bar_idx":   i,
                "ts":        ts[i],
                "direction": 1,
                "gap_top":   float(low[i]),
                "gap_bot":   float(high[i - 2]),
                "gap_size":  float(low[i] - high[i - 2]),
                "atr_ref":   float(atr[i]),
            })
        elif high[i] < low[i - 2]:      # bearish gap
            records.append({
                "bar_idx":   i,
                "ts":        ts[i],
                "direction": -1,
                "gap_top":   float(low[i - 2]),
                "gap_bot":   float(high[i]),
                "gap_size":  float(low[i - 2] - high[i]),
                "atr_ref":   float(atr[i]),
            })
    return pd.DataFrame(records)


@register_diagnostic
class D06FvgFillRate(BaseDiagnostic):
    id        = "d06"
    tags      = ["fvg", "structure", "smc"]
    hypothesis = (
        "M1 FVG fill rates are non-uniform across sessions and ATR contexts. "
        "Fill rate, time-to-fill, and conditional fill probability are measurable."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1 = data.ds.m1
        fvg_df = _detect_fvgs(
            m1.open, m1.high, m1.low, m1.close, m1.atr, m1.ts,
            data_fp=data.data_fp
        )
        if fvg_df.empty:
            return _empty()

        # Filter to mask date range
        _ts_m1  = ts_as_i64(m1.ts)
        _ts_min = _ts_m1[mask][0]  if mask.sum() > 0 else _ts_m1[0]
        _ts_max = _ts_m1[mask][-1] if mask.sum() > 0 else _ts_m1[-1]
        _ts_ev  = ts_as_i64(fvg_df["ts"].values)
        fvg_df  = fvg_df[(_ts_ev >= _ts_min) & (_ts_ev <= _ts_max)]

        if len(fvg_df) < 50:
            return _empty()

        N        = len(m1.close)
        bar_idx  = fvg_df["bar_idx"].values.astype(np.int64)
        dirn_arr = fvg_df["direction"].values.astype(np.int8)
        mid_arr  = ((fvg_df["gap_top"].values + fvg_df["gap_bot"].values) / 2).astype(np.float64)
        atr_arr  = np.where(np.isnan(fvg_df["atr_ref"].values), 1.0, fvg_df["atr_ref"].values)
        sess_arr = np.where(bar_idx < len(data.session), data.session[np.clip(bar_idx, 0, len(data.session)-1)], 3)

        # ── Vectorised fill check: forward rolling min/max for each horizon ─────
        # forward_min_low[i]  = min(m1.low[i : i+h])
        # forward_max_high[i] = max(m1.high[i : i+h])
        # Achieved by reversing the series, rolling backward, reversing back.
        low_s  = pd.Series(np.asarray(m1.low,  dtype=np.float64))
        high_s = pd.Series(np.asarray(m1.high, dtype=np.float64))

        fill_cols: dict[int, np.ndarray] = {}
        last_filled = np.zeros(len(bar_idx), dtype=bool)
        for h in _FILL_HORIZONS:
            fwd_min = low_s[::-1].rolling(h, min_periods=1).min()[::-1].values
            fwd_max = high_s[::-1].rolling(h, min_periods=1).max()[::-1].values
            idx_capped = np.minimum(bar_idx, N - 1)
            bull_fill  = (dirn_arr == 1)  & (fwd_min[idx_capped] <= mid_arr)
            bear_fill  = (dirn_arr == -1) & (fwd_max[idx_capped] >= mid_arr)
            filled     = (bull_fill | bear_fill) | last_filled  # monotone: filled at h ⊇ filled at shorter h
            fill_cols[h]  = filled.astype(np.int8)
            last_filled   = filled

        df = pd.DataFrame({
            "bar_idx":      bar_idx,
            "direction":    dirn_arr,
            "gap_size_atr": fvg_df["gap_size"].values / (atr_arr + 1e-9),
            "session":      sess_arr,
            **{f"filled_{h}": fill_cols[h] for h in _FILL_HORIZONS},
        })

        n_obs = len(df)

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        # ── Global fill rates by horizon
        for h in _FILL_HORIZONS:
            col = f"filled_{h}"
            rate = float(df[col].mean())
            n_fill = int(df[col].sum())
            _, lo, hi = bootstrap_proportion_ci(n_fill, n_obs, n_boot=config.n_bootstrap)
            effect_sizes[f"fill_rate_{h}"] = rate
            cis[f"fill_rate_{h}"]          = (lo, hi)

        # ── By session (primary horizon: 60 bars)
        baseline_60 = float(df["filled_60"].mean())
        for sess_id, sname in {0: "Asian", 1: "London", 2: "NY"}.items():
            sub = df[df["session"] == sess_id]
            if len(sub) < 20:
                continue
            rate = float(sub["filled_60"].mean())
            n_f  = int(sub["filled_60"].sum())
            _, lo, hi = bootstrap_proportion_ci(n_f, len(sub), n_boot=config.n_bootstrap)
            key = f"fill60_{sname}"
            effect_sizes[key] = rate
            cis[key]          = (lo, hi)

            er = build_effect_report(
                finding      = f"FVG fill rate within 60 bars ({sname})",
                condition    = f"session={sname}",
                baseline     = baseline_60,
                effect_value = rate,
                effect_unit  = "probability_difference",
                ci           = (lo, hi),
                p_perm       = 1.0,   # permutation on binary data is same as chi2
                p_adj        = 1.0,
                effect_d     = cohen_d(sub["filled_60"].values,
                                       df[df["session"] != sess_id]["filled_60"].values),
                stability    = 0.0,
                n_obs        = len(sub),
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        # Feature table: active FVG flags per bar
        bar_indices = np.where(mask)[0]
        bull_fvgs   = fvg_df[fvg_df["direction"] == 1]
        bear_fvgs   = fvg_df[fvg_df["direction"] == -1]
        fvg_active_bull = np.zeros(len(bar_indices), dtype=bool)
        fvg_active_bear = np.zeros(len(bar_indices), dtype=bool)
        # Simple window: FVG active if bar_idx within 60 bars of formation
        for _, fvg in bull_fvgs.iterrows():
            lo_i = int(fvg["bar_idx"])
            hi_i = lo_i + 60
            start = np.searchsorted(bar_indices, lo_i)
            end   = np.searchsorted(bar_indices, hi_i)
            fvg_active_bull[start:end] = True
        for _, fvg in bear_fvgs.iterrows():
            lo_i = int(fvg["bar_idx"])
            hi_i = lo_i + 60
            start = np.searchsorted(bar_indices, lo_i)
            end   = np.searchsorted(bar_indices, hi_i)
            fvg_active_bear[start:end] = True

        ft = pd.DataFrame({
            "bar_idx":        bar_indices,
            "fvg_active_bull": fvg_active_bull,
            "fvg_active_bear": fvg_active_bear,
        })

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": df, "effect_reports": effect_reports,
            "feature_df": ft,
            "summary_stats": {
                "n_fvgs": n_obs,
                "fill_rate_60":  effect_sizes.get("fill_rate_60"),
                "fill_rate_240": effect_sizes.get("fill_rate_240"),
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
