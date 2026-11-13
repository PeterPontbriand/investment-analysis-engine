"""The Graham Number ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay, which write the same document.
"""

from typing import Final, Self

from pydantic import model_validator

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.reporting.documents.shared_parts import (
    DocumentPart,
    LeftOutYearPart,
    PriceComparisonPart,
    QuotePart,
    ResolvedInputPart,
)
from investment_analysis_engine.reporting.documents.strategy_document import (
    StrategyDocumentHeader,
    StrategyDocumentTail,
)
from investment_analysis_engine.strategies.graham_number.vocabulary import AnalysisId, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 12


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
    reason_code: ReasonCode | None
    reason: str | None
    result: GrahamNumberResultPart
    inputs: GrahamNumberInputsPart
    left_out_years: tuple[LeftOutYearPart, ...]
    quote: QuotePart


class GrahamNumberDocument(StrategyDocumentTail, GrahamNumberBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The Graham Number document, version 12, as ``graham-number --json`` and ``runs show --json`` write it.

    The shared header and tail come from :mod:`investment_analysis_engine.reporting.documents.strategy_document`.
    """

    @model_validator(mode="after")
    def _check_reason_code_follows_status(self) -> Self:
        """Require ``reason_code`` to be null exactly when ``status`` is ``ok``."""
        if (self.reason_code is None) is (self.status is not CalculationStatus.OK):
            raise ValueError("reason_code is null exactly when status is ok.")
        return self


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "GrahamNumberBody",
    "GrahamNumberDocument",
    "GrahamNumberInputsPart",
    "GrahamNumberResultPart",
]
