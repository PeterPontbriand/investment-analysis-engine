"""The Graham Growth ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from typing import Final

from src.reporting.documents.shared_parts import DocumentPart, PriceComparisonPart, QuotePart, ResolvedInputPart
from src.reporting.documents.strategy_document import StrategyDocumentHeader, StrategyDocumentTail
from src.strategies.graham_growth.vocabulary import AnalysisId, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 8


class GrahamGrowthResultPart(DocumentPart):
    """The computed value; null unless the calculation succeeded."""

    growth_value: float | None
    margin_of_safety_percent: float | None


class GrahamGrowthInputsPart(DocumentPart):
    """The inputs the method needs, each null when it could not be resolved."""

    eps: ResolvedInputPart | None
    expected_growth: ResolvedInputPart | None
    current_aaa_yield: ResolvedInputPart | None
    current_price: ResolvedInputPart | None


class GrahamGrowthAssumptionsPart(DocumentPart):
    """The method assumptions the calculation used."""

    base_pe: float
    growth_multiplier: float
    baseline_aaa_yield: float


class GrahamGrowthBody(DocumentPart):
    """The keys only the Graham Growth document writes."""

    price_comparison: PriceComparisonPart | None
    reason: str | None
    result: GrahamGrowthResultPart
    inputs: GrahamGrowthInputsPart
    method_assumptions: GrahamGrowthAssumptionsPart
    quote: QuotePart


class GrahamGrowthDocument(StrategyDocumentTail, GrahamGrowthBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The Graham Growth document, version 8, as ``graham-growth --json`` and ``runs show --json`` write it.

    The shared header and tail come from :mod:`src.reporting.documents.strategy_document`.
    """


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "GrahamGrowthAssumptionsPart",
    "GrahamGrowthBody",
    "GrahamGrowthDocument",
    "GrahamGrowthInputsPart",
    "GrahamGrowthResultPart",
]
