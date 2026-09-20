"""Production provider/resolver composition shared by CLI entry points.

These functions build the SEC EDGAR/Massive financial-fact providers and the
Graham input resolvers used by the direct commands (``src.cli``) and by the
refresh service's dispatch executor (``src.cli_workspace``). They read
declared application identity and growth-assumption constants from
``settings`` — configuration entirely independent of database access.

This is deliberately its own module, not ``src.cli_support``: the shared
test fixture ``isolated_cli_database`` (``tests/_cli_helpers.py``) rebinds
``src.cli_support.settings`` and ``src.cli_workspace.settings`` to a
disposable, isolated instance so tests never depend on a developer machine's
real local database being migrated. Several already-accepted tests also rely
on ``patch.object(settings, "sec_user_agent", value)`` mutating the one real
shared settings singleton that ``src.cli`` reads. If these functions lived in
``src.cli_support`` or ``src.cli_workspace``, that database-only isolation
would silently defeat the SEC-identity/growth-assumption patches too, since
both concerns would share one rebindable module-level name. Keeping this
composition in its own, never-rebound module preserves both: refresh's own
database access stays isolated via ``src.cli_workspace.settings``, while
provider/resolver composition here always reads the real settings singleton.
"""

from datetime import timedelta

from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.cli_support import AnalysisConfigurationError
from src.config import settings
from src.core.constants import ConfigKeys
from src.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheProtocol
from src.data.financial.facts import FinancialFactsProvider
from src.data.financial.providers import (
    MASSIVE_PROVIDER_ID,
    SEC_PROVIDER_ID,
    MassiveFinancialFactsAdapter,
    ProductionFinancialFactsProvider,
    SecEdgarFinancialFactsAdapter,
)
from src.data.financial.quote_freshness import QuoteFreshnessPolicy


def build_sec_production_provider() -> ProductionFinancialFactsProvider:
    """Build the SEC-backed production provider from declared application identity."""
    user_agent = settings.sec_user_agent
    if user_agent is None or not user_agent.strip():
        raise AnalysisConfigurationError(
            "SEC EDGAR access is not configured. "
            "Set SEC_USER_AGENT to a declared identity such as "
            '"Your Name your-email@example.com" and retry.'
        )
    sec_edgar = SecEdgarFinancialFactsAdapter(user_agent=user_agent)
    return ProductionFinancialFactsProvider(sec_edgar=sec_edgar)


def build_massive_production_provider() -> MassiveFinancialFactsAdapter:
    """Build Massive only when usable API credentials are configured."""
    massive = MassiveFinancialFactsAdapter()
    if not massive.is_configured:
        raise AnalysisConfigurationError("Massive access is not configured. Set MASSIVE_API_KEY and retry.")
    return massive


def build_graham_resolver[ResolverT: (GrahamNumberInputResolver, GrahamGrowthInputResolver)](
    *, resolver_type: type[ResolverT], data_provider: str | None, cache: ResolvedInputCacheProtocol | None = None
) -> ResolverT:
    """Build only the production provider capabilities needed by this invocation."""
    provider: FinancialFactsProvider
    if data_provider == MASSIVE_PROVIDER_ID:
        provider = build_massive_production_provider()
    elif data_provider == SEC_PROVIDER_ID:
        provider = build_sec_production_provider()
    elif data_provider is not None:
        raise AnalysisConfigurationError(
            f"Unsupported valuation data provider {data_provider!r}; "
            f"supported providers are {SEC_PROVIDER_ID!r} and {MASSIVE_PROVIDER_ID!r}."
        )
    else:
        provider = build_sec_production_provider()

    return resolver_type(
        provider,
        cache=cache if cache is not None else InMemoryResolvedInputCache(),
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=settings.quote_cache_ttl_seconds)),
    )


def growth_assumptions() -> GrahamGrowthCalculationPolicy:
    """Read the configured constants for the growth-value method."""
    values = settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES]
    return GrahamGrowthCalculationPolicy(
        base_pe=float(values[ConfigKeys.BASE_PE]),
        growth_multiplier=float(values[ConfigKeys.GROWTH_MULTIPLIER]),
        baseline_aaa_yield=float(values[ConfigKeys.BASELINE_AAA_YIELD]),
    )


__all__ = [
    "build_graham_resolver",
    "build_massive_production_provider",
    "build_sec_production_provider",
    "growth_assumptions",
]
