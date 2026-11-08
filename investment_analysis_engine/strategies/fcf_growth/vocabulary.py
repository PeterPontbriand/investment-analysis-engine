"""FCF Growth's vocabulary: its names, its stored-configuration version and its shared enumerations.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. The six
enumerations are the values its policy, classification and forward evidence take.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

AnalysisId = Literal["fcf_earnings_growth"]
MethodId = Literal["reported_fcf_eps_cagr"]

ANALYSIS_ID: Final[AnalysisId] = "fcf_earnings_growth"
METHOD_ID: Final[MethodId] = "reported_fcf_eps_cagr"

ConfigSchemaVersion = Literal[3]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 3


class HistoricalHorizon(StrEnum):
    """Requested historical elapsed-year horizon for classification."""

    LONGEST_AVAILABLE = "longest_available"
    THREE_YEARS = "3"
    FOUR_YEARS = "4"
    FIVE_YEARS = "5"


class ForwardPolicy(StrEnum):
    """How forward consensus evidence affects the headline result."""

    DISPLAY_ONLY = "display_only"
    CONFIRMATION = "confirmation"
    HARD_GATE = "hard_gate"


class FCFClassificationBasis(StrEnum):
    """Free-cash-flow measure controlling classification."""

    TOTAL_FCF = "total_fcf"
    FCF_PER_SHARE = "fcf_per_share"


class Classification(StrEnum):
    """Headline historical screening conclusion."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class TrendClassification(StrEnum):
    """Historical relationship between FCF and earnings growth (evidence, not a score)."""

    BOTH_GROWING = "both_growing"
    FCF_GROWING_EARNINGS_NOT = "fcf_growing_earnings_not"
    EARNINGS_GROWING_FCF_NOT = "earnings_growing_fcf_not"
    NEITHER_GROWING = "neither_growing"
    INSUFFICIENT_OR_NONMEANINGFUL_GROWTH = "insufficient_or_nonmeaningful_growth"


class ForwardEvidenceStatus(StrEnum):
    """Completeness of the forward consensus evidence block."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


HEADLINE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "fcf_cagr": "cagr",
        "eps_cagr": "cagr",
        "classification": "fcf-classification",
    }
)
"""The glossary term that explains the label of each headline cell, by the cell's key."""

CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "Classification": MappingProxyType(
            {
                Classification.PASS.value: "fcf-classification",
                Classification.FAIL.value: "fcf-classification",
                Classification.INDETERMINATE.value: "fcf-classification",
            }
        ),
        "ForwardEvidenceStatus": MappingProxyType(
            {
                ForwardEvidenceStatus.COMPLETE.value: "forward-evidence-status",
                ForwardEvidenceStatus.PARTIAL.value: "forward-evidence-status",
                ForwardEvidenceStatus.UNAVAILABLE.value: "forward-evidence-status",
            }
        ),
        "HistoricalHorizon": MappingProxyType(
            {
                HistoricalHorizon.LONGEST_AVAILABLE.value: "historical-horizon",
                HistoricalHorizon.THREE_YEARS.value: "historical-horizon",
                HistoricalHorizon.FOUR_YEARS.value: "historical-horizon",
                HistoricalHorizon.FIVE_YEARS.value: "historical-horizon",
            }
        ),
        "FCFGrowthSelection.HistoricalHorizon": MappingProxyType(
            {
                HistoricalHorizon.LONGEST_AVAILABLE.value: "historical-horizon",
                HistoricalHorizon.THREE_YEARS.value: "historical-horizon",
                HistoricalHorizon.FOUR_YEARS.value: "historical-horizon",
                HistoricalHorizon.FIVE_YEARS.value: "historical-horizon",
            }
        ),
        "ForwardPolicy": MappingProxyType(
            {
                ForwardPolicy.DISPLAY_ONLY.value: "forward-policy",
                ForwardPolicy.CONFIRMATION.value: "forward-policy",
                ForwardPolicy.HARD_GATE.value: "forward-policy",
            }
        ),
        "FCFGrowthSelection.ForwardPolicy": MappingProxyType(
            {
                ForwardPolicy.DISPLAY_ONLY.value: "forward-policy",
                ForwardPolicy.CONFIRMATION.value: "forward-policy",
                ForwardPolicy.HARD_GATE.value: "forward-policy",
            }
        ),
        "FCFClassificationBasis": MappingProxyType(
            {
                FCFClassificationBasis.TOTAL_FCF.value: "classification-basis",
                FCFClassificationBasis.FCF_PER_SHARE.value: "classification-basis",
            }
        ),
        "FCFGrowthSelection.FCFClassificationBasis": MappingProxyType(
            {
                FCFClassificationBasis.TOTAL_FCF.value: "classification-basis",
                FCFClassificationBasis.FCF_PER_SHARE.value: "classification-basis",
            }
        ),
        "TrendClassification": MappingProxyType(
            {
                TrendClassification.BOTH_GROWING.value: "growth-trend",
                TrendClassification.FCF_GROWING_EARNINGS_NOT.value: "growth-trend",
                TrendClassification.EARNINGS_GROWING_FCF_NOT.value: "growth-trend",
                TrendClassification.NEITHER_GROWING.value: "growth-trend",
                TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH.value: "growth-trend",
            }
        ),
    }
)
"""The glossary term that explains each value of each code set this strategy defines, by the name of the OpenAPI
component that carries it."""
