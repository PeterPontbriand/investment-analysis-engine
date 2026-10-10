"""The Momentum ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from datetime import date
from typing import Final

from src.core.constants import TrendStatus
from src.data.financial.provenance import SourceKind
from src.reporting.documents.shared_parts import DocumentPart, MetricResultPart
from src.reporting.documents.strategy_document import StrategyDocumentHeader, StrategyDocumentTail
from src.reporting.documents.timestamp import DocumentTimestamp
from src.strategies.momentum.vocabulary import AnalysisId, CrossoverState, MethodId, PriceBasis, TrendRelationship

DOCUMENT_SCHEMA_VERSION: Final = 7


class MomentumResultPart(DocumentPart):
    """The computed trend and metrics; each metric is null when the available history cannot support it.

    ``trend`` is the verdict (``UNKNOWN`` when the history cannot support both moving averages), never the
    document's ``status``, which says only that the calculation ran.
    """

    trend: TrendStatus
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


class MomentumBody(DocumentPart):
    """The keys only the Momentum document writes."""

    result: MomentumResultPart
    parameters: MomentumParametersPart
    source: MomentumSourcePart
    data_resolution: MomentumDataResolutionPart | None


class MomentumDocument(StrategyDocumentTail, MomentumBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The Momentum document, version 7, as ``momentum --json`` and ``runs show --json`` write it.

    The shared header and tail come from :mod:`src.reporting.documents.strategy_document`.
    """


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "MomentumBody",
    "MomentumDataResolutionPart",
    "MomentumDocument",
    "MomentumParametersPart",
    "MomentumResultPart",
    "MomentumSourcePart",
]
