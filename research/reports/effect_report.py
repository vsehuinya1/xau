"""
research/reports/effect_report.py — EffectReport dataclass and recommendation engine.

EffectReport is the atomic output unit: one key finding rendered as a
structured record with effect, CI, permutation p, FDR-adjusted p, stability,
and recommendation. Reports sort by stability_score DESC.
"""
from __future__ import annotations

from dataclasses import dataclass


PRACTICAL_THRESHOLDS: dict[str, float] = {
    "probability_difference": 0.10,   # < 10 ppt → not actionable
    "cohen_d":                0.20,   # < 0.2 → small effect
    "odds_ratio_delta":       0.20,   # < 20% change in odds
    "return_difference":      0.001,  # < 0.1% mean return difference
    "default":                0.10,
}


@dataclass
class EffectReport:
    finding:         str     # "London session continuation rate"
    condition:       str     # "when Asian DE > 0.7"
    baseline:        float   # unconditional rate / zero
    effect_value:    float   # conditional value (not delta)
    effect_unit:     str     # "probability" / "cohen_d" / "USD"
    ci_lower:        float   # 95% BCa lower bound
    ci_upper:        float   # 95% BCa upper bound
    p_perm:          float   # permutation test raw p
    p_adj:           float   # FDR-adjusted p (BH default)
    effect_d:        float   # Cohen's d or equivalent standardised
    practical_min:   float   # pre-specified minimum effect size
    is_practical:    bool    # |effect_value − baseline| > practical_min
    ci_excl_zero:    bool    # CI entirely on one side of baseline
    stability:       float   # ∈ [0, 1]
    recommendation:  str     # "Actionable" / "Monitor" / "Ignore"
    n_obs:           int     # number of observations in this cell
    n_obs_baseline:  int     # number of observations in baseline

    # ── Formatted one-liner for reports
    def label(self) -> str:
        icons = {"Actionable": "✓", "Monitor": "~", "Ignore": "✗"}
        icon  = icons.get(self.recommendation, "?")
        delta = self.effect_value - self.baseline
        sign  = "+" if delta >= 0 else ""
        return (
            f"[{icon} {self.recommendation}]  {self.finding}  |  {self.condition}\n"
            f"  Baseline {self.baseline:.1%}  →  Effect {self.effect_value:.1%}  "
            f"({sign}{delta:.1%})\n"
            f"  95% CI [{self.ci_lower:.1%}, {self.ci_upper:.1%}]  "
            f"p_perm={self.p_perm:.4f}  p_adj={self.p_adj:.4f}  "
            f"d={self.effect_d:.2f}  stab={self.stability:.2f}  n={self.n_obs}"
        )


def make_recommendation(r: EffectReport) -> str:
    """
    Actionable: practical + CI excludes zero + p_adj < 0.05 + stability ≥ 0.60
    Monitor   : practical + (unstable OR marginal CI)
    Ignore    : not practical, OR CI crosses zero AND p_adj > 0.10
    """
    if (r.is_practical
            and r.ci_excl_zero
            and r.p_adj < 0.05
            and r.stability >= 0.60
            and r.n_obs >= 50):
        return "Actionable"
    if r.is_practical and (r.stability >= 0.40 or r.ci_excl_zero) and r.n_obs >= 30:
        return "Monitor"
    return "Ignore"


def build_effect_report(
    finding:        str,
    condition:      str,
    baseline:       float,
    effect_value:   float,
    effect_unit:    str,
    ci:             tuple[float, float],
    p_perm:         float,
    p_adj:          float,
    effect_d:       float,
    stability:      float,
    n_obs:          int,
    n_obs_baseline: int,
) -> EffectReport:
    """Construct an EffectReport with auto-computed recommendation."""
    thresh  = PRACTICAL_THRESHOLDS.get(effect_unit, PRACTICAL_THRESHOLDS["default"])
    delta   = abs(effect_value - baseline)
    is_prac = delta >= thresh

    # CI excludes the baseline value
    ci_excl = (ci[0] > baseline) or (ci[1] < baseline)

    r = EffectReport(
        finding        = finding,
        condition      = condition,
        baseline       = baseline,
        effect_value   = effect_value,
        effect_unit    = effect_unit,
        ci_lower       = ci[0],
        ci_upper       = ci[1],
        p_perm         = p_perm,
        p_adj          = p_adj,
        effect_d       = effect_d,
        practical_min  = thresh,
        is_practical   = is_prac,
        ci_excl_zero   = ci_excl,
        stability      = stability,
        recommendation = "Ignore",  # placeholder
        n_obs          = n_obs,
        n_obs_baseline = n_obs_baseline,
    )
    r.recommendation = make_recommendation(r)
    return r
