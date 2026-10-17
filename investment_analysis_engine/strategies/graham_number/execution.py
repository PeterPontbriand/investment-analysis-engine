"""Graham Number execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
formerly inlined in the ``_run_graham_number`` helper so both the
direct command and a future save/refresh service call identical code.
Presentation, exit-code selection, and friendly failure rendering stay in
the command (``investment_analysis_engine.strategies.graham_number.cli``); this module captures execution evidence only.

``classify_graham_number_outcome`` freezes the exact native-status mapping
required before any run is persisted: a native ``NOT_APPLICABLE`` maps to
``RunOutcome.NOT_APPLICABLE``, whether the assembly reports it (an ETF) or the
calculation does (a non-positive EPS or BVPS, which the method does not apply
to); a missing required input (``INPUT_UNAVAILABLE``) maps to
``RunOutcome.UNAVAILABLE``; an invalid input or provider error, or a
calculation that returns invalid input, maps to ``RunOutcome.FAILED``; a
completed calculation maps to ``RunOutcome.COMPLETED``.
"""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import failure_reason_code, provider_failure_of
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies._shared.profile import compose_graham_profile
from investment_analysis_engine.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class GrahamNumberCapture:
    """Captured evidence for one Graham Number command execution.

    ``analysis`` is the unmodified native analyzer result. ``profile`` is
    the exact profile associated with the analysis: the analyzer's own
    ``instrument_profile`` when it returned one, otherwise the profile
    composed before calculation — the same fallback the CLI already applies.
    ``outcome`` is the frozen status mapping described above.
    """

    analysis: GrahamNumberAnalysis
    profile: InstrumentProfile
    outcome: RunOutcome


def classify_graham_number_outcome(analysis: GrahamNumberAnalysis) -> RunOutcome:
    """Map native Graham Number status to the workspace's terminal outcome."""
    assembly_status = analysis.assembly.status
    if assembly_status is CalculationStatus.NOT_APPLICABLE:
        return RunOutcome.NOT_APPLICABLE
    if assembly_status is CalculationStatus.INPUT_UNAVAILABLE:
        return RunOutcome.UNAVAILABLE
    if assembly_status is not CalculationStatus.OK:
        return RunOutcome.FAILED
    if analysis.result.status is CalculationStatus.OK:
        return RunOutcome.COMPLETED
    if analysis.result.status is CalculationStatus.NOT_APPLICABLE:
        return RunOutcome.NOT_APPLICABLE
    return RunOutcome.FAILED


def execute_graham_number(  # noqa: PLR0913
    resolver: GrahamNumberInputResolver,
    ticker: str,
    config: GrahamNumberConfig,
    profile_provider: object,
    *,
    as_of: datetime | None,
    executed_at: datetime,
    use_cache: bool,
    profile_cache: InstrumentProfileResolver | None = None,
) -> GrahamNumberCapture:
    """Compose the profile and run the existing Graham Number analyzer.

    Args:
        resolver: A borrowed, already-composed input resolver.
        ticker: The normalized target ticker.
        config: The validated Graham Number configuration.
        profile_provider: The Yahoo-identity candidate source, exactly as
            the CLI supplies it today.
        as_of: The requested point-in-time boundary, or None.
        executed_at: The run's own execution clock, a single aware read of
            "now" taken once by the caller.
        use_cache: Whether resolved-input caching is enabled for this run.
        profile_cache: When supplied, resolves the profile through the
            durable P2-Profiles cache instead of composing live every call.

    Returns:
        The captured native analysis, its associated profile, and the
        mapped terminal outcome.
    """
    composed_profile = compose_graham_profile(
        ticker,
        primary_provider=resolver.provider,
        primary_provider_id=config.security_provider_id,
        yahoo_provider=profile_provider,
        profile_cache=profile_cache,
    )
    context = AnalysisContext(
        as_of=as_of, executed_at=executed_at, use_cache=use_cache, instrument_profile=composed_profile
    )
    analysis = GrahamNumberAnalyzer(resolver).run_analysis(ticker, config, context)
    profile = analysis.instrument_profile or composed_profile
    return GrahamNumberCapture(analysis=analysis, profile=profile, outcome=classify_graham_number_outcome(analysis))


def capture_provider_failure(capture: GrahamNumberCapture) -> ProviderFailure | None:
    """Return the ``provider_failure`` element of a failed run, or ``None`` when it did not fail on a provider."""
    if capture.outcome is not RunOutcome.FAILED:
        return None
    return provider_failure_of((capture.analysis.assembly.provider_failure,))


def _failure_code(capture: GrahamNumberCapture) -> str | None:
    """Return the stable code of a failed run, derived from the stored native status and provider failure."""
    if capture.outcome is not RunOutcome.FAILED:
        return None
    return failure_reason_code(capture.analysis.native_status, capture_provider_failure(capture)).value


def from_graham_number_capture(capture: GrahamNumberCapture) -> ExecutionCapture:
    """Normalize a Graham Number capture."""
    return ExecutionCapture(
        native_evidence=capture.analysis,
        profile=capture.profile,
        outcome=capture.outcome,
        failure_reason_code=_failure_code(capture),
        provider_failure=capture_provider_failure(capture),
    )


__all__ = [
    "capture_provider_failure",
    "from_graham_number_capture",
    "GrahamNumberCapture",
    "classify_graham_number_outcome",
    "execute_graham_number",
]
