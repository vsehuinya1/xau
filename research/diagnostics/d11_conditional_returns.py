"""
D11 — Conditional Return Distribution
======================================
The foundation diagnostic. Runs first.

Hypothesis: The conditional distribution of forward returns (15m, 60m, 4h, 1d)
differs materially across regimes defined by session × weekday × ATR-pct tercile
× prior session direction. No thresholds. No entries. The output is the universal
prior for all future strategy research.

Also writes fwd_ret_* columns to the feature table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d
from research.reports.effect_report import build_effect_report, EffectReport

_HORIZONS       = [15, 60, 240, 390, 780]
_HORIZON_LABELS = ["15m", "60m", "4h", "1d", "2d"]


@register_diagnostic
class D11ConditionalReturnDistribution(BaseDiagnostic):
    id        = "d11"
    tags      = ["baseline", "distributions", "sessions", "all"]
    hypothesis = (
        "Forward return distributions at multiple horizons differ materially "
        "across regimes (session × weekday × ATR-pct tercile × prior direction). "
        "No thresholds. This is the universal prior for all future research."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1      = data.ds.m1
        session = data.session[mask]
        weekday = data.weekday[mask]
        atr_pct = m1.atr_pct[mask]

        # ATR-pct tercile: 0=low, 1=normal, 2=high
        p33 = np.nanpercentile(atr_pct, 33.3)
        p67 = np.nanpercentile(atr_pct, 66.7)
        atr_tercile = np.zeros(mask.sum(), dtype=np.int8)
        atr_tercile[atr_pct > p67] = 2
        atr_tercile[(atr_pct > p33) & (atr_pct <= p67)] = 1

        # Forward returns — fully vectorised, no Python loops
        bar_indices = np.where(mask)[0]
        fwd = {
            lab: data.fwd_ret.get(h, np.full(len(m1.ts), np.nan))[mask]
            for h, lab in zip(_HORIZONS, _HORIZON_LABELS)
        }

        # Build regime DataFrame directly from arrays (no Python per-bar loop)
        df = pd.DataFrame({
            "bar_idx":     bar_indices.astype(np.int64),
            "session":     session.astype(np.int8),
            "weekday":     weekday.astype(np.int8),
            "atr_tercile": atr_tercile,
            **{lab: fwd[lab].astype(np.float32) for lab in _HORIZON_LABELS},
        })

        n_obs          = len(df)
        baseline_60m   = df["60m"].dropna()
        baseline_mean  = float(baseline_60m.mean())

        p_values_perm: dict[str, float] = {}
        p_values_raw:  dict[str, float] = {}
        cis:           dict[str, tuple] = {}
        effect_sizes:  dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        # ── Session × horizon analysis
        for sess in [0, 1, 2]:
            sess_mask = df["session"] == sess
            sess_name = {0: "Asian", 1: "London", 2: "NY"}[sess]

            for lab in ["15m", "60m", "4h"]:
                grp = df.loc[sess_mask, lab].dropna().values
                baseline_h = df[lab].dropna().values
                if len(grp) < 30 or len(baseline_h) < 30:
                    continue

                _, ks_p = ks_2samp(grp, baseline_h)
                mean_, lo, hi = bootstrap_ci(grp, np.mean, n=config.n_bootstrap)
                bl_v, _, _    = bootstrap_ci(baseline_h, np.mean, n=config.n_bootstrap)
                d             = cohen_d(grp, baseline_h)

                key = f"session_{sess}_{lab}_mean"
                p_values_raw[key] = float(ks_p)
                cis[key]          = (lo, hi)
                effect_sizes[key] = d

                er = build_effect_report(
                    finding      = f"{sess_name} {lab} mean return",
                    condition    = f"session={sess_name}",
                    baseline     = float(bl_v),
                    effect_value = float(mean_),
                    effect_unit  = "return_difference",
                    ci           = (lo, hi),
                    p_perm       = float(ks_p),
                    p_adj        = float(ks_p),
                    effect_d     = d,
                    stability    = 0.0,
                    n_obs        = len(grp),
                    n_obs_baseline = len(baseline_h),
                )
                effect_reports.append(er)

            # ATR-tercile breakdown within London
            if sess == 1:
                for terc in [0, 1, 2]:
                    t_mask = sess_mask & (df["atr_tercile"] == terc)
                    t_grp  = df.loc[t_mask, "60m"].dropna().values
                    if len(t_grp) < 30:
                        continue
                    t_mean, t_lo, t_hi = bootstrap_ci(t_grp, np.mean, n=config.n_bootstrap)
                    t_key = f"london_atr_terc{terc}_60m_mean"
                    p_values_raw[t_key]  = float(ks_2samp(t_grp, baseline_60m.values)[1])
                    cis[t_key]           = (t_lo, t_hi)
                    effect_sizes[t_key]  = cohen_d(t_grp, baseline_60m.values)

        # ── Weekday mean return at 60m
        for wd in range(5):
            wd_name = ["Mon", "Tue", "Wed", "Thu", "Fri"][wd]
            grp = df.loc[df["weekday"] == wd, "60m"].dropna().values
            if len(grp) < 50:
                continue
            mean_, lo, hi = bootstrap_ci(grp, np.mean, n=config.n_bootstrap)
            key = f"weekday_{wd}_60m_mean"
            p_values_raw[key]  = float(ks_2samp(grp, baseline_60m.values)[1])
            cis[key]           = (lo, hi)
            effect_sizes[key]  = cohen_d(grp, baseline_60m.values)

        # ── Feature table: forward return columns (vectorised)
        feature_df = pd.DataFrame({
            "bar_idx":    bar_indices.astype(np.int64),
            "fwd_ret_15m": fwd["15m"],
            "fwd_ret_60m": fwd["60m"],
            "fwd_ret_4h":  fwd["4h"],
            "fwd_ret_1d":  fwd["1d"],
            "fwd_ret_2d":  fwd["2d"],
        })

        return {
            "n_obs":          n_obs,
            "effect_sizes":   effect_sizes,
            "ci":             cis,
            "p_values_raw":   p_values_raw,
            "p_values_perm":  p_values_perm,
            "raw_events":     df,
            "effect_reports": effect_reports,
            "feature_df":     feature_df,
            "summary_stats": {
                "global_60m_mean":   baseline_mean,
                "n_regimes_tested":  len(p_values_raw),
                "n_bars":            n_obs,
            },
        }
