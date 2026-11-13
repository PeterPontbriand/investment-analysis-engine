"""Graham Growth's application functions: its settings and its run function.

The application tier pairs these with the Graham Growth core bundle; nothing here registers itself. The run function
composes the dependencies of one run, runs it through :func:`execute_graham_growth`, and returns it with the means to
present it as a document and as text, so a caller never needs Graham Growth's presentation.
"""

from datetime import datetime

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import stored_configuration
from investment_analysis_engine.application.providers import production_financial_cache
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies._graham.application import build_graham_resolver
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from investment_analysis_engine.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    build_graham_growth_document,
    growth_with_public_quote_reason,
    render_graham_growth,
)
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_growth.settings import GrahamGrowthSettings
from investment_analysis_engine.strategies.graham_growth.workspace import (
    execute_graham_growth,
    from_graham_growth_capture,
)
from investment_analysis_engine.strategy_wiring import GRAHAM_GROWTH


def graham_growth_settings(context: ApplicationContext) -> GrahamGrowthSettings:
    """Return Graham Growth's validated settings from the context's settings folder, loaded once per folder."""
    return load_component_settings(GRAHAM_GROWTH.alias, GrahamGrowthSettings, context.settings.config_dir)


def run(
    context: ApplicationContext,
    ticker: str,
    selection: GrahamGrowthSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run Graham Growth once with freshly composed, run-scoped dependencies and return it with its presentation.

    Args:
        context: The application context, whose settings give the providers, the cache and the policy.
        ticker: The target ticker.
        selection: The validated selection.
        executed_at: The run's own execution clock, the only clock the resolver's quote freshness reads.
        profile_cache: The durable profile cache, or ``None`` to compose the profile live.

    Returns:
        The normalized capture with the document and the text of the run.
    """
    config = stored_configuration(selection.to_graham_growth_config)
    policy = graham_growth_settings(context).to_policy()
    with production_financial_cache(context, use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            context,
            resolver_type=GrahamGrowthInputResolver,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_growth(
            resolver,
            ticker,
            config,
            policy,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    analysis = capture.analysis
    profile = capture.profile
    identity_resolution = profile_identity_resolution(profile)

    def presentation(element: tuple[ProviderCheckItem, ...] | None) -> GrahamGrowthPresentation:
        """Build the failure, not-applicable or success presentation of this analysis."""
        assembly = analysis.assembly
        if assembly.status is CalculationStatus.OK:
            return GrahamGrowthPresentation(
                ticker=ticker,
                assembly=growth_with_public_quote_reason(assembly),
                result=analysis.result,
                base_pe=policy.base_pe,
                growth_multiplier=policy.growth_multiplier,
                baseline_aaa_yield=policy.baseline_aaa_yield,
                as_of=selection.as_of,
                effective_as_of=analysis.effective_as_of,
                margin_of_safety_percent=analysis.margin_of_safety_percent,
                price_comparison=analysis.price_comparison,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
                provider_check=element,
            )
        if assembly.status is CalculationStatus.NOT_APPLICABLE:
            return GrahamGrowthPresentation(
                ticker=ticker,
                assembly=assembly,
                result=analysis.result,
                price_comparison=analysis.price_comparison,
                base_pe=policy.base_pe,
                growth_multiplier=policy.growth_multiplier,
                baseline_aaa_yield=policy.baseline_aaa_yield,
                as_of=selection.as_of,
                effective_as_of=analysis.effective_as_of,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
                provider_check=element,
            )
        return GrahamGrowthPresentation(
            ticker=ticker,
            assembly=growth_with_public_quote_reason(assembly),
            price_comparison=analysis.price_comparison,
            result=None,
            base_pe=policy.base_pe,
            growth_multiplier=policy.growth_multiplier,
            baseline_aaa_yield=policy.baseline_aaa_yield,
            as_of=selection.as_of,
            effective_as_of=analysis.effective_as_of,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            provider_check=element,
        )

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        return render_graham_growth(presentation(element), mode)

    return StrategyRun(
        execution=from_graham_growth_capture(capture),
        document=lambda element: build_graham_growth_document(presentation(element)),
        render_text=render_text,
    )


__all__ = ["graham_growth_settings", "run"]
