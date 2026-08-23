"""Analysis modules for Graham valuation methods.

Public exports for the pure calculation layer (Slice B):

- ``GrahamMethod`` — method discriminator enum.
- ``CalculationStatus`` — shared status enum (all five statuses).
- ``GrahamNumberResult`` — typed result for the Graham Number method.
- ``GrahamGrowthValueResult`` — typed result for the growth-value method.
- ``compute_graham_number`` — pure Graham Number calculator.
- ``compute_graham_growth_value`` — pure growth-value calculator.
"""

from src.analysis.graham_value.calculators import compute_graham_growth_value, compute_graham_number
from src.analysis.graham_value.models import (
    CalculationStatus,
    GrahamGrowthValueResult,
    GrahamMethod,
    GrahamNumberResult,
)

__all__ = [
    "CalculationStatus",
    "GrahamGrowthValueResult",
    "GrahamMethod",
    "GrahamNumberResult",
    "compute_graham_growth_value",
    "compute_graham_number",
]
