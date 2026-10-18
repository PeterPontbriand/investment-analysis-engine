"""The specimen's ``--json`` document: its version and typed model."""

from typing import Final

from investment_analysis_engine.reporting.documents.shared_parts import DocumentPart
from investment_analysis_engine.reporting.documents.strategy_document import (
    StrategyDocumentHeader,
    StrategyDocumentTail,
)
from tests.specimen.vocabulary import AnalysisId, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 1


class SpecimenResultPart(DocumentPart):
    """The computed value, its input and the multiplier applied."""

    value: float
    multiplier: float
    scaled: float


class SpecimenBody(DocumentPart):
    """The keys only the specimen document writes."""

    result: SpecimenResultPart


class SpecimenDocument(StrategyDocumentTail, SpecimenBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The specimen document, as ``specimen-test --json`` and a replay write it."""
