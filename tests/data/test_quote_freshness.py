"""Quote retrieval age is independent of annual facts and cache insertion age."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic.config import Config

from alembic import command
from src.config import ProjectSettings
from src.core.analysis_status import CalculationStatus
from src.core.clock import FROZEN_CLOCK_SKEW_TOLERANCE
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.financial.quote_freshness import QuoteFreshnessPolicy, evaluate_quote_freshness
from src.data.financial.resolver import InputResolver
from src.data.repositories import SQLiteDatabase, SQLiteResolvedInputCache
from src.data.yfinance import YFinanceClient, YFinanceFinancialFactsAdapter, YFinanceQuote

NOW = datetime(2026, 9, 11, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age", "status"),
    [
        (299, "recent_retrieval"),
        (300, "recent_retrieval"),
        (301, "expired"),
        (-1, "recent_retrieval"),
        (0, "recent_retrieval"),
    ],
)
def test_retrieval_boundary(age: int, status: str) -> None:
    """Equality is eligible; future and expired evidence are distinct."""
    value = ResolvedInput(
        "current_price",
        20.0,
        SourceKind.PROVIDER,
        NOW,
        provider_id="yfinance",
        retrieved_at=NOW - timedelta(seconds=age),
    )
    evidence = evaluate_quote_freshness(value, now=NOW, policy=QuoteFreshnessPolicy())
    assert evidence.status == status
    assert evidence.market_observed_at is None


def test_retrieved_at_just_inside_the_skew_tolerance_is_recent_retrieval_with_zero_age() -> None:
    """A quote retrieved moments after a frozen per-run clock is not a data problem."""
    skew = FROZEN_CLOCK_SKEW_TOLERANCE
    value = ResolvedInput(
        "current_price", 20.0, SourceKind.PROVIDER, NOW, provider_id="yfinance", retrieved_at=NOW + skew
    )
    evidence = evaluate_quote_freshness(value, now=NOW, policy=QuoteFreshnessPolicy())
    assert evidence.status == "recent_retrieval"
    assert evidence.retrieval_age_seconds == 0.0


def test_retrieved_at_just_beyond_the_skew_tolerance_is_still_future_timestamp() -> None:
    """A retrieval far ahead of the run's own clock is still rejected, not silently accepted."""
    skew = FROZEN_CLOCK_SKEW_TOLERANCE + timedelta(seconds=1)
    value = ResolvedInput(
        "current_price", 20.0, SourceKind.PROVIDER, NOW, provider_id="yfinance", retrieved_at=NOW + skew
    )
    evidence = evaluate_quote_freshness(value, now=NOW, policy=QuoteFreshnessPolicy())
    assert evidence.status == "future_timestamp"


def test_observed_at_just_inside_the_skew_tolerance_is_recent_retrieval() -> None:
    """A market trade during the resolver's own live fetch is not a future-dated observation."""
    skew = FROZEN_CLOCK_SKEW_TOLERANCE
    value = ResolvedInput(
        "current_price",
        20.0,
        SourceKind.PROVIDER,
        NOW,
        provider_id="yfinance",
        retrieved_at=NOW,
        observed_at=NOW + skew,
    )
    evidence = evaluate_quote_freshness(value, now=NOW, policy=QuoteFreshnessPolicy())
    assert evidence.status == "recent_retrieval"
    assert evidence.market_observed_at == NOW + skew


def test_observed_at_just_beyond_the_skew_tolerance_is_still_future_timestamp() -> None:
    """A market observation far ahead of the run's own clock is still rejected."""
    skew = FROZEN_CLOCK_SKEW_TOLERANCE + timedelta(seconds=1)
    value = ResolvedInput(
        "current_price",
        20.0,
        SourceKind.PROVIDER,
        NOW,
        provider_id="yfinance",
        retrieved_at=NOW,
        observed_at=NOW + skew,
    )
    evidence = evaluate_quote_freshness(value, now=NOW, policy=QuoteFreshnessPolicy())
    assert evidence.status == "future_timestamp"


def test_unknown_retrieval_is_not_made_fresh_by_resolution() -> None:
    """Resolution time cannot stand in for original retrieval."""
    value = ResolvedInput("current_price", 20.0, SourceKind.PROVIDER, NOW, provider_id="yfinance")
    assert evaluate_quote_freshness(value, now=NOW).status == "unknown_retrieval_time"


