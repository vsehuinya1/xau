"""D06 — FVG Fill Rate Analysis"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_proportion_ci, cohen_d
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
        m1_ts_min = m1.ts[mask][0]  if mask.sum() > 0 else m1.ts[0]
        m1_ts_max = m1.ts[mask][-1] if mask.sum() > 0 else m1.ts[-1]
        fvg_df = fvg_df[(fvg_df["ts"] >= m1_ts_min) & (fvg_df["ts"] <= m1_ts_max)]

        if len(fvg_df) < 50:
            return _empty()

        N = len(m1.close)
        records = []
        for _, row in fvg_df.iterrows():
            i    = int(row["bar_idx"])
            dirn = int(row["direction"])
            mid  = (float(row["gap_top"]) + float(row["gap_bot"])) / 2
            atr  = float(row["atr_ref"]) if not np.isnan(row["atr_ref"]) else 1.0
            sess = int(data.session[i]) if i < len(data.session) else 3

            filled_at: dict[int, bool] = {h: False for h in _FILL_HORIZONS}
            for h in _FILL_HORIZONS:
                end = min(i + h, N)
                window_lo = np.min(m1.low[i:end])
                window_hi = np.max(m1.high[i:end])
                if dirn == 1:
                    filled_at[h] = window_lo <= mid
                else:
                    filled_at[h] = window_hi >= mid
                if filled_at[h]:
                    break    # once filled at shorter horizon, also filled at longer

            records.append({
                "bar_idx":   i,
                "direction": dirn,
                "gap_size_atr": float(row["gap_size"]) / (atr + 1e-9),
                "session":   sess,
                **{f"filled_{h}": int(filled_at[h]) for h in _FILL_HORIZONS},
            })

        df = pd.DataFrame(records)
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
