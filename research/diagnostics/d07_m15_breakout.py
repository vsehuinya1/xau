"""D07 — M15 Breakout Sustainability"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_proportion_ci, bootstrap_ci, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport
from research.data.cache import disk_cached

_LOOKBACK_BARS = [5, 10, 20]     # M15 bars for high/low definition
_SUSTAIN_BARS  = 5               # bars before re-entry counts as "reversed"


@disk_cached(fmt="feather")
def _detect_m15_breakouts(high, low, close, atr, ts, lookback: int,
                           data_fp: str = "") -> pd.DataFrame:
    N = len(close)
    records = []
    for i in range(lookback + 1, N):
        window_hi = np.max(high[i - lookback: i])
        window_lo = np.min(low[i - lookback: i])
        bull_bo = close[i] > window_hi
        bear_bo = close[i] < window_lo
        if not (bull_bo or bear_bo):
            continue
        direction = 1 if bull_bo else -1
        level     = float(window_hi if bull_bo else window_lo)
        records.append({
            "bar_idx":   i,
            "ts":        ts[i],
            "direction": direction,
            "level":     level,
            "bar_size":  float(abs(close[i] - level)),
            "atr_ref":   float(atr[i]),
        })
    return pd.DataFrame(records)


@register_diagnostic
class D07M15Breakout(BaseDiagnostic):
    id        = "d07"
    tags      = ["structure", "breakout", "m15"]
    hypothesis = (
        "M15 range breakouts sustain (no close back below breakout level within "
        "5 bars) with probability P that is materially context-dependent."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m15  = data.ds.m15
        m1   = data.ds.m1
        lb   = config.params.get("lookback_bars", 10)

        bo_df = _detect_m15_breakouts(
            m15.high, m15.low, m15.close, m15.atr, m15.ts,
            lookback=lb, data_fp=data.data_fp
        )
        if bo_df.empty:
            return _empty()

        # Filter to mask range
        m1_ts_min = m1.ts[mask][0]  if mask.sum() > 0 else m1.ts[0]
        m1_ts_max = m1.ts[mask][-1] if mask.sum() > 0 else m1.ts[-1]
        bo_df = bo_df[(bo_df["ts"] >= m1_ts_min) & (bo_df["ts"] <= m1_ts_max)]

        if len(bo_df) < 30:
            return _empty()

        N15 = len(m15.close)
        records = []
        for _, row in bo_df.iterrows():
            i    = int(row["bar_idx"])
            dirn = int(row["direction"])
            level = float(row["level"])
            sess  = int(data.session[
                np.searchsorted(m1.ts, row["ts"], side="right") - 1
            ]) if row["ts"] >= m1.ts[0] else 3

            # Sustained = price does not close back below (bull) / above (bear) level
            sustained = True
            for j in range(i + 1, min(i + _SUSTAIN_BARS + 1, N15)):
                if dirn == 1 and m15.close[j] < level:
                    sustained = False; break
                if dirn == -1 and m15.close[j] > level:
                    sustained = False; break

            # MAE within 10 bars
            scan = slice(i, min(i + 10, N15))
            if dirn == 1:
                mae = float(m15.close[i] - np.min(m15.low[scan])) / \
                      (float(row["atr_ref"]) + 1e-9)
            else:
                mae = float(np.max(m15.high[scan]) - m15.close[i]) / \
                      (float(row["atr_ref"]) + 1e-9)

            records.append({
                "bar_idx":   i,
                "direction": dirn,
                "session":   sess,
                "sustained": int(sustained),
                "mae_atr":   float(mae),
                "bar_size_atr": float(row["bar_size"]) / (float(row["atr_ref"]) + 1e-9),
            })

        df = pd.DataFrame(records)
        n_obs = len(df)

        baseline_sustain = float(df["sustained"].mean())
        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        effect_sizes["sustain_rate_global"] = baseline_sustain
        n_sus = int(df["sustained"].sum())
        _, lo, hi = bootstrap_proportion_ci(n_sus, n_obs, n_boot=config.n_bootstrap)
        cis["sustain_rate_global"] = (lo, hi)

        # By session
        for sess_id, sname in {0: "Asian", 1: "London", 2: "NY"}.items():
            sub = df[df["session"] == sess_id]
            if len(sub) < 20:
                continue
            rate = float(sub["sustained"].mean())
            nf   = int(sub["sustained"].sum())
            _, lo2, hi2 = bootstrap_proportion_ci(nf, len(sub), n_boot=config.n_bootstrap)
            pr = permutation_test(
                sub["sustained"].values,
                df[df["session"] != sess_id]["sustained"].values,
                np.mean,
                n_permutations=min(config.n_permutations, 3_000),
            )
            key = f"sustain_{sname}"
            effect_sizes[key] = rate
            cis[key]          = (lo2, hi2)
            p_perm[key]       = pr.p_value

            er = build_effect_report(
                finding      = f"M15 breakout sustainability ({sname})",
                condition    = f"session={sname}, lookback={lb} bars",
                baseline     = baseline_sustain,
                effect_value = rate,
                effect_unit  = "probability_difference",
                ci           = (lo2, hi2),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = cohen_d(sub["sustained"].values,
                                       df[df["session"] != sess_id]["sustained"].values),
                stability    = 0.0,
                n_obs        = len(sub),
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        # Feature table
        bar_indices = np.where(mask)[0]
        m1_bo_bull  = np.zeros(len(bar_indices), dtype=bool)
        m1_bo_bear  = np.zeros(len(bar_indices), dtype=bool)
        m1_bo_age   = np.full(len(bar_indices), -1, dtype=np.int16)

        for _, row in bo_df.iterrows():
            m1_i = int(np.searchsorted(m1.ts, row["ts"], side="right") - 1)
            m1_i = np.clip(m1_i, 0, len(m1.ts) - 1)
            idx  = np.searchsorted(bar_indices, m1_i)
            end  = min(idx + 60, len(bar_indices))
            if row["direction"] == 1:
                m1_bo_bull[idx:end] = True
            else:
                m1_bo_bear[idx:end] = True
            for k in range(idx, end):
                age = bar_indices[k] - m1_i
                if m1_bo_age[k] < 0 or age < m1_bo_age[k]:
                    m1_bo_age[k] = np.int16(age)

        ft = pd.DataFrame({
            "bar_idx":    bar_indices,
            "m15_bo_bull": m1_bo_bull,
            "m15_bo_bear": m1_bo_bear,
            "m15_bo_age":  np.clip(m1_bo_age, 0, 32767).astype(np.int16),
        })

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": df, "effect_reports": effect_reports,
            "feature_df": ft,
            "summary_stats": {
                "n_breakouts": n_obs,
                "sustain_rate": baseline_sustain,
                "mae_atr_mean": float(df["mae_atr"].mean()),
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
