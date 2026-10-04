"""Free Cash Flow & Earnings Growth's production analysis-tool arguments."""

from __future__ import annotations

from pydantic import field_validator

from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.strategies.fcf_growth.models import FCFClassificationBasis, ForwardPolicy, HistoricalHorizon


class FCFEarningsGrowthToolArguments(AnalysisToolArguments):
    """Validated arguments for Free Cash Flow & Earnings Growth analysis."""

    historical_horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE
    classification_basis: FCFClassificationBasis = FCFClassificationBasis.TOTAL_FCF
    forward_policy: ForwardPolicy = ForwardPolicy.DISPLAY_ONLY
    include_fcf_yield: bool = True
    currency: str = "USD"
    use_cache: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize and require a non-empty currency identifier."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("currency must be a non-empty string.")
        return normalized
