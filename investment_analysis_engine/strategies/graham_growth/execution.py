"""Graham Growth execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation formerly inlined in the ``_run_graham_growth``
helper so both the direct command and a future save/refresh service call identical code. Presentation, exit-code
selection, and friendly failure rendering stay in the command
(``investment_analysis_engine.strategies.graham_growth.cli``); this module captures execution evidence only. The
effective calculation policy (base P/E, growth multiplier, baseline AAA yield) is supplied by the caller — exactly as
the composition root builds it from the configured Graham Growth settings (``GrahamGrowthSettings.to_policy()``) — and
retained unmodified inside the native ``GrahamGrowthAnalysis.policy`` field; no new assumption is derived here.

The module reports facts only: the native status and the recorded provider failure. The shared rule
``RunOutcome.from_status`` produces the outcome, and ``ExecutionCapture`` derives it. A nonpositive growth value is a
valid, completed calculation, not an execution failure.
"""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies._shared.profile import compose_graham_profile
from investment_analysis_engine.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
)
from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class GrahamGrowthCapture:
    """Captured evidence for one Graham Growth command execution.

    ``analysis`` is the unmodified native analyzer result, including its own
    ``policy`` field (the effective calculation policy actually used).
    ``profile`` is the exact profile associated with the analysis: the
    analyzer's own ``instrument_profile`` when it returned one, otherwise the
    profile composed before calculation — the same fallback the CLI already
    applies.
    """

    analysis: GrahamGrowthAnalysis
    profile: InstrumentProfile


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
        The captured native analysis and its associated profile.
    """
    composed_profile = compose_graham_profile(
        ticker,
        primary_provider=resolver.provider,
        yahoo_provider=profile_provider,
        profile_cache=profile_cache,
    )
    context = AnalysisContext(
        as_of=as_of, executed_at=executed_at, use_cache=use_cache, instrument_profile=composed_profile
    )
    analysis = GrahamGrowthAnalyzer(resolver, policy=policy).run_analysis(ticker, config, context)
    profile = analysis.instrument_profile or composed_profile
    return GrahamGrowthCapture(analysis=analysis, profile=profile)


def from_graham_growth_capture(capture: GrahamGrowthCapture) -> ExecutionCapture:
    """Normalize a Graham Growth capture."""
    return ExecutionCapture(
        native_evidence=capture.analysis,
        profile=capture.profile,
        native_status=capture.analysis.native_status,
        provider_failure=provider_failure_of((capture.analysis.assembly.provider_failure,)),
    )


__all__ = [
    "from_graham_growth_capture",
    "GrahamGrowthCapture",
    "execute_graham_growth",
]