class QuoteProvider:
    """Synthetic provider with controllable response time and failure."""

    def __init__(self) -> None:
        """Start at the fixed clock with a successful provider."""
        self.now = NOW
        self.calls = 0
        self.fail = False

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        """Return a fresh response or one explicit transport failure."""
        self.calls += 1
        if self.fail:
            raise FinancialProviderError("synthetic refresh failed")
        return (
            ProviderFact(
                subject_kind=FinancialSubjectKind.SECURITY,
                subject_id="ACME",
                field_name=request.field_name,
                value=20.0,
                units=FinancialUnit.CURRENCY_PER_SHARE,
                provider_id="yfinance",
                provider_field="fast_info.last_price",
                retrieved_at=self.now,
                currency="USD",
            ),
        )


@pytest.mark.parametrize(("age", "calls"), [(299, 1), (300, 1), (301, 2)])
def test_cache_age_uses_original_retrieval(age: int, calls: int) -> None:
    """A real resolver/cache round trip preserves retrieval and refreshes once."""
    provider = QuoteProvider()
    cache = InMemoryResolvedInputCache(clock=lambda: provider.now)
    resolver = InputResolver(provider, cache, clock=lambda: provider.now)
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")
    first = resolver.resolve(request)
    provider.now += timedelta(seconds=age)
    second = resolver.resolve(request)
    assert provider.calls == calls
    assert first.resolved_input is not None
    assert second.resolved_input is not None
    assert second.resolved_input.retrieved_at == (NOW if calls == 1 else provider.now)
    assert second.quote_freshness is not None
    assert second.quote_freshness.retrieval_age_seconds == (age if calls == 1 else 0)


def test_expired_quote_refresh_failure_never_returns_stale_value() -> None:
    """A usable old numeric value cannot override failed freshness evidence."""
    provider = QuoteProvider()
    resolver = InputResolver(
        provider, InMemoryResolvedInputCache(clock=lambda: provider.now), clock=lambda: provider.now
    )
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")
    assert resolver.resolve(request).resolved_input is not None
    provider.now += timedelta(hours=14)
    provider.fail = True
    result = resolver.resolve(request)
    assert result.resolved_input is None
    assert result.status.value == "provider_error"
    assert provider.calls == 2


def test_zero_ttl_bypass_and_override_do_not_reuse_quote() -> None:
    """Zero disables cache hits even at the same clock tick; overrides do not fetch."""
    provider = QuoteProvider()
    resolver = InputResolver(
        provider,
        InMemoryResolvedInputCache(clock=lambda: NOW),
        clock=lambda: NOW,
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(0)),
    )
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")
    resolver.resolve(request)
    resolver.resolve(request)
    resolver.resolve(request, use_cache=False)
    override = resolver.resolve(request, override=15.0)
    assert provider.calls == 3
    assert override.quote_freshness is not None
    assert override.quote_freshness.status == "user_supplied"


def test_legacy_yahoo_timestamp_is_not_market_observation() -> None:
    """Prior adapter retrieval surrogates remain explicitly unverified."""
    value = ResolvedInput(
        "current_price",
        20.0,
        SourceKind.PROVIDER,
        NOW,
        provider_id="yfinance",
        retrieved_at=NOW,
        observed_at=NOW,
        notes=("observed_at and available_at conservatively use retrieval time",),
    )
    assert evaluate_quote_freshness(value, now=NOW).market_observed_at is None
    assert evaluate_quote_freshness(replace(value, as_of=NOW), now=NOW).status == "historical"


def test_yahoo_adapter_quote_round_trips_through_real_sqlite(tmp_path: Path) -> None:
    """The descriptive quote basis must agree with its persisted request identity."""
    settings = ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'quote.sqlite3').as_posix()}")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    client = MagicMock(spec=YFinanceClient)
    client.fetch_current_quote.return_value = YFinanceQuote(87.83, "USD")
    database = SQLiteDatabase(settings)
    try:
        resolver = InputResolver(
            YFinanceFinancialFactsAdapter(client=client, clock=lambda: NOW),
            SQLiteResolvedInputCache(database, clock=lambda: NOW),
            clock=lambda: NOW,
        )
        request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")
        first = resolver.resolve(request)
        second = resolver.resolve(request)
        assert first.resolved_input is not None
        assert second.resolved_input is not None
        assert second.resolved_input.source_kind is SourceKind.CACHE
        assert second.resolved_input.basis == "latest_provider_quote"
        assert second.resolved_input.retrieved_at == NOW
        assert second.resolved_input.observed_at is None
        client.fetch_current_quote.assert_called_once()
    finally:
        database.close()


