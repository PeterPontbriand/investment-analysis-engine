"""Public contracts for graham_growth."""

from __future__ import annotations

from src.analysis.shared.graham_contracts import GrahamMethod
from src.analysis.strategy.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
    compute_graham_growth_value,
)
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis, run_graham_growth_analysis
from src.core.analysis_status import CalculationStatus

__all__ = [
    "CalculationStatus",
    "GrahamMethod",
    "GrahamGrowthConfig",
    "GrahamGrowthAnalyzer",
    "GrowthValueInputAssembly",
    "GrahamGrowthValueResult",
    "GrahamGrowthInputResolver",
    "GrahamGrowthAnalysis",
    "compute_graham_growth_value",
    "run_graham_growth_analysis",
    "GrahamGrowthCalculationPolicy",
]
