"""
research/diagnostics/base.py — BaseDiagnostic ABC + ResultsBundle + Conclusion.

Every diagnostic inherits BaseDiagnostic and implements _compute_core().
The base class's run() method handles:
  - Disk caching (via research.data.cache)
  - Subperiod splitting (2018-2021 / 2022-2025)
  - Stability score computation
  - FDR correction across all p-values in the bundle
  - Automatic warning generation
  - Conclusion classification
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.utils import fdr_correction
from research.reports.stability import compute_stability_score, subperiod_mask
from research.reports.effect_report import EffectReport

# Default subperiods for stability checks
SUBPERIODS = [
    ("2018-01-01", "2021-12-31"),
    ("2022-01-01", "2025-12-31"),
]

MIN_OBS_WARN = 50    # Warn if any cell has fewer observations


class Conclusion(str, Enum):
    POSITIVE     = "positive"       # stable, practical, p < 0.05
    NEGATIVE     = "negative"       # measured but below practical threshold
    NULL         = "null"           # effect indistinguishable from noise
    INCONCLUSIVE = "inconclusive"   # insufficient sample or unstable


@dataclass
class DiagnosticConfig:
    """Runtime config parsed from YAML or defaults."""
    n_bootstrap:    int   = 2_000
    n_permutations: int   = 10_000
    fdr_method:     str   = "bh"
    alpha:          float = 0.05
    use_cache:      bool  = True
    emit_features:  bool  = True
    subperiods:     list  = field(default_factory=lambda: list(SUBPERIODS))
    params:         dict  = field(default_factory=dict)


@dataclass
class ResultsBundle:
    # ── Identity
    diagnostic_id:       str
    hypothesis:          str
    parameters:          dict
    date_range:          tuple[str, str]

    # ── Sample
    sample_size:         int

    # ── Subperiod bundles (partial — only summary_stats and effect_reports)
    subperiod_results:   dict[str, dict]

    # ── Statistics
    effect_sizes:        dict[str, float]
    confidence_intervals: dict[str, tuple[float, float]]
    p_values:            dict[str, tuple[float, float, float]]  # (raw, perm, adj)

    # ── Stability
    stability_score:     float

    # ── Warnings (auto-generated)
    warnings:            list[str]

    # ── Key findings
    effect_reports:      list[EffectReport]

    # ── Conclusion
    conclusion:          Conclusion

    # ── Data outputs
    raw_events:          pd.DataFrame
    feature_contributions: pd.DataFrame | None   # bar_idx-indexed feature cols

    # ── Narrative
    summary:             str


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseDiagnostic(ABC):
    """
    Subclasses must define:
      id:         str            e.g. "d01"
      tags:       list[str]      e.g. ["sessions", "direction"]
      hypothesis: str            one-sentence hypothesis

    And implement:
      _compute_core(data, config, mask) -> dict
        data   : DataProxy
        config : DiagnosticConfig
        mask   : bool array — selects M1 bars in scope (for subperiod slicing)

    _compute_core must return a dict with at least:
      "n_obs"          : int
      "effect_sizes"   : dict[str, float]
      "cond_probs"     : dict   (conditional probability tables)
      "raw_events"     : pd.DataFrame
      "p_values_raw"   : dict[str, float]   (before FDR)
      "p_values_perm"  : dict[str, float]   (permutation tests)
      "ci"             : dict[str, tuple[float, float]]   (95% BCa)
      "effect_reports" : list[EffectReport]  (pre-built, stability=0 placeholder)
      "feature_df"     : pd.DataFrame | None
      "summary_stats"  : dict[str, Any]
    """

    id:         str = ""
    tags:       list[str] = []
    hypothesis: str = ""

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(
        self,
        data:   "DataProxy",   # noqa: F821
        config: DiagnosticConfig | None = None,
    ) -> ResultsBundle:
        if config is None:
            config = DiagnosticConfig()

        print(f"\n[{self.id}] Running …  hypothesis: {self.hypothesis[:60]}")

        ts = data.ds.m1.ts
        date_range = (
            str(pd.Timestamp(ts[0]).date()),
            str(pd.Timestamp(ts[-1]).date()),
        )

        # ── Full-period computation
        full_mask = np.ones(len(ts), dtype=bool)
        core      = self._compute_core(data, config, full_mask)

        # ── Subperiod computation (for stability)
        sub_results: dict[str, dict] = {}
        sub_cores:   list[tuple[str, dict]] = []
        for start, end in config.subperiods:
            mask = subperiod_mask(ts, start, end)
            if mask.sum() < MIN_OBS_WARN:
                sub_results[f"{start[:4]}-{end[:4]}"] = {"n_obs": int(mask.sum())}
                continue
            sc = self._compute_core(data, config, mask)
            label = f"{start[:4]}-{end[:4]}"
            sub_results[label] = {
                "n_obs":        sc["n_obs"],
                "effect_sizes": sc["effect_sizes"],
                "summary_stats": sc.get("summary_stats", {}),
            }
            sub_cores.append((label, sc))

        # ── Stability score (use first key effect if available)
        stability = 0.5   # default if only one subperiod
        if len(sub_cores) >= 2:
            key = next(iter(core["effect_sizes"]), None)
            if key and all(key in sc["effect_sizes"] for _, sc in sub_cores[:2]):
                ea  = sub_cores[0][1]["effect_sizes"][key]
                eb  = sub_cores[1][1]["effect_sizes"][key]
                cia = sub_cores[0][1]["ci"].get(key, (ea, ea))
                cib = sub_cores[1][1]["ci"].get(key, (eb, eb))
                stability = compute_stability_score(ea, eb, cia, cib)

        # ── FDR correction across all p-values
        raw_ps   = core.get("p_values_raw",  {})
        perm_ps  = core.get("p_values_perm", {})
        all_ps   = {**raw_ps, **perm_ps}
        adj      = fdr_correction(all_ps, method=config.fdr_method, alpha=config.alpha)
        p_values = {
            k: (raw_ps.get(k, np.nan),
                perm_ps.get(k, np.nan),
                adj.get(k, (np.nan, False))[0])
            for k in set(raw_ps) | set(perm_ps)
        }

        # ── Attach stability and p_adj to each EffectReport
        effect_reports = []
        for r in core.get("effect_reports", []):
            key_perm = r.finding.replace(" ", "_").lower()
            r.stability = stability
            r.p_adj     = adj.get(key_perm, (r.p_adj, False))[0]
            from research.reports.effect_report import make_recommendation
            r.recommendation = make_recommendation(r)
            effect_reports.append(r)

        # ── Auto-warnings
        warnings = _auto_warnings(
            core, stability, p_values, config.alpha, adj
        )

        # ── Conclusion
        conclusion = _classify_conclusion(effect_reports, stability, core["n_obs"])

        # ── Summary text
        summary = self._make_summary(core, effect_reports, stability, conclusion)

        print(f"  [{self.id}] n={core['n_obs']:,}  "
              f"stability={stability:.2f}  conclusion={conclusion.value}")
        for r in effect_reports[:3]:
            print(f"    {r.label().splitlines()[0]}")

        return ResultsBundle(
            diagnostic_id          = self.id,
            hypothesis             = self.hypothesis,
            parameters             = config.params,
            date_range             = date_range,
            sample_size            = core["n_obs"],
            subperiod_results      = sub_results,
            effect_sizes           = core["effect_sizes"],
            confidence_intervals   = core["ci"],
            p_values               = p_values,
            stability_score        = stability,
            warnings               = warnings,
            effect_reports         = effect_reports,
            conclusion             = conclusion,
            raw_events             = core.get("raw_events", pd.DataFrame()),
            feature_contributions  = core.get("feature_df"),
            summary                = summary,
        )

    # ── Abstract ───────────────────────────────────────────────────────────────

    @abstractmethod
    def _compute_core(
        self,
        data:   "DataProxy",  # noqa: F821
        config: DiagnosticConfig,
        mask:   np.ndarray,
    ) -> dict:
        """Core statistical computation for the given bar mask (subperiod)."""
        ...

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _make_summary(
        self,
        core:           dict,
        effect_reports: list[EffectReport],
        stability:      float,
        conclusion:     Conclusion,
    ) -> str:
        actionable = [r for r in effect_reports if r.recommendation == "Actionable"]
        monitor    = [r for r in effect_reports if r.recommendation == "Monitor"]
        lines = [
            f"n_observations = {core['n_obs']:,}",
            f"stability_score = {stability:.2f}",
            f"conclusion = {conclusion.value}",
            f"actionable findings = {len(actionable)}",
            f"monitor findings = {len(monitor)}",
        ]
        if actionable:
            lines.append("\nActionable findings:")
            for r in actionable:
                lines.append(f"  {r.finding}: {r.effect_value - r.baseline:+.1%}")
        return "\n".join(lines)


# ── Auto-warning generation ───────────────────────────────────────────────────

def _auto_warnings(
    core:       dict,
    stability:  float,
    p_values:   dict,
    alpha:      float,
    adj:        dict,
) -> list[str]:
    w: list[str] = []

    if core["n_obs"] < MIN_OBS_WARN:
        w.append(f"LOW_SAMPLE: {core['n_obs']} events (minimum recommended: {MIN_OBS_WARN})")

    ci = core.get("ci", {})
    for name, (lo, hi) in ci.items():
        if not np.isnan(lo) and not np.isnan(hi) and lo < 0 < hi:
            w.append(f"CI_CROSSES_ZERO: '{name}' CI [{lo:.3f}, {hi:.3f}]")

    if stability < 0.40:
        w.append(f"SUBPERIOD_UNSTABLE: stability_score={stability:.2f} < 0.40")

    n_rejected = sum(1 for _, reject in adj.values() if reject)
    n_total    = len(adj)
    if n_total > 1:
        w.append(
            f"FDR_ADJUSTED: {n_rejected}/{n_total} tests rejected at "
            f"q={alpha:.2f} after BH correction"
        )

    return w


def _classify_conclusion(
    reports:    list[EffectReport],
    stability:  float,
    n_obs:      int,
) -> Conclusion:
    if n_obs < MIN_OBS_WARN or stability < 0.30:
        return Conclusion.INCONCLUSIVE
    if any(r.recommendation == "Actionable" for r in reports):
        return Conclusion.POSITIVE
    # Distinguish NEGATIVE (effect measured, too small) from NULL (no signal)
    if any(r.is_practical for r in reports):
        return Conclusion.NEGATIVE
    non_null = [r for r in reports if r.ci_excl_zero]
    if non_null:
        return Conclusion.NEGATIVE
    return Conclusion.NULL
