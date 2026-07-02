"""
research/reports/output.py — Report serialisation: CSV, JSON, plain-text console.

Produces:
  research/output/<run_id>/<diagnostic_id>.txt   — human-readable summary
  research/output/<run_id>/<diagnostic_id>.json  — machine-readable full bundle
  research/output/<run_id>/findings.csv          — all EffectReports across run
  research/output/<run_id>/negative_findings.md  — negative / null results
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from research.diagnostics.base import ResultsBundle

OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "research" / "output"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_safe(obj):
    """Recursively make obj JSON-serialisable."""
    if isinstance(obj, float):
        return None if (obj != obj) else obj          # NaN → null
    if isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if hasattr(obj, "__float__"):
        v = float(obj)
        return None if v != v else v
    return str(obj)


# ── Per-diagnostic output ─────────────────────────────────────────────────────

def save_bundle(bundle: "ResultsBundle", run_id: str) -> None:
    out_dir = OUTPUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Plain text summary
    txt_path = out_dir / f"{bundle.diagnostic_id}.txt"
    txt_path.write_text(_format_text(bundle), encoding="utf-8")

    # ── JSON (full bundle, minus raw DataFrames which are too large)
    json_path = out_dir / f"{bundle.diagnostic_id}.json"
    payload = {
        "diagnostic_id":    bundle.diagnostic_id,
        "hypothesis":       bundle.hypothesis,
        "parameters":       _json_safe(bundle.parameters),
        "date_range":       bundle.date_range,
        "sample_size":      bundle.sample_size,
        "stability_score":  bundle.stability_score,
        "conclusion":       bundle.conclusion.value,
        "warnings":         bundle.warnings,
        "effect_sizes":     _json_safe(bundle.effect_sizes),
        "confidence_intervals": _json_safe(bundle.confidence_intervals),
        "p_values":         _json_safe(bundle.p_values),
        "effect_reports": [
            _json_safe(asdict(r)) for r in bundle.effect_reports
        ],
        "summary": bundle.summary,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format_text(b: "ResultsBundle") -> str:
    lines = [
        "=" * 70,
        f"  {b.diagnostic_id.upper()} — {b.hypothesis[:60]}",
        "=" * 70,
        f"  Date range    : {b.date_range[0]} → {b.date_range[1]}",
        f"  Sample size   : {b.sample_size:,}",
        f"  Stability     : {b.stability_score:.2f} / 1.00",
        f"  Conclusion    : {b.conclusion.value.upper()}",
        "",
    ]

    if b.warnings:
        lines.append("  WARNINGS")
        for w in b.warnings:
            lines.append(f"    ⚠  {w}")
        lines.append("")

    if b.effect_reports:
        lines.append("  FINDINGS  (sorted by stability)")
        for r in sorted(b.effect_reports, key=lambda x: -x.stability):
            lines.append("")
            for ln in r.label().split("\n"):
                lines.append("    " + ln)
        lines.append("")

    lines.append("  SUMMARY")
    for ln in b.summary.split("\n"):
        lines.append("  " + ln)

    return "\n".join(lines) + "\n"


# ── Cross-run aggregation ─────────────────────────────────────────────────────

def save_findings_csv(bundles: list["ResultsBundle"], run_id: str) -> Path:
    """Write all EffectReports across all diagnostics to a single CSV."""
    rows = []
    for b in bundles:
        for r in b.effect_reports:
            rows.append({
                "diagnostic_id": b.diagnostic_id,
                "conclusion":    b.conclusion.value,
                "stability_score": b.stability_score,
                "finding":       r.finding,
                "condition":     r.condition,
                "baseline":      r.baseline,
                "effect_value":  r.effect_value,
                "delta":         r.effect_value - r.baseline,
                "ci_lower":      r.ci_lower,
                "ci_upper":      r.ci_upper,
                "p_perm":        r.p_perm,
                "p_adj":         r.p_adj,
                "effect_d":      r.effect_d,
                "stability":     r.stability,
                "n_obs":         r.n_obs,
                "recommendation":r.recommendation,
            })

    out_dir = OUTPUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "findings.csv"
    pd.DataFrame(rows).sort_values("stability", ascending=False).to_csv(
        path, index=False
    )
    return path


def save_negative_findings(bundles: list["ResultsBundle"], run_id: str) -> Path:
    """Write a markdown log of all negative/null/inconclusive conclusions."""
    from research.diagnostics.base import Conclusion
    lines = [
        "# Negative Findings Log",
        f"Run: {run_id}",
        "",
        "All hypotheses that were tested and did NOT produce actionable findings.",
        "Prevents re-testing known dead ends.",
        "",
        "---",
        "",
    ]
    for b in bundles:
        if b.conclusion in (Conclusion.NEGATIVE, Conclusion.NULL,
                            Conclusion.INCONCLUSIVE):
            lines += [
                f"## {b.diagnostic_id.upper()} — {b.conclusion.value.upper()}",
                f"**Hypothesis:** {b.hypothesis}",
                f"**Sample:** {b.sample_size:,}  "
                f"**Stability:** {b.stability_score:.2f}",
                "",
            ]
            for r in b.effect_reports:
                delta = r.effect_value - r.baseline
                lines.append(
                    f"- {r.finding}: effect={delta:+.1%}  "
                    f"CI=[{r.ci_lower:.1%}, {r.ci_upper:.1%}]  "
                    f"p={r.p_adj:.3f}  → **{r.recommendation}**"
                )
            lines.append("")

    out_dir = OUTPUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "negative_findings.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
