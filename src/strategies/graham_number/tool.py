"""Graham Number's production analysis-tool arguments."""

from __future__ import annotations

from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments, FiniteFloat
from src.strategies.graham_number.config import GrahamNumberEPSBasis


class GrahamNumberToolArguments(AnalysisToolArguments):
    """Validated arguments for Graham Number analysis."""

    eps_basis: GrahamNumberEPSBasis = "three_year_average"
    eps_override: FiniteFloat | None = None
    bvps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True
