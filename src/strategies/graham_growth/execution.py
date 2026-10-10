"""Graham Growth execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
formerly inlined in the ``_run_graham_growth`` helper so both the
direct command and a future save/refresh service call identical code.
Presentation, exit-code selection, and friendly failure rendering stay in
the command (``src.strategies.graham_growth.cli``); this module captures execution evidence only. The effective
calculation policy (base P/E, growth multiplier, baseline AAA yield) is
supplied by the caller — exactly as ``src.cli_composition``'s
``growth_assumptions`` already resolves it — and retained unmodified inside the native
``GrahamGrowthAnalysis.policy`` field; no new assumption is derived here.

``classify_graham_growth_outcome`` freezes the exact native-status mapping
required before any run is persisted: native ``NOT_APPLICABLE`` maps to
``RunOutcome.NOT_APPLICABLE``; a missing required input
(``INPUT_UNAVAILABLE``) maps to ``RunOutcome.UNAVAILABLE``; an invalid input
or provider error maps to ``RunOutcome.FAILED``; a completed calculation
(including a nonpositive growth value, which is a valid financial outcome,
not an execution failure) maps to ``RunOutcome.COMPLETED``.
"""

from dataclasses import dataclass
from datetime import datetime

from src.analysis.base_analyzer import AnalysisContext
from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentProfile
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.reporting.failure_classification import failure_reason_code, provider_failure_of
from src.strategies._shared.profile import compose_graham_profile
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.strategies.graham_growth.config import GrahamGrowthConfig
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.workspace.capture import ExecutionCapture
from src.workspace.models import RunOutcome


@dataclass(frozen=True)
class GrahamGrowthCapture:
    """Captured evidence for one Graham Growth command execution.

    ``analysis`` is the unmodified native analyzer result, including its own
    ``policy`` field (the effective calculation policy actually used).
    ``profile`` is the exact profile associated with the analysis: the
    analyzer's own ``instrument_profile`` when it returned one, otherwise the
    profile composed before calculation — the same fallback the CLI already
    applies. ``outcome`` is the frozen status mapping described above.
    """

    analysis: GrahamGrowthAnalysis
    profile: InstrumentProfile
    outcome: RunOutcome


def classify_graham_growth_outcome(analysis: GrahamGrowthAnalysis) -> RunOutcome:
    """Map native Graham Growth status to the workspace's terminal outcome.

    A nonpositive growth value is a valid, completed calculation (the
    method's own financial signal), not an execution failure or a
    non-``OK`` result status; it maps to ``COMPLETED`` like any other
    successful calculation.
    """
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


def execute_graham_growth(  # noqa: PLR0913
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    config: GrahamGrowthConfig,
    policy: GrahamGrowthCalculationPolicy,
    profile_provider: object,
    *,
    as_of: datetime | None,
    executed_at: datetime,
    use_cache: bool,
    profile_cache: InstrumentProfileResolver | None = None,
) -> GrahamGrowthCapture:
    """Compose the profile and run the existing Graham Growth analyzer.

    Args:
        resolver: A borrowed, already-composed input resolver.
        ticker: The normalized target ticker.
        config: The validated Graham Growth configuration.
        policy: The effective calculation policy to apply, resolved by the
            caller exactly as the CLI does today.
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
    analysis = GrahamGrowthAnalyzer(resolver, policy=policy).run_analysis(ticker, config, context)
    profile = analysis.instrument_profile or composed_profile
    return GrahamGrowthCapture(analysis=analysis, profile=profile, outcome=classify_graham_growth_outcome(analysis))


def _failure_code(capture: GrahamGrowthCapture) -> str | None:
    """Return the stable code of a failed run, derived from the stored native status and provider failure."""
    if capture.outcome is not RunOutcome.FAILED:
        return None
    return failure_reason_code(
        capture.analysis.native_status, provider_failure_of((capture.analysis.assembly.provider_failure,))
    ).value


def from_graham_growth_capture(capture: GrahamGrowthCapture) -> ExecutionCapture:
    """Normalize a Graham Growth capture."""
    return ExecutionCapture(
        native_evidence=capture.analysis,
        profile=capture.profile,
        outcome=capture.outcome,
        failure_reason_code=_failure_code(capture),
    )


__all__ = [
    "from_graham_growth_capture",
    "GrahamGrowthCapture",
    "classify_graham_growth_outcome",
    "execute_graham_growth",
]
