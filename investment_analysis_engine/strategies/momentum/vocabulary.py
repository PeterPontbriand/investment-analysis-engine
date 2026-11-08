"""Momentum's vocabulary: its names, its stored-configuration version and its shared enumerations.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. The price basis,
trend relationship and crossover state are the values its presenter derives and its document writes.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

AnalysisId = Literal["momentum"]
MethodId = Literal["sma_crossover"]

ANALYSIS_ID: Final[AnalysisId] = "momentum"
METHOD_ID: Final[MethodId] = "sma_crossover"

ConfigSchemaVersion = Literal[2]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 2


class PriceBasis(StrEnum):
    """Which close the current price is."""

    LATEST_ADJUSTED_HISTORICAL_CLOSE = "latest_adjusted_historical_close"
    LATEST_HISTORICAL_CLOSE = "latest_historical_close"


class TrendRelationship(StrEnum):
    """How the short moving average stands against the long one."""

    SHORT_ABOVE_LONG = "short_above_long"
    SHORT_BELOW_LONG = "short_below_long"
    SHORT_EQUAL_LONG = "short_equal_long"


class CrossoverState(StrEnum):
    """What the latest crossover signal says."""

    BULLISH_CROSSOVER = "bullish_crossover"
    BEARISH_CROSSOVER = "bearish_crossover"
    NO_NEW_CROSSOVER = "no_new_crossover"


HEADLINE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "trend": "momentum-states",
        "rsi": "rsi",
    }
)
"""The glossary term that explains the label of each headline cell, by the cell's key."""

CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "PriceBasis": MappingProxyType(
            {
                PriceBasis.LATEST_ADJUSTED_HISTORICAL_CLOSE.value: "price-basis",
                PriceBasis.LATEST_HISTORICAL_CLOSE.value: "price-basis",
            }
        ),
        "TrendRelationship": MappingProxyType(
            {
                TrendRelationship.SHORT_ABOVE_LONG.value: "trend-relationship",
                TrendRelationship.SHORT_BELOW_LONG.value: "trend-relationship",
                TrendRelationship.SHORT_EQUAL_LONG.value: "trend-relationship",
            }
        ),
        "CrossoverState": MappingProxyType(
            {
                CrossoverState.BULLISH_CROSSOVER.value: "crossover-bullish",
                CrossoverState.BEARISH_CROSSOVER.value: "crossover-bearish",
                CrossoverState.NO_NEW_CROSSOVER.value: "crossover-none",
            }
        ),
    }
)
"""The glossary term that explains each value of each code set this strategy defines, by the name of the OpenAPI
component that carries it."""
