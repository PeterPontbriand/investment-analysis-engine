"""Production provider, cache and settings composition shared by every application operation.

These functions build the SEC EDGAR financial-fact provider and own the durable caches an analysis uses. Each takes the
:class:`ApplicationContext` and reads the declared application identity, the cache lifetimes and the settings folder
from the settings it holds; none reads a module-level settings object. A strategy's own providers, resolvers and
settings are built in that strategy's ``application`` module from the functions here.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.data.cached_client import CachedHistoricalDataClient
from investment_analysis_engine.data.financial.cache import ResolvedInputSeriesCacheProtocol
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.http_json import fetch_json
from investment_analysis_engine.data.instrument_profile_cache import CachedInstrumentProfileResolver
from investment_analysis_engine.data.market_data import SPLIT_ADJUSTED_PRICE
from investment_analysis_engine.data.provider_checks import (
    ConnectionStep,
    ProviderClients,
    SecTransport,
    SecUnavailable,
)
from investment_analysis_engine.data.provider_probe import ProviderProbe
from investment_analysis_engine.data.quality import HistoricalQualityPolicy
from investment_analysis_engine.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from investment_analysis_engine.data.repositories.market_data import SQLiteMarketDataRepository
from investment_analysis_engine.data.repositories.readiness import ensure_database_ready
from investment_analysis_engine.data.repositories.resolved_input_cache import SQLiteResolvedInputCache
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.data.sec_edgar.settings import (
    PROVIDER_SETTINGS_FOLDER,
    SEC_EDGAR_ALIAS,
    SecEdgarSettings,
)
from investment_analysis_engine.data.yfinance.client import (
    YFINANCE_HISTORICAL_INTERVAL,
    YFINANCE_PRICE_ADJUSTMENT,
    YFinanceClient,
)
from investment_analysis_engine.strategy_wiring import STRATEGIES


def build_sec_edgar_adapter(context: ApplicationContext) -> SecEdgarFinancialFactsAdapter:
    """Build the SEC EDGAR adapter from the declared application identity in the context's settings.

    Raises:
        AnalysisConfigurationError: If no SEC user agent is configured.
    """
    user_agent = context.settings.sec_user_agent
    if user_agent is None or not user_agent.strip():
        raise AnalysisConfigurationError(
            "SEC EDGAR access is not configured. "
            "Set SEC_USER_AGENT to a declared identity such as "
            '"Your Name your-email@example.com" and retry.'
        )
    overrides = {ticker: str(cik) for ticker, cik in sec_edgar_settings(context).ticker_overrides.items()}
    return SecEdgarFinancialFactsAdapter(user_agent=user_agent, ticker_overrides=overrides)


def build_sec_production_provider(context: ApplicationContext) -> ProductionFinancialFactsProvider:
    """Build the SEC-backed production provider from the declared application identity."""
    return ProductionFinancialFactsProvider(sec_edgar=build_sec_edgar_adapter(context))


def sec_edgar_settings(context: ApplicationContext) -> SecEdgarSettings:
    """Return the SEC adapter's validated settings from the context's settings folder, loaded once per folder."""
    return load_component_settings(
        SEC_EDGAR_ALIAS, SecEdgarSettings, context.settings.config_dir, PROVIDER_SETTINGS_FOLDER
    )


def build_provider_clients(context: ApplicationContext) -> ProviderClients:
    """Compose the production adapters; a missing SEC identity becomes an unavailable SEC check, not a skipped one."""
    sec: SecTransport | SecUnavailable
    try:
        build_sec_production_provider(context)
    except AnalysisConfigurationError as exc:
        sec = SecUnavailable(str(exc))
    else:
        sec = SecTransport(fetch_json, (context.settings.sec_user_agent or "").strip())
    return ProviderClients(yahoo=YFinanceClient(), sec=sec, connection=ConnectionStep())


def build_provider_probe(context: ApplicationContext) -> ProviderProbe:
    """Build the automatic provider check of one operation from the context's settings.

    Each operation that reports a provider failure builds its own probe, which remembers its findings for that
    operation only, so a provider is tested at most once within it and no finding carries over to the next. The probe
    contacts no provider until a failure is reported.
    """
    return ProviderProbe(
        enabled=context.settings.provider_check,
        timeout_seconds=context.settings.provider_check_timeout_seconds,
        clients=lambda: build_provider_clients(context),
    )


def load_all_component_settings(context: ApplicationContext) -> None:
    """Load and validate the settings of every strategy that declares a settings model, and of the SEC adapter.

    Called once at startup, so an invalid file stops every command with one message.

    Raises:
        ComponentSettingsError: If a shipped file is missing, a file is not valid TOML or the values break a rule.
    """
    sec_edgar_settings(context)
    for descriptor in STRATEGIES:
        if descriptor.settings_type is not None:
            load_component_settings(descriptor.alias, descriptor.settings_type, context.settings.config_dir)


@contextmanager
def production_historical_client(
    context: ApplicationContext, provider: YFinanceClient, *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[CachedHistoricalDataClient]:
    """Borrow the Yahoo client and own historical storage for one analysis.

    Daily adjusted request identity matches the provider's download configuration.
    Reuse age comes from settings. Readiness is checked and storage initialized before
    fetching only when ``use_cache`` is True; the per-call ``use_cache`` gate on the
    yielded client's own methods is what actually skips reads/writes.
    """
    database = SQLiteDatabase(context.settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = context.settings.historical_cache_ttl_seconds
        yield CachedHistoricalDataClient(
            provider,
            SQLiteMarketDataRepository(database),
            request_variant=f"{YFINANCE_HISTORICAL_INTERVAL}:{YFINANCE_PRICE_ADJUSTMENT}",
            split_request_variant=f"{YFINANCE_HISTORICAL_INTERVAL}:{SPLIT_ADJUSTED_PRICE}",
            ttl=None if seconds is None else timedelta(seconds=seconds),
            clock=clock,
            quality_policy=HistoricalQualityPolicy(expected_adjustment=YFINANCE_PRICE_ADJUSTMENT),
        )
    finally:
        database.close()


@contextmanager
def production_financial_cache(
    context: ApplicationContext, *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[ResolvedInputSeriesCacheProtocol]:
    """Own one invocation's durable cache; schema upgrades remain explicit unless caching is disabled.

    Financial facts use configured residence age (unlimited by default) and
    temporal quality checks. Readiness is checked only when ``use_cache`` is True; the
    resolver's own per-call ``use_cache`` gate is what actually skips reads/writes, so
    disabling caching still never touches storage.
    """
    database = SQLiteDatabase(context.settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = context.settings.financial_cache_ttl_seconds
        yield SQLiteResolvedInputCache(
            database, ttl=None if seconds is None else timedelta(seconds=seconds), clock=clock
        )
    finally:
        database.close()


def production_instrument_profile_cache(
    context: ApplicationContext, database: SQLiteDatabase, *, clock: Callable[[], datetime]
) -> CachedInstrumentProfileResolver:
    """Build the durable instrument-profile cache over an already-open database.

    Unlike the historical and financial cache helpers above, this does not own or close ``database``: every caller
    already manages that lifecycle for its own reason (Analysis Run persistence, watchlist storage), and durable
    profiles are database-free lookups when the instrument-profile contract calls for staying live-only (no database is
    opened here or by any caller solely to obtain one of these).
    """
    seconds = context.settings.instrument_profile_ttl_seconds
    return CachedInstrumentProfileResolver(
        SQLiteInstrumentProfileRepository(database),
        ttl=None if seconds is None else timedelta(seconds=seconds),
        clock=clock,
    )


__all__ = [
    "build_provider_clients",
    "build_provider_probe",
    "build_sec_edgar_adapter",
    "build_sec_production_provider",
    "load_all_component_settings",
    "production_financial_cache",
    "production_historical_client",
    "production_instrument_profile_cache",
    "sec_edgar_settings",
]
