"""The Graham Number ``--json`` document: its identity constants, version and typed model.

This is the strategy's identity leaf: it imports no other Graham Number module, so the presenter writes the
identifiers from here and the conformance tests compare them with the selection class's own declaration.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from typing import Final, Literal

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

ANALYSIS_ID: Final = "graham_number"
METHOD_ID: Final = "graham_number"
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
    analysis: Literal["graham_number"]
    ticker: str
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None
    method: Literal["graham_number"]
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
    "ANALYSIS_ID",
    "DOCUMENT_SCHEMA_VERSION",
    "METHOD_ID",
    "GrahamNumberDocument",
    "GrahamNumberInputsPart",
    "GrahamNumberResultPart",
]
