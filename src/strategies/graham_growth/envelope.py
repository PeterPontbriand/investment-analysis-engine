"""The Graham Growth ``--json`` document: its identity constants, version and typed model.

This is the strategy's identity leaf: it imports no other Graham Growth module, so the presenter writes the
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

ANALYSIS_ID: Final = "graham_growth_value"
METHOD_ID: Final = "graham_growth_value"
DOCUMENT_SCHEMA_VERSION: Final = 6


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


class GrahamGrowthDocument(DocumentPart):
    """The Graham Growth document, version 6, as ``graham-growth --json`` and ``runs show --json`` write it."""

    schema_version: int
    price_comparison: PriceComparisonPart | None
    analysis: Literal["graham_growth_value"]
    ticker: str
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None
    method: Literal["graham_growth_value"]
    as_of: DocumentTimestamp | None
    status: CalculationStatus
    reason: str | None
    result: GrahamGrowthResultPart
    inputs: GrahamGrowthInputsPart
    method_assumptions: GrahamGrowthAssumptionsPart
    quote: QuotePart
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    diagnostics: tuple[DiagnosticEntry, ...]


__all__ = [
    "ANALYSIS_ID",
    "DOCUMENT_SCHEMA_VERSION",
    "METHOD_ID",
    "GrahamGrowthAssumptionsPart",
    "GrahamGrowthDocument",
    "GrahamGrowthInputsPart",
    "GrahamGrowthResultPart",
]
