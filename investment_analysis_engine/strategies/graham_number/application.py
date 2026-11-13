"""Graham Number's application functions: its run function.

The application tier pairs these with the Graham Number core bundle; nothing here registers itself. The run function
composes the dependencies of one run, runs it through :func:`execute_graham_number`, and returns it with the means to
present it as a document and as text, so a caller never needs Graham Number's presentation.
"""

from datetime import datetime

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import stored_configuration
from investment_analysis_engine.application.providers import production_financial_cache
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies._graham.application import build_graham_resolver
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    build_graham_number_document,
    number_with_public_quote_reason,
    render_graham_number,
)
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.graham_number.workspace import (
    execute_graham_number,
    from_graham_number_capture,
)


def run(
    context: ApplicationContext,
    ticker: str,
    selection: GrahamNumberSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run Graham Number once with freshly composed, run-scoped dependencies and return it with its presentation.

    Args:
        context: The application context, whose settings give the providers and the cache.
        ticker: The target ticker.
        selection: The validated selection.
        executed_at: The run's own execution clock, the only clock the resolver's quote freshness reads.
        profile_cache: The durable profile cache, or ``None`` to compose the profile live.

    Returns:
        The normalized capture with the document and the text of the run.
    """
    config = stored_configuration(selection.to_graham_number_config)
    with production_financial_cache(context, use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            context,
            resolver_type=GrahamNumberInputResolver,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_number(
            resolver,
            ticker,
            config,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    analysis = capture.analysis
    profile = capture.profile
    identity_resolution = profile_identity_resolution(profile)

    def presentation(element: tuple[ProviderCheckItem, ...] | None) -> GrahamNumberPresentation:
        """Build the failure, not-applicable or success presentation of this analysis."""
        assembly = analysis.assembly
        if assembly.status is CalculationStatus.OK:
            return GrahamNumberPresentation(
                ticker=ticker,
                assembly=number_with_public_quote_reason(assembly),
                result=analysis.result,
                as_of=selection.as_of,
                effective_as_of=analysis.effective_as_of,
                margin_of_safety_percent=analysis.margin_of_safety_percent,
                price_comparison=analysis.price_comparison,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
                provider_check=element,
            )
        if assembly.status is CalculationStatus.NOT_APPLICABLE:
            return GrahamNumberPresentation(
                ticker=ticker,
                assembly=assembly,
                result=analysis.result,
                price_comparison=analysis.price_comparison,
                as_of=selection.as_of,
                effective_as_of=analysis.effective_as_of,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
                provider_check=element,
            )
        return GrahamNumberPresentation(
            ticker=ticker,
            assembly=number_with_public_quote_reason(assembly),
            price_comparison=analysis.price_comparison,
            result=None,
            as_of=selection.as_of,
            effective_as_of=analysis.effective_as_of,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            provider_check=element,
        )

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        return render_graham_number(presentation(element), mode)

    return StrategyRun(
        execution=from_graham_number_capture(capture),
        document=lambda element: build_graham_number_document(presentation(element)),
        render_text=render_text,
    )


__all__ = ["run"]
