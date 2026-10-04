"""Graham growth-value's production analysis-tool arguments."""

from __future__ import annotations

from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments, FiniteFloat, PositiveFiniteFloat
from src.strategies.graham_growth.config import GrahamGrowthEPSBasis


class GrahamGrowthValueToolArguments(AnalysisToolArguments):
    """Validated arguments for Graham growth-value analysis."""

    eps_basis: GrahamGrowthEPSBasis = "three_year_average"
    expected_growth: FiniteFloat
    current_aaa_yield: PositiveFiniteFloat
    eps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True
