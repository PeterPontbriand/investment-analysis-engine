"""The Momentum ``--json`` document: its identity constants, version and typed model.

This is the strategy's identity leaf: it imports no other Momentum module, so the presenter writes the
identifiers from here and the conformance tests compare them with the selection class's own declaration.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from datetime import date
from typing import Final, Literal

from src.core.constants import TrendStatus
from src.data.financial.provenance import SourceKind
from src.reporting.documents.shared_parts import (
    DiagnosticEntry,
    DocumentPart,
    InstrumentKindPart,
    MetricResultPart,
    SecurityIdentityPart,
)
from src.reporting.documents.timestamp import DocumentTimestamp

ANALYSIS_ID: Final = "momentum"
METHOD_ID: Final = "sma_crossover"
DOCUMENT_SCHEMA_VERSION: Final = 5

PriceBasis = Literal["latest_adjusted_historical_close", "latest_historical_close"]
TrendRelationship = Literal["short_above_long", "short_below_long", "short_equal_long"]
CrossoverState = Literal["bullish_crossover", "bearish_crossover", "no_new_crossover"]


class MomentumResultPart(DocumentPart):
    """The computed trend metrics; each is null when the available history cannot support it."""

    current_price: float
    price_basis: PriceBasis
    short_sma: float | None
    long_sma: float | None
    sma_spread: float | None
    sma_spread_percent: float | None
    trend_relationship: TrendRelationship | None
    crossover_signal: float | None
    crossover_result: MetricResultPart | None
    crossover_state: CrossoverState | None
    rsi: MetricResultPart


class MomentumParametersPart(DocumentPart):
    """The windows and period the analysis used."""

    short_window: int
    long_window: int
    rsi_period: int


class MomentumSourcePart(DocumentPart):
    """What the historical market data said about itself; every field is null when it said nothing."""

    provider: str | None
    data_as_of: date | None
    interval: str | None
    observation_count: int | None
    currency: str | None
    price_adjustment: str | None


class MomentumDataResolutionPart(DocumentPart):
    """Where the historical series came from at execution time."""

    source_kind: SourceKind
    retrieved_at: DocumentTimestamp | None
    cached_at: DocumentTimestamp | None
    resolved_at: DocumentTimestamp
    cache_schema_version: int | None


class MomentumDocument(DocumentPart):
    """The Momentum document, version 5, as ``momentum --json`` and ``runs show --json`` write it."""

    schema_version: int
    analysis: Literal["momentum"]
    ticker: str
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None
    method: Literal["sma_crossover"]
    as_of: date | None
    analysis_timestamp: DocumentTimestamp
    status: TrendStatus
    result: MomentumResultPart
    parameters: MomentumParametersPart
    source: MomentumSourcePart
    warnings: tuple[str, ...]
    data_resolution: MomentumDataResolutionPart | None
    limitations: tuple[str, ...]
    diagnostics: tuple[DiagnosticEntry, ...]


__all__ = [
    "ANALYSIS_ID",
    "DOCUMENT_SCHEMA_VERSION",
    "METHOD_ID",
    "CrossoverState",
    "MomentumDataResolutionPart",
    "MomentumDocument",
    "MomentumParametersPart",
    "MomentumResultPart",
    "MomentumSourcePart",
    "PriceBasis",
    "TrendRelationship",
]
