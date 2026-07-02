#!/usr/bin/env python3
"""
research/runner.py — CLI entry point for the Market Diagnostics Framework.

Usage
-----
  # Run everything
  python research/runner.py --all --start 2018 --end 2025

  # Run specific diagnostics
  python research/runner.py --id d01,d04,d11

  # Run by tag
  python research/runner.py --tag sessions

  # Run with custom config (overrides defaults)
  python research/runner.py --id d02 --config config/d02.yaml

  # List all registered diagnostics
  python research/runner.py --list

Output
------
  research/output/<run_id>/
    d01.txt, d01.json, …
    findings.csv         — all EffectReports sorted by stability
    negative_findings.md — null/negative/inconclusive results
    feature_store/<tag>.parquet — assembled feature table
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

# Import all diagnostics (fires @register_diagnostic decorators)
import research  # noqa: F401 — side-effect import

from research.diagnostics.registry import (
    all_diagnostics, get_by_tag, get_diagnostic, list_diagnostics
)
from research.diagnostics.base import DiagnosticConfig
from research.data.proxy import build_data_proxy
from research.features.builder import FeatureTableBuilder
from research.reports.output import save_bundle, save_findings_csv, save_negative_findings
from smc.loader import load


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="XAUUSD Market Diagnostics Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all",  action="store_true", help="Run all registered diagnostics")
    g.add_argument("--id",   type=str, help="Comma-separated diagnostic IDs, e.g. d01,d04")
    g.add_argument("--tag",  type=str, help="Run all diagnostics with this tag, e.g. sessions")
    g.add_argument("--list", action="store_true", help="List all registered diagnostics and exit")

    p.add_argument("--start",   type=int, default=2018, help="Start year (default 2018)")
    p.add_argument("--end",     type=int, default=2025, help="End year (default 2025)")
    p.add_argument("--config",  type=str, default=None, help="YAML config file (optional)")
    p.add_argument("--workers", type=int, default=1,    help="Parallel workers (future use)")
    p.add_argument("--no-cache",action="store_true",    help="Disable intermediate caching")
    p.add_argument("--run-id",  type=str, default=None, help="Output run ID (default: timestamp)")
    p.add_argument("--features-tag", type=str, default="xauusd",
                   help="Tag for feature table parquet file")

    return p.parse_args()


def _load_config(path: str | None, extra_params: dict | None = None) -> DiagnosticConfig:
    cfg = DiagnosticConfig()
    if path:
        with open(path) as f:
            raw = yaml.safe_load(f)
        cfg.n_bootstrap    = raw.get("statistical", {}).get("n_bootstrap",    cfg.n_bootstrap)
        cfg.n_permutations = raw.get("statistical", {}).get("n_permutations", cfg.n_permutations)
        cfg.fdr_method     = raw.get("statistical", {}).get("fdr_method",     cfg.fdr_method)
        cfg.alpha          = raw.get("statistical", {}).get("alpha",          cfg.alpha)
        cfg.use_cache      = raw.get("cache",   cfg.use_cache)
        cfg.emit_features  = raw.get("emit_features", cfg.emit_features)
        cfg.params         = raw.get("parameters", {})
        if "subperiods" in raw:
            cfg.subperiods = [(s["start"], s["end"]) for s in raw["subperiods"]]
    if extra_params:
        cfg.params.update(extra_params)
    return cfg


def main() -> None:
    args     = _parse_args()
    run_id   = args.run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # ── List mode
    if args.list:
        print("\nRegistered diagnostics:\n")
        list_diagnostics()
        return

    # ── Select diagnostics to run
    if args.all:
        classes = all_diagnostics()
        # D11 always runs first (writes forward returns to feature table)
        d11_cls = next((c for c in classes if c.id == "d11"), None)
        others  = [c for c in classes if c.id != "d11"]
        classes = ([d11_cls] if d11_cls else []) + sorted(others, key=lambda c: c.id)
    elif args.id:
        classes = [get_diagnostic(did.strip()) for did in args.id.split(",")]
    elif args.tag:
        classes = get_by_tag(args.tag)
        if not classes:
            print(f"No diagnostics found with tag '{args.tag}'")
            return
    else:
        print("Specify --all, --id, --tag, or --list.  Use --help for details.")
        return

    print(f"\n{'='*60}")
    print(f"  XAUUSD Market Diagnostics Framework")
    print(f"  Run ID : {run_id}")
    print(f"  Period : {args.start}–{args.end}")
    print(f"  Diagnostics: {[c.id for c in classes]}")
    print(f"{'='*60}\n")

    # ── Load data
    print(f"Loading data {args.start}–{args.end} …")
    t0 = time.time()
    ds = load(args.start, args.end)
    print(f"  Loaded in {time.time()-t0:.1f}s  M1 bars: {len(ds.m1.ts):,}\n")

    print("Building DataProxy …")
    t0 = time.time()
    data = build_data_proxy(ds)
    print(f"  DataProxy ready in {time.time()-t0:.1f}s\n")

    # ── Feature table builder
    ft_builder = FeatureTableBuilder(len(ds.m1.ts), ds.m1.ts)

    # ── Load config
    config = _load_config(args.config)
    if args.no_cache:
        config.use_cache = False

    # ── Run diagnostics
    bundles = []
    total_t = time.time()

    for cls in classes:
        # Try per-diagnostic config file if no global config given
        if not args.config:
            cfg_path = Path("config") / f"{cls.id}.yaml"
            if cfg_path.exists():
                diag_config = _load_config(str(cfg_path))
            else:
                diag_config = DiagnosticConfig()
        else:
            diag_config = config

        t_diag = time.time()
        diag   = cls()
        try:
            bundle = diag.run(data, diag_config)
        except Exception as exc:
            print(f"  [{cls.id}] ERROR: {exc}")
            import traceback; traceback.print_exc()
            continue

        bundles.append(bundle)

        # Accumulate feature contributions
        if bundle.feature_contributions is not None and not bundle.feature_contributions.empty:
            ft_builder.add_features(bundle.feature_contributions, source=cls.id)

        save_bundle(bundle, run_id)
        elapsed = time.time() - t_diag
        print(f"  [{cls.id}] done in {elapsed:.1f}s  "
              f"conclusion={bundle.conclusion.value}  "
              f"stability={bundle.stability_score:.2f}\n")

    # ── Build & save feature table
    if bundles:
        print("Building feature table …")
        ft_builder.build(tag=args.features_tag)

    # ── Cross-run reports
    if bundles:
        findings_path = save_findings_csv(bundles, run_id)
        neg_path      = save_negative_findings(bundles, run_id)
        print(f"\n{'='*60}")
        print(f"  Run complete in {time.time()-total_t:.1f}s")
        print(f"  Diagnostics run : {len(bundles)}")
        print(f"  Findings CSV    : {findings_path}")
        print(f"  Negative log    : {neg_path}")
        print(f"  Output dir      : research/output/{run_id}/")
        print(f"{'='*60}\n")

        # ── Print top findings sorted by stability
        import pandas as pd
        findings_df = pd.read_csv(findings_path)
        actionable  = findings_df[findings_df["recommendation"] == "Actionable"]
        if not actionable.empty:
            print("  TOP ACTIONABLE FINDINGS (by stability):\n")
            for _, row in actionable.sort_values("stability", ascending=False).head(10).iterrows():
                delta = row["delta"]
                print(f"  [{row['diagnostic_id']}] {row['finding']}")
                print(f"    {row['condition']}  →  {delta:+.1%}  "
                      f"stab={row['stability']:.2f}  p={row['p_adj']:.4f}")
            print()
        else:
            print("  No actionable findings at configured thresholds.")
            print("  (Check 'Monitor' findings in findings.csv)\n")


if __name__ == "__main__":
    main()
