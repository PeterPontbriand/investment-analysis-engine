"""The specimen's presenter: the four presentation modes, from the evidence alone."""

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.reporting.documents.shared_parts import SecurityIdentityPart
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.presentation import PresentationMode
from tests.specimen.analyzer import SpecimenResult
from tests.specimen.envelope import DOCUMENT_SCHEMA_VERSION, SpecimenDocument, SpecimenResultPart
from tests.specimen.vocabulary import ANALYSIS_ID, METHOD_ID


def specimen_document(result: SpecimenResult) -> SpecimenDocument:
    """Build the typed document of one specimen result."""
    return SpecimenDocument(
        schema_version=DOCUMENT_SCHEMA_VERSION,
        analysis=ANALYSIS_ID,
        method=METHOD_ID,
        ticker=result.ticker,
        status=CalculationStatus.OK,
        provider_failure=None,
        provider_check=None,
        requested_as_of=None,
        effective_as_of=result.effective_as_of,
        security_identity=SecurityIdentityPart(
            ticker=result.ticker,
            instrument_name=None,
            listing_venue=None,
            issuer_identifier=None,
            instrument_identifier=None,
            provider_id=None,
            resolved_at=None,
        ),
        instrument_kind=None,
        result=SpecimenResultPart(value=result.value, multiplier=result.multiplier, scaled=result.scaled),
        warnings=(),
        limitations=(),
        diagnostics=(),
    )


def render_specimen(result: SpecimenResult, mode: PresentationMode = PresentationMode.CONCISE) -> str:
    """Render one specimen result in ``mode``."""
    if mode is PresentationMode.JSON:
        return strategy_document_json(specimen_document(result))
    lines = [f"{result.ticker} specimen value: {result.scaled}"]
    if mode in {PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS}:
        lines.append(f"Input value: {result.value}; multiplier: {result.multiplier}")
    if mode is PresentationMode.DIAGNOSTICS:
        lines.append(f"Effective as of: {result.effective_as_of.isoformat()}")
    return "\n".join(lines)