class _TradingHoursQuoteProvider:
    """Return one CURRENT_PRICE fact with independently controllable retrieved/observed times."""

    def __init__(self, *, retrieved_at: datetime, observed_at: datetime, available_at: datetime | None = None) -> None:
        """Fix each timestamp independently of the resolver's own frozen clock."""
        self._retrieved_at = retrieved_at
        self._observed_at = observed_at
        self._available_at = available_at

    def fetch_facts(
        self, request: FinancialFactRequest, *, effective_as_of: datetime | None = None
    ) -> tuple[ProviderFact, ...]:
        """Return the fixed quote fact regardless of the requested field."""
        del effective_as_of
        return (
            ProviderFact(
                subject_kind=FinancialSubjectKind.SECURITY,
                subject_id=request.subject_id,
                field_name=request.field_name,
                value=20.0,
                units=FinancialUnit.CURRENCY_PER_SHARE,
                provider_id="yfinance",
                provider_field="fast_info.last_price",
                retrieved_at=self._retrieved_at,
                observed_at=self._observed_at,
                available_at=self._available_at,
                currency="USD",
            ),
        )


def test_resolver_accepts_a_quote_that_ticked_during_the_run_trading_hours_case() -> None:
    """A market trade between run start and the live fetch is not a future-dated observation.

    ``executed_at`` stands in for the resolver's own frozen clock; the provider's response is
    stamped later, once the live fetch actually completes, exactly as a real trading-hours quote
    would be.
    """
    executed_at = NOW
    provider = _TradingHoursQuoteProvider(
        retrieved_at=executed_at + timedelta(seconds=45), observed_at=executed_at + timedelta(seconds=30)
    )
    resolver = InputResolver(provider, InMemoryResolvedInputCache(clock=lambda: executed_at), clock=lambda: executed_at)
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")

    result = resolver.resolve(request)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.quote_freshness is not None
    assert result.quote_freshness.status == "recent_retrieval"


def test_resolver_rejects_a_quote_ticked_beyond_the_skew_tolerance() -> None:
    """An observation far beyond the tolerance is still rejected, not silently accepted.

    Rejection happens at the earlier, generic ``evaluate_freshness`` gate (``observation_age``,
    now the single owner of this comparison), before the quote-specific ``evaluate_quote_freshness``
    is ever reached — so unlike the accepted case, ``quote_freshness`` stays unset here.
    """
    executed_at = NOW
    beyond_tolerance = FROZEN_CLOCK_SKEW_TOLERANCE + timedelta(seconds=1)
    provider = _TradingHoursQuoteProvider(
        retrieved_at=executed_at + timedelta(seconds=5), observed_at=executed_at + beyond_tolerance
    )
    resolver = InputResolver(provider, InMemoryResolvedInputCache(clock=lambda: executed_at), clock=lambda: executed_at)
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")

    result = resolver.resolve(request)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None
    assert result.quote_freshness is None
    assert result.reason is not None
    assert "observation_age" in result.reason


def test_same_run_cache_round_trip_tolerates_a_quote_ticked_after_the_frozen_clock() -> None:
    """A quote cached earlier in the same run is not penalized for its own timing.

    Read back against the same frozen clock, it must not be penalized for its own
    observed_at/available_at sitting a few seconds ahead of that clock. This exercises
    ``_try_cache_hit`` specifically (the second ``resolve()`` call is a cache hit,
    not a fresh provider fetch) — the same tolerance must apply there too, via the same
    ``evaluate_freshness`` gate, not just on the initial fetch path.
    """
    executed_at = NOW
    provider = _TradingHoursQuoteProvider(
        retrieved_at=executed_at + timedelta(seconds=45),
        observed_at=executed_at + timedelta(seconds=30),
        available_at=executed_at + timedelta(seconds=30),
    )
    cache = InMemoryResolvedInputCache(clock=lambda: executed_at)
    resolver = InputResolver(provider, cache, clock=lambda: executed_at)
    request = FinancialFactRequest(FinancialSubjectKind.SECURITY, "ACME", FinancialField.CURRENT_PRICE, "yfinance")

    first = resolver.resolve(request)
    second = resolver.resolve(request)

    assert first.status is CalculationStatus.OK
    assert first.resolved_input is not None
    assert second.status is CalculationStatus.OK
    assert second.resolved_input is not None
    assert second.resolved_input.source_kind is SourceKind.CACHE
    assert second.quote_freshness is not None
    assert second.quote_freshness.status == "recent_retrieval"
