"""The Piotroski F-Score strategy's workspace adapter.

It composes the identity profile, calls the analyzer and captures the evidence. Presentation and exit-code selection
stay in the strategy's application module; this module reports facts only: the evidence, its profile, the native
status and the recorded provider failure.
"""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies._shared.profile import compose_production_profile
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer, PiotroskiResult
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class PiotroskiCapture:
    """The captured evidence of one Piotroski F-Score execution.

    ``result`` is the unmodified native analyzer result. ``profile`` is the profile composed before the calculation and
    given to the analyzer.
    """

    result: PiotroskiResult
    profile: InstrumentProfile


def execute_piotroski(  # noqa: PLR0913
    analyzer: PiotroskiAnalyzer,
    ticker: str,
    selection: PiotroskiSelection,
    *,
    executed_at: datetime,
    provider: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> PiotroskiCapture:
    """Compose the profile and run the analyzer for ``selection``.

    Args:
        analyzer: A borrowed, already-composed analyzer.
        ticker: The normalized target ticker.
        selection: The validated selection: the boundary and the cache choice.
        executed_at: The run's own execution clock, a single aware read of "now" taken once by the caller.
        provider: The production provider, used as both the primary and the Yahoo identity candidate, as the FCF and
            Earnings Growth command composes it.
        profile_cache: When supplied, resolves the profile through the durable profile cache instead of composing live.

    Returns:
        The captured native result and its profile.
    """
    profile = compose_production_profile(
        ticker, primary_provider=provider, yahoo_provider=provider, profile_cache=profile_cache
    )
    context = selection.to_analysis_context(executed_at=executed_at, instrument_profile=profile)
    return PiotroskiCapture(result=analyzer.run_analysis(ticker, context), profile=profile)


def from_piotroski_capture(capture: PiotroskiCapture) -> ExecutionCapture:
    """Normalize a Piotroski F-Score capture.

    It passes the evidence, profile, native status and recorded provider failure.
    """
    return ExecutionCapture(
        native_evidence=capture.result,
        profile=capture.profile,
        native_status=capture.result.execution_status,
        provider_failure=provider_failure_of((capture.result.provider_failure,)),
    )
