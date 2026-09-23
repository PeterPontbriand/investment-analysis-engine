"""FCF/Earnings Growth execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the profile composition and analyzer invocation
currently inlined in ``src.cli``'s ``fcf-growth`` command so both the direct
command and a future save/refresh service call identical code.
Presentation and exit-code selection stay in ``src.cli``; this module
captures execution evidence only.

Unlike Graham Number/Growth, the CLI composes the FCF profile using the same
production provider object for both the primary and Yahoo identity
candidates (there is no separate Yahoo client in this command's
composition); that exact choice is preserved here rather than "corrected."
The analyzer also returns its own ``instrument_profile`` field, but the CLI
never reads it back for rendering — it reuses the profile it composed before
calling the analyzer — so no post-analysis profile fallback is captured
here, matching that exact behavior.

``classify_fcf_growth_outcome`` freezes the exact native-status mapping
required before any run is persisted: native ``NOT_APPLICABLE`` (including
the analyzer's own known-ETF short-circuit) maps to
``RunOutcome.NOT_APPLICABLE``; a missing required input
(``INPUT_UNAVAILABLE``) maps to ``RunOutcome.UNAVAILABLE``; an invalid input
or provider error maps to ``RunOutcome.FAILED``; a completed calculation
maps to ``RunOutcome.COMPLETED`` regardless of the method's own PASS/FAIL
trend classification, which is a financial signal, not an execution
outcome. Partial/optional metrics (forward evidence, FCF yield) inside a
completed result are retained unmodified by this adapter.
"""

from dataclasses import dataclass
from datetime import datetime

from src.analysis.strategy.fcf_earnings_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.analysis.strategy.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthPolicy, FCFEarningsGrowthResult
from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentProfile
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.workspace.graham_shared import compose_graham_profile
from src.workspace.models import RunOutcome


@dataclass(frozen=True)
class FCFGrowthCapture:
    """Captured evidence for one FCF/Earnings Growth command execution.

    ``result`` is the unmodified native analyzer result. ``profile`` is the
    profile composed before calculation and supplied to the analyzer —
    exactly what the CLI renders with today. ``outcome`` is the frozen
    status mapping described above.
    """

    result: FCFEarningsGrowthResult
    profile: InstrumentProfile
    outcome: RunOutcome


def classify_fcf_growth_outcome(result: FCFEarningsGrowthResult) -> RunOutcome:
    """Map native FCF execution status to the workspace's terminal outcome."""
    status = result.execution_status
    if status is CalculationStatus.NOT_APPLICABLE:
        return RunOutcome.NOT_APPLICABLE
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return RunOutcome.UNAVAILABLE
    if status is not CalculationStatus.OK:
        return RunOutcome.FAILED
    return RunOutcome.COMPLETED


def execute_fcf_growth(  # noqa: PLR0913
    resolver: ProductionAnnualGrowthSeriesResolver,
    ticker: str,
    *,
    policy: FCFEarningsGrowthPolicy,
    currency: str,
    as_of: datetime | None,
    provider_id: str,
    use_cache: bool,
    effective_as_of: datetime,
    provider: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> FCFGrowthCapture:
    """Compose the profile and run the existing FCF/Earnings Growth analyzer.

    Args:
        resolver: A borrowed, already-composed annual growth-series resolver.
        ticker: The normalized target ticker.
        policy: The requested FCF/Earnings Growth policy.
        currency: The normalized three-letter reporting currency.
        as_of: The requested point-in-time boundary, or None.
        provider_id: The canonical security-fact provider identifier.
        use_cache: Whether resolved-input caching is enabled.
        effective_as_of: The aware execution boundary actually applied.
        provider: The production provider, used as both the primary and
            Yahoo identity candidate, exactly as the CLI composes it today.
        profile_cache: When supplied, resolves the profile through the
            durable P2-Profiles cache instead of composing live every call.

    Returns:
        The captured native result, its associated profile, and the mapped
        terminal outcome.
    """
    profile = compose_graham_profile(
        ticker,
        primary_provider=provider,
        primary_provider_id=provider_id,
        yahoo_provider=provider,
        profile_cache=profile_cache,
    )
    result = FCFEarningsGrowthAnalyzer(resolver).run_analysis(
        ticker=ticker,
        policy=policy,
        currency=currency,
        as_of=as_of,
        provider_id=provider_id,
        use_cache=use_cache,
        effective_as_of=effective_as_of,
        instrument_profile=profile,
    )
    return FCFGrowthCapture(result=result, profile=profile, outcome=classify_fcf_growth_outcome(result))


__all__ = [
    "FCFGrowthCapture",
    "classify_fcf_growth_outcome",
    "execute_fcf_growth",
]
