"""The Graham Number ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from typing import Final

from src.reporting.documents.shared_parts import DocumentPart, PriceComparisonPart, QuotePart, ResolvedInputPart
from src.reporting.documents.strategy_document import StrategyDocumentHeader, StrategyDocumentTail
from src.strategies.graham_number.vocabulary import AnalysisId, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 7


class GrahamNumberResultPart(DocumentPart):
    """The computed ceiling; null unless the calculation succeeded."""

    maximum_indicated_price: float | None
    margin_of_safety_percent: float | None


class GrahamNumberInputsPart(DocumentPart):
    """The inputs the method needs, each null when it could not be resolved."""

    eps: ResolvedInputPart | None
    bvps: ResolvedInputPart | None
    current_price: ResolvedInputPart | None


class GrahamNumberBody(DocumentPart):
    """The keys only the Graham Number document writes."""

    price_comparison: PriceComparisonPart | None
    reason: str | None
    result: GrahamNumberResultPart
    inputs: GrahamNumberInputsPart
    quote: QuotePart


class GrahamNumberDocument(StrategyDocumentTail, GrahamNumberBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The Graham Number document, version 7, as ``graham-number --json`` and ``runs show --json`` write it.

    The shared header and tail come from :mod:`src.reporting.documents.strategy_document`.
    """


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "GrahamNumberBody",
    "GrahamNumberDocument",
    "GrahamNumberInputsPart",
    "GrahamNumberResultPart",
]
