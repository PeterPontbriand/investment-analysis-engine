"""Production provider/resolver composition shared by CLI entry points.

These functions build the SEC EDGAR financial-fact provider and the
Graham input resolvers used by the direct commands (``src.strategies.<strategy>.cli``) and by the
refresh service's dispatch executor (``src.cli_workspace``). They read
declared application identity from ``settings`` and each strategy's typed settings from its settings
file; neither depends on database access.

This is deliberately its own module, not ``src.cli_support``: the shared
test fixture ``isolated_cli_database`` (``tests/_cli_helpers.py``) rebinds
``src.cli_support.settings`` and ``src.cli_workspace.settings`` to a
disposable, isolated instance so tests never depend on a developer machine's
real local database being migrated. Several already-accepted tests also rely
on ``patch.object(settings, "sec_user_agent", value)`` mutating the one real
shared settings singleton that the direct commands read. If these functions lived in
``src.cli_support`` or ``src.cli_workspace``, that database-only isolation
would silently defeat the SEC-identity/growth-assumption patches too, since
both concerns would share one rebindable module-level name. Keeping this
composition in its own, never-rebound module preserves both: refresh's own
database access stays isolated via ``src.cli_workspace.settings``, while
provider/resolver composition here always reads the real settings singleton.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from src.config import settings
from src.config.strategy_settings import load_strategy_settings
from src.core.operator_errors import AnalysisConfigurationError
from src.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheProtocol
from src.data.financial.facts import FinancialFactsProvider
from src.data.financial.providers import (
    SEC_PROVIDER_ID,
    ProductionFinancialFactsProvider,
    SecEdgarFinancialFactsAdapter,
)
from src.data.financial.quote_freshness import QuoteFreshnessPolicy
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from src.strategies.graham_growth.settings import GrahamGrowthSettings
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from src.strategies.momentum.settings import MomentumSettings
from src.strategy_wiring import GRAHAM_GROWTH, MOMENTUM, STRATEGIES


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


def build_graham_resolver[ResolverT: (GrahamNumberInputResolver, GrahamGrowthInputResolver)](
    *,
    resolver_type: type[ResolverT],
    data_provider: str | None,
    clock: Callable[[], datetime],
    cache: ResolvedInputCacheProtocol | None = None,
) -> ResolverT:
    """Build only the production provider capabilities needed by this invocation.

    ``clock`` must resolve to the composition root's own ``executed_at`` —
    the sole source for the resolver's quote-freshness evaluation. It is
    never fed a point-in-time boundary.
    """
    provider: FinancialFactsProvider
    if data_provider is not None and data_provider != SEC_PROVIDER_ID:
        raise AnalysisConfigurationError(
            f"Unsupported valuation data provider {data_provider!r}; supported provider is {SEC_PROVIDER_ID!r}."
        )
    provider = build_sec_production_provider()

    return resolver_type(
        provider,
        cache=cache if cache is not None else InMemoryResolvedInputCache(clock=clock),
        clock=clock,
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=settings.quote_cache_ttl_seconds)),
    )


def _strategy_settings_directory() -> Path:
    """Return the folder that holds the strategy settings files."""
    return settings.base_dir / "config" / "strategies"


def momentum_settings() -> MomentumSettings:
    """Return Momentum's validated settings, loaded once per process."""
    return load_strategy_settings(MOMENTUM.alias, MomentumSettings, _strategy_settings_directory())


def graham_growth_settings() -> GrahamGrowthSettings:
    """Return Graham Growth's validated settings, loaded once per process."""
    return load_strategy_settings(GRAHAM_GROWTH.alias, GrahamGrowthSettings, _strategy_settings_directory())


def load_all_strategy_settings() -> None:
    """Load and validate the settings file of every strategy that declares one.

    Called once at startup, so a missing or invalid file stops every command with one message.

    Raises:
        StrategySettingsError: If a declared file is missing, is not valid TOML or does not satisfy its model.
    """
    directory = _strategy_settings_directory()
    for descriptor in STRATEGIES:
        if descriptor.settings_type is not None:
            load_strategy_settings(descriptor.alias, descriptor.settings_type, directory)


__all__ = [
    "build_graham_resolver",
    "build_sec_production_provider",
    "graham_growth_settings",
    "load_all_strategy_settings",
    "momentum_settings",
]
