"""Public contracts for graham_number."""

from __future__ import annotations

from src.analysis.shared.graham_contracts import GrahamMethod
from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberInputResolver,
    GrahamNumberResult,
    compute_graham_number,
)
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis, run_graham_number_analysis
from src.core.analysis_status import CalculationStatus

__all__ = [
    "CalculationStatus",
    "GrahamMethod",
    "GrahamNumberConfig",
    "GrahamNumberAnalyzer",
    "GrahamNumberInputAssembly",
    "GrahamNumberResult",
    "GrahamNumberInputResolver",
    "GrahamNumberAnalysis",
    "compute_graham_number",
    "run_graham_number_analysis",
]
