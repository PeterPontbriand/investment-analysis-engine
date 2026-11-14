"""The Piotroski F-Score strategy's ``--json`` document.

It holds the document version and the typed model. The document is the complete result plus the shared header and
tail: the nine tests with their ratios and operands, the score, the industry class and the failure
that stopped a run. The identifiers and enumerations it writes come from the strategy's ``vocabulary.py`` and the
calculation.
"""

from datetime import date
from typing import Final

from investment_analysis_engine.analysis.shared.applicability import IndustryClass
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.reporting.documents.shared_parts import (
    DocumentPart,
    MetricResultPart,
    ResolvedInputPart,
)
from investment_analysis_engine.reporting.documents.strategy_document import (
    StrategyDocumentHeader,
    StrategyDocumentTail,
)
from investment_analysis_engine.strategies.piotroski.vocabulary import AnalysisId, CheckOutcome, Completeness, MethodId

DOCUMENT_SCHEMA_VERSION: Final = 4


class PiotroskiOperandPart(DocumentPart):
    """One input a test used, under the name the test gives it, with its provenance."""

    name: str
    input: ResolvedInputPart


class PiotroskiRatioPart(DocumentPart):
    """One ratio a test compared, under the name the test gives it."""

    name: str
    result: MetricResultPart


class PiotroskiTestPart(DocumentPart):
    """One of the nine tests: its outcome, the ratios and operands behind it, and why it is unavailable."""

    number: int
    name: str
    group: str
    outcome: CheckOutcome
    ratios: tuple[PiotroskiRatioPart, ...]
    operands: tuple[PiotroskiOperandPart, ...]
    diagnostics: tuple[str, ...]
    reason_code: ReasonCode | None
    reason: str | None


class PiotroskiSourceFilingPart(DocumentPart):
    """A filing an operand came from and its filing date."""

    accession: str
    filing_date: date


class PiotroskiUnavailablePart(DocumentPart):
    """Why a value is unavailable."""

    reason_code: ReasonCode
    reason: str


class PiotroskiInputFailurePart(DocumentPart):
    """The input whose provider failure stopped the assembly, and the explanation."""

    input_name: str
    reason: str


class PiotroskiBody(DocumentPart):
    """The keys only the Piotroski F-Score document writes."""

    result_schema_version: int
    method_version: int
    reason_code: ReasonCode | None
    reason: str | None
    industry_class: IndustryClass | None
    industry_class_unknown: PiotroskiUnavailablePart | None
    source_filings: tuple[PiotroskiSourceFilingPart, ...]
    taxonomy: str | None
    score: MetricResultPart | None
    completeness: Completeness | None
    available_count: int | None
    unavailable_tests: tuple[int, ...]
    tests: tuple[PiotroskiTestPart, ...]
    input_failure: PiotroskiInputFailurePart | None


class PiotroskiDocument(StrategyDocumentTail, PiotroskiBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The Piotroski F-Score document, version 1.

    ``piotroski --json`` and a replay write it.
    """
