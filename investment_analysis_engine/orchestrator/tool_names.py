"""Approved production analysis-tool identifiers."""

from enum import StrEnum


class ToolName(StrEnum):
    """Approved production analysis-tool identifiers."""

    ANALYZE_MOMENTUM = "analyze_momentum"
    ANALYZE_GRAHAM_NUMBER = "analyze_graham_number"
    ANALYZE_GRAHAM_GROWTH_VALUE = "analyze_graham_growth_value"
    ANALYZE_FCF_EARNINGS_GROWTH = "analyze_fcf_earnings_growth"
