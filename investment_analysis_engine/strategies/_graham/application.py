"""The production resolver composition the two Graham strategies share, for the application tier.

Both Graham strategies resolve company facts through the SEC-backed production provider and one quote-freshness
policy, so their resolvers are built by the same function. Each strategy's own ``application`` module calls it with its
resolver class, so this module imports no strategy.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.providers import build_sec_production_provider
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheProtocol
from investment_analysis_engine.data.financial.quote_freshness import QuoteFreshnessPolicy
from investment_analysis_engine.data.financial.resolver import InputResolver


def build_graham_resolver[ResolverT: InputResolver](
    context: ApplicationContext,
    *,
    resolver_type: type[ResolverT],
    clock: Callable[[], datetime],
    cache: ResolvedInputCacheProtocol | None = None,
) -> ResolverT:
    """Build only the production provider capabilities needed by this invocation.

    ``clock`` must resolve to the run's own ``executed_at`` — the sole source for the resolver's quote-freshness
    evaluation. It is never fed a point-in-time boundary.
    """
    return resolver_type(
        build_sec_production_provider(context),
        cache=cache if cache is not None else InMemoryResolvedInputCache(clock=clock),
        clock=clock,
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=context.settings.quote_cache_ttl_seconds)),
    )
