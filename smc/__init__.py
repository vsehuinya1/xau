"""SMC signal engine — Phase 1."""
from smc.loader import load, DataStore, BarData
from smc.structure import compute_structure, StructureArrays
from smc.fvg import compute_fvgs, FVGArrays
from smc.regime import compute_regime, RegimeArrays, RegimeParams
from smc.confluence import run_simulation, StrategyParams, ExecutionParams, Trade

__all__ = [
    "load", "DataStore", "BarData",
    "compute_structure", "StructureArrays",
    "compute_fvgs", "FVGArrays",
    "compute_regime", "RegimeArrays", "RegimeParams",
    "run_simulation", "StrategyParams", "ExecutionParams", "Trade",
]
