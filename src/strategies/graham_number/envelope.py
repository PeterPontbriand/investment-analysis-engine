"""The Graham Number ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from typing import Final

from src.core.analysis_status import CalculationStatus
from src.reporting.documents.shared_parts import (
    DiagnosticEntry,
    DocumentPart,
    InstrumentKindPart,
    PriceComparisonPart,
    QuotePart,
    ResolvedInputPart,
    SecurityIdentityPart,
)
from src.reporting.documents.timestamp import DocumentTimestamp
from src.strategies.graham_number.vocabulary import AnalysisId, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 6


class GrahamNumberResultPart(DocumentPart):
    """The computed ceiling; null unless the calculation succeeded."""

    maximum_indicated_price: float | None
    margin_of_safety_percent: float | None


class GrahamNumberInputsPart(DocumentPart):
    """The inputs the method needs, each null when it could not be resolved."""

    eps: ResolvedInputPart | None
    bvps: ResolvedInputPart | None
    current_price: ResolvedInputPart | None


class GrahamNumberDocument(DocumentPart):
    """The Graham Number document, version 6, as ``graham-number --json`` and ``runs show --json`` write it."""

    schema_version: int
    price_comparison: PriceComparisonPart | None
    analysis: AnalysisId
    ticker: str
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None
    method: MethodId
    as_of: DocumentTimestamp | None
    status: CalculationStatus
    reason: str | None
    result: GrahamNumberResultPart
    inputs: GrahamNumberInputsPart
    quote: QuotePart
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    diagnostics: tuple[DiagnosticEntry, ...]


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "GrahamNumberDocument",
    "GrahamNumberInputsPart",
    "GrahamNumberResultPart",
]
