"""Graham Number execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
formerly inlined in the ``_run_graham_number`` helper so both the
direct command and a future save/refresh service call identical code.
Presentation, exit-code selection, and friendly failure rendering stay in
the command (``investment_analysis_engine.strategies.graham_number.cli``); this module captures execution evidence only.

The module reports facts only: the native status and the recorded provider failure. The shared rule
``RunOutcome.from_status`` produces the outcome, and ``ExecutionCapture`` derives it.
"""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.failure_classification import provider_failure_of
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
    """

    analysis: GrahamNumberAnalysis
    profile: InstrumentProfile


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
    analysis = GrahamNumberAnalyzer(resolver).run_analysis(ticker, config, context)
    profile = analysis.instrument_profile or composed_profile
    return GrahamNumberCapture(analysis=analysis, profile=profile)


def from_graham_number_capture(capture: GrahamNumberCapture) -> ExecutionCapture:
    """Normalize a Graham Number capture."""
    return ExecutionCapture(
        native_evidence=capture.analysis,
        profile=capture.profile,
        native_status=capture.analysis.native_status,
        provider_failure=provider_failure_of((capture.analysis.assembly.provider_failure,)),
    )


__all__ = [
    "from_graham_number_capture",
    "GrahamNumberCapture",
    "execute_graham_number",
]
