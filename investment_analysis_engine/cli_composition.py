"""Production provider/resolver composition shared by CLI entry points.

These functions build the SEC EDGAR financial-fact provider and the
Graham input resolvers used by the direct commands (``investment_analysis_engine.strategies.<strategy>.cli``) and by the
refresh service's dispatch executor (``investment_analysis_engine.cli_workspace``). They read
declared application identity from ``settings`` and each strategy's typed settings from its settings
file; neither depends on database access.

This is deliberately its own module, not ``investment_analysis_engine.cli_support``: the shared
test fixture ``isolated_cli_database`` (``tests/_cli_helpers.py``) rebinds
``investment_analysis_engine.cli_support.settings`` and ``investment_analysis_engine.cli_workspace.settings`` to a
disposable, isolated instance so tests never depend on a developer machine's
real local database being migrated. Several already-accepted tests also rely
on ``patch.object(settings, "sec_user_agent", value)`` mutating the one real
shared settings singleton that the direct commands read. If these functions lived in
``investment_analysis_engine.cli_support`` or ``investment_analysis_engine.cli_workspace``, that database-only isolation
would silently defeat the SEC-identity/growth-assumption patches too, since
both concerns would share one rebindable module-level name. Keeping this
composition in its own, never-rebound module preserves both: refresh's own
database access stays isolated via ``investment_analysis_engine.cli_workspace.settings``, while
provider/resolver composition here always reads the real settings singleton.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from investment_analysis_engine.config import settings
from investment_analysis_engine.config.strategy_settings import load_strategy_settings
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheProtocol
from investment_analysis_engine.data.financial.facts import FinancialFactsProvider
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.quote_freshness import QuoteFreshnessPolicy
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from investment_analysis_engine.strategies.graham_growth.settings import GrahamGrowthSettings
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategy_wiring import GRAHAM_GROWTH, MOMENTUM, STRATEGIES


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
    clock: Callable[[], datetime],
    cache: ResolvedInputCacheProtocol | None = None,
) -> ResolverT:
    """Build only the production provider capabilities needed by this invocation.

    ``clock`` must resolve to the composition root's own ``executed_at`` —
    the sole source for the resolver's quote-freshness evaluation. It is
    never fed a point-in-time boundary.
    """
    provider: FinancialFactsProvider
    provider = build_sec_production_provider()

    return resolver_type(
        provider,
        cache=cache if cache is not None else InMemoryResolvedInputCache(clock=clock),
        clock=clock,
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=settings.quote_cache_ttl_seconds)),
    )


def _settings_folder() -> Path:
    """Return the user's settings folder, which may hold strategy settings files that override the shipped ones."""
    return settings.config_dir


def momentum_settings() -> MomentumSettings:
    """Return Momentum's validated settings, loaded once per process."""
    return load_strategy_settings(MOMENTUM.alias, MomentumSettings, _settings_folder())


def graham_growth_settings() -> GrahamGrowthSettings:
    """Return Graham Growth's validated settings, loaded once per process."""
    return load_strategy_settings(GRAHAM_GROWTH.alias, GrahamGrowthSettings, _settings_folder())


def load_all_strategy_settings() -> None:
    """Load and validate the settings of every strategy that declares a settings model.

    Called once at startup, so an invalid file stops every command with one message.

    Raises:
        StrategySettingsError: If a shipped file is missing, a file is not valid TOML or the values break a rule.
    """
    folder = _settings_folder()
    for descriptor in STRATEGIES:
        if descriptor.settings_type is not None:
            load_strategy_settings(descriptor.alias, descriptor.settings_type, folder)


__all__ = [
    "build_graham_resolver",
    "build_sec_production_provider",
    "graham_growth_settings",
    "load_all_strategy_settings",
    "momentum_settings",
]
