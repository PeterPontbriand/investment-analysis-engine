"""FCF Growth's vocabulary: the identifiers and enumerations more than one of its files needs.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. The six
enumerations are the values its policy, classification and forward evidence take.
"""

from enum import StrEnum
from typing import Final, Literal

AnalysisId = Literal["fcf_earnings_growth"]
MethodId = Literal["reported_fcf_eps_cagr"]

ANALYSIS_ID: Final[AnalysisId] = "fcf_earnings_growth"
METHOD_ID: Final[MethodId] = "reported_fcf_eps_cagr"


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
