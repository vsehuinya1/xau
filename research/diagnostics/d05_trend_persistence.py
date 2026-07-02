"""D05 — Trend Persistence After N-Day High/Low"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport

_LOOKBACKS = [5, 10, 20, 60]
_HORIZONS  = [15, 60, 240, 390]   # M1 bars
_HLABELS   = ["15m", "60m", "4h", "1d"]


@register_diagnostic
class D05TrendPersistence(BaseDiagnostic):
    id        = "d05"
    tags      = ["trend", "momentum", "daily"]
    hypothesis = (
        "Price making a new N-day high or low exhibits measurable forward "
        "momentum over subsequent K bars. Effect size and direction compared "
        "to random baseline."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1  = data.ds.m1
        bar_indices = np.where(mask)[0]

        fwd = {h: data.fwd_ret.get(h, np.full(len(m1.ts), np.nan)) for h in _HORIZONS}

        # Primary lookback: 20 days
        primary_n = 20
        flag_h = data.nd_high.get(primary_n, np.zeros(len(m1.ts), dtype=bool))
        flag_l = data.nd_low.get(primary_n, np.zeros(len(m1.ts), dtype=bool))

        records = []
        for bi in bar_indices:
            if flag_h[bi] or flag_l[bi]:
                direction = 1 if flag_h[bi] else -1
                records.append({
                    "bar_idx":   int(bi),
                    "direction": direction,
                    "session":   int(data.session[bi]),
                    **{lab: float(fwd[h][bi]) for h, lab in zip(_HORIZONS, _HLABELS)},
                })
        df = pd.DataFrame(records)
        n_obs = len(df)

        if n_obs < 30:
            return _empty()

        # Baseline: all bars in mask
        baseline_60m = fwd[60][bar_indices]
        baseline_60m = baseline_60m[~np.isnan(baseline_60m)]

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        # ── Bullish momentum
        bull = df[df["direction"] == 1]
        bear = df[df["direction"] == -1]

        for lab in ["60m", "4h", "1d"]:
            bull_ret = bull[lab].dropna().values
            if len(bull_ret) < 20:
                continue
            _, lo, hi   = bootstrap_ci(bull_ret, np.mean, n=config.n_bootstrap)
            t_stat, t_p = ttest_1samp(bull_ret, 0.0)
            pr          = permutation_test(bull_ret, baseline_60m if lab == "60m"
                                           else bull_ret, np.mean,
                                           n_permutations=min(config.n_permutations, 3_000))

            key = f"new20d_high_{lab}_mean"
            effect_sizes[key] = float(np.nanmean(bull_ret))
            cis[key]          = (lo, hi)
            p_raw[key]        = float(t_p)
            p_perm[key]       = pr.p_value

            er = build_effect_report(
                finding      = f"New 20d high → {lab} forward return",
                condition    = "new_20d_high, all sessions",
                baseline     = float(np.nanmean(baseline_60m)),
                effect_value = float(np.nanmean(bull_ret)),
                effect_unit  = "return_difference",
                ci           = (lo, hi),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = cohen_d(bull_ret, baseline_60m),
                stability    = 0.0,
                n_obs        = len(bull_ret),
                n_obs_baseline = len(baseline_60m),
            )
            effect_reports.append(er)

        # ── Bearish momentum
        for lab in ["60m", "4h"]:
            bear_ret = bear[lab].dropna().values * -1   # flip sign: bearish = expect negative
            if len(bear_ret) < 20:
                continue
            _, lo, hi = bootstrap_ci(bear_ret, np.mean, n=config.n_bootstrap)
            key = f"new20d_low_{lab}_mean"
            effect_sizes[key] = float(np.nanmean(bear_ret))
            cis[key]          = (lo, hi)
            t_stat, t_p       = ttest_1samp(bear_ret, 0.0)
            p_raw[key]        = float(t_p)

        # ── N-day breakdown (quick scan: effect by lookback)
        n_effects = {}
        for n in _LOOKBACKS:
            fh = data.nd_high.get(n, np.zeros(len(m1.ts), dtype=bool))
            events = bar_indices[fh[bar_indices]]
            if len(events) < 20:
                continue
            ret60 = fwd[60][events]
            ret60 = ret60[~np.isnan(ret60)]
            n_effects[n] = float(np.nanmean(ret60))

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": df, "effect_reports": effect_reports,
            "feature_df": None,
            "summary_stats": {
                "n_new_20d_high": int(len(bull)),
                "n_new_20d_low":  int(len(bear)),
                "n_effects_by_lookback": n_effects,
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
