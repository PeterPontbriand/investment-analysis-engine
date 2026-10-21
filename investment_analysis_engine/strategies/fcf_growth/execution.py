"""FCF/Earnings Growth execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
formerly inlined in the ``fcf-growth`` command so both the direct
command and a future save/refresh service call identical code.
Presentation and exit-code selection stay in the command
(``investment_analysis_engine.strategies.fcf_growth.cli``); this module
captures execution evidence only.

Unlike Graham Number/Growth, the CLI composes the FCF profile using the same
production provider object for both the primary and Yahoo identity
candidates (there is no separate Yahoo client in this command's
composition); that exact choice is preserved here rather than "corrected."
The analyzer also returns its own ``instrument_profile`` field, but the CLI
never reads it back for rendering — it reuses the profile it composed before
calling the analyzer — so no post-analysis profile fallback is captured
here, matching that exact behavior.

The module reports facts only: the native status and the recorded provider failure. The shared rule
``RunOutcome.from_status`` produces the outcome, and ``ExecutionCapture`` derives it; a completed calculation is
completed regardless of the method's own PASS/FAIL trend classification, which is a financial signal, not an
execution outcome. Partial/optional metrics (forward evidence, FCF yield) inside a
completed result are retained unmodified by this adapter.
"""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies._shared.profile import compose_graham_profile
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthResult
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class FCFGrowthCapture:
    """Captured evidence for one FCF/Earnings Growth command execution.

    ``result`` is the unmodified native analyzer result. ``profile`` is the
    profile composed before calculation and supplied to the analyzer —
    exactly what the CLI renders with today.
    """

    result: FCFEarningsGrowthResult
    profile: InstrumentProfile


def execute_fcf_growth(  # noqa: PLR0913
    resolver: ProductionAnnualGrowthSeriesResolver,
    ticker: str,
    *,
    config: FCFEarningsGrowthConfig,
    as_of: datetime | None,
    executed_at: datetime,
    use_cache: bool,
    provider: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> FCFGrowthCapture:
    """Compose the profile and run the existing FCF/Earnings Growth analyzer.

    Args:
        resolver: A borrowed, already-composed annual growth-series resolver.
        ticker: The normalized target ticker.
        config: The requested policy, currency, and provider selection.
        as_of: The requested point-in-time boundary, or None.
        executed_at: The run's own execution clock, a single aware read of
            "now" taken once by the caller.
        use_cache: Whether resolved-input caching is enabled.
        provider: The production provider, used as both the primary and
            Yahoo identity candidate, exactly as the CLI composes it today.
        profile_cache: When supplied, resolves the profile through the
            durable P2-Profiles cache instead of composing live every call.

    Returns:
        The captured native result and its associated profile.
    """
    profile = compose_graham_profile(
        ticker,
        primary_provider=provider,
        yahoo_provider=provider,
        profile_cache=profile_cache,
    )
    context = AnalysisContext(as_of=as_of, executed_at=executed_at, use_cache=use_cache, instrument_profile=profile)
    result = FCFEarningsGrowthAnalyzer(resolver).run_analysis(ticker, config, context)
    return FCFGrowthCapture(result=result, profile=profile)


def from_fcf_growth_capture(capture: FCFGrowthCapture) -> ExecutionCapture:
    """Normalize a FCF/Earnings Growth capture."""
    return ExecutionCapture(
        native_evidence=capture.result,
        profile=capture.profile,
        native_status=capture.result.execution_status,
        provider_failure=provider_failure_of((capture.result.provider_failure,)),
    )


__all__ = [
    "from_fcf_growth_capture",
    "FCFGrowthCapture",
    "execute_fcf_growth",
]
