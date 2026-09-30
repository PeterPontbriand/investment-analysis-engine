"""Graham Number execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
currently inlined in ``src.cli``'s ``_run_graham_number`` helper so both the
direct command and a future save/refresh service call identical code.
Presentation, exit-code selection, and friendly failure rendering stay in
``src.cli``; this module captures execution evidence only.

``classify_graham_number_outcome`` freezes the exact native-status mapping
required before any run is persisted: native ``NOT_APPLICABLE`` maps to
``RunOutcome.NOT_APPLICABLE``; a missing required input
(``INPUT_UNAVAILABLE``) maps to ``RunOutcome.UNAVAILABLE``; an invalid input
or provider error maps to ``RunOutcome.FAILED``; a completed calculation
maps to ``RunOutcome.COMPLETED``.
"""

from dataclasses import dataclass
from datetime import datetime

from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentProfile
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.workspace.graham_shared import compose_graham_profile
from src.workspace.models import RunOutcome


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


__all__ = [
    "GrahamNumberCapture",
    "classify_graham_number_outcome",
    "execute_graham_number",
]
