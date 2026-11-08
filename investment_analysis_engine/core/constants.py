"""
Centralized domain constants.

This module provides strongly-typed constants for financial data agents, including:
- Market trend status vectors
- Standardized DataFrame column definitions

Classes:
    TrendStatus(str, Enum): Strongly-typed market trend indicators.
    DataColumns: Standardized pandas DataFrame column definitions.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class TrendStatus(StrEnum):
    """
    Strongly-typed market trend indicators.

    Attributes:
        BULLISH: Bullish market trend.
        BEARISH: Bearish market trend.
        UNKNOWN: Unknown or neutral market state.

    """

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    UNKNOWN = "UNKNOWN"

    def display_name(self) -> str:
        """
        Return the English display name of the trend status.

        Returns:
            The English name: "Bullish Trend", "Bearish Trend" or "Unknown State".

        """
        return _DISPLAY_NAMES[self.value]


_DISPLAY_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        TrendStatus.BULLISH.value: "Bullish Trend",
        TrendStatus.BEARISH.value: "Bearish Trend",
        TrendStatus.UNKNOWN.value: "Unknown State",
    }
)


class DataColumns:
    """
    Standardized DataFrame column definitions for schema validation.

    Attributes:
        CLOSE: Closing price column.

    """

    CLOSE: Final[str] = "Close"


TREND_STATUS_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        TrendStatus.BULLISH.value: "trend-bullish",
        TrendStatus.BEARISH.value: "trend-bearish",
        TrendStatus.UNKNOWN.value: "trend-unknown",
    }
)
"""The glossary term that explains each trend status; each value has its own entry."""
