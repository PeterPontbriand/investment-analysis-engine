"""FCF Growth's application functions: its run function.

The application tier pairs these with the FCF Growth core bundle; nothing here registers itself. The run function
composes the dependencies of one run, runs it through :func:`execute_fcf_growth`, and returns it with the means to
present it as a document and as text, so a caller never needs FCF Growth's presentation.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import stored_configuration
from investment_analysis_engine.application.providers import (
    build_sec_production_provider,
    production_financial_cache,
    production_historical_client,
)
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.financial.cache import ResolvedInputSeriesCacheProtocol
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.quote_freshness import QuoteFreshnessPolicy
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.market_data import DatedSplitAdjustedHistoryProvider
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies.fcf_growth.analyzer import MarketCapDependencies
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.presenter import (
    build_fcf_growth_document,
    render_fcf_earnings_growth,
)
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.fcf_growth.workspace import execute_fcf_growth, from_fcf_growth_capture


def _market_cap_dependencies(
    context: ApplicationContext,
    provider: ProductionFinancialFactsProvider,
    cache: ResolvedInputSeriesCacheProtocol,
    historical_client: DatedSplitAdjustedHistoryProvider,
    *,
    clock: Callable[[], datetime],
) -> MarketCapDependencies:
    """Compose the FCF yield's dependencies once per run: the quote, the split history and the cover listing.

    The quote and the share counts come through the production provider and the run's financial cache, with the quote's
    own freshness policy; the split history comes through the cached historical client, as Momentum's prices do; the
    cover is read through the production provider. No new cache is created.
    """
    return MarketCapDependencies(
        resolver=InputResolver(
            provider,
            cache=cache,
            clock=clock,
            quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=context.settings.quote_cache_ttl_seconds)),
        ),
        split_history=historical_client,
        listing=provider,
    )


def run(
    context: ApplicationContext,
    ticker: str,
    selection: FCFGrowthSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run FCF Growth once with freshly composed, run-scoped dependencies and return it with its presentation.

    Args:
        context: The application context, whose settings give the providers and the caches.
        ticker: The target ticker.
        selection: The validated selection.
        executed_at: The run's own execution clock.
        profile_cache: The durable profile cache, or ``None`` to compose the profile live.

    Returns:
        The normalized capture with the document and the text of the run.
    """
    config = stored_configuration(selection.to_fcf_config)
    with (
        production_financial_cache(context, use_cache=selection.use_cache, clock=lambda: executed_at) as cache,
        production_historical_client(
            context, YFinanceClient(), use_cache=selection.use_cache, clock=lambda: executed_at
        ) as historical_client,
    ):
        provider = build_sec_production_provider(context)
        resolver = ProductionAnnualGrowthSeriesResolver(provider, cache=cache, clock=lambda: executed_at)
        capture = execute_fcf_growth(
            resolver,
            ticker,
            config=config,
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            provider=provider,
            market_data=_market_cap_dependencies(
                context, provider, cache, historical_client, clock=lambda: executed_at
            ),
            profile_cache=profile_cache,
        )
    result = capture.result
    profile = capture.profile
    identity_resolution = profile_identity_resolution(profile)

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        return render_fcf_earnings_growth(result, mode, identity_resolution, profile, element)

    return StrategyRun(
        execution=from_fcf_growth_capture(capture),
        document=lambda element: build_fcf_growth_document(result, identity_resolution, profile, element),
        render_text=render_text,
    )


__all__ = ["run"]
