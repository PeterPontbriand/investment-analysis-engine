"""The Piotroski F-Score strategy's application functions: its run function.

The application tier pairs these with the Piotroski core bundle; nothing here registers itself.

The strategy reads no market data and no cache: the balance-sheet series, the annual series and the share counts are not
cached, so a run composes the SEC adapter once and builds the analyzer on it. The adapter is also the as-filed SIC
source of the industry class, so it is built here and the production provider is composed from it.
"""

from datetime import datetime

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.providers import build_sec_edgar_adapter
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer
from investment_analysis_engine.strategies.piotroski.presenter import build_piotroski_document, render_piotroski
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategies.piotroski.workspace import execute_piotroski, from_piotroski_capture


def compose_piotroski(
    context: ApplicationContext, executed_at: datetime
) -> tuple[PiotroskiAnalyzer, ProductionFinancialFactsProvider]:
    """Compose the production analyzer and the provider its profile is composed from.

    The SEC adapter is built once. It serves the analyzer's resolver through the production provider and is the
    analyzer's as-filed SIC source, so the industry class is read from the same analysis scope as the inputs.

    Args:
        context: The application context, whose settings declare the SEC identity.
        executed_at: The run's single reading of the current time, never the ``--as-of`` boundary.

    Returns:
        The analyzer and the production provider.
    """
    adapter = build_sec_edgar_adapter(context)
    provider = ProductionFinancialFactsProvider(sec_edgar=adapter)
    return PiotroskiAnalyzer(InputResolver(provider, clock=lambda: executed_at), adapter), provider


def run(
    context: ApplicationContext,
    ticker: str,
    selection: PiotroskiSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run the Piotroski F-Score once with a freshly composed analyzer and return it with its presentation.

    Args:
        context: The application context, whose settings declare the SEC identity.
        ticker: The target ticker.
        selection: The validated selection: the boundary and the cache choice.
        executed_at: The run's own execution clock.
        profile_cache: The durable profile cache, or ``None`` to compose the profile live.

    Returns:
        The normalized capture with the document and the text of the run.
    """
    analyzer, provider = compose_piotroski(context, executed_at)
    capture = execute_piotroski(
        analyzer, ticker, selection, executed_at=executed_at, provider=provider, profile_cache=profile_cache
    )
    result = capture.result
    profile = capture.profile
    identity_resolution = profile_identity_resolution(profile)

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        return render_piotroski(result, mode, identity_resolution, profile, element)

    return StrategyRun(
        execution=from_piotroski_capture(capture),
        document=lambda element: build_piotroski_document(result, identity_resolution, profile, element),
        render_text=render_text,
    )


__all__ = ["compose_piotroski", "run"]
