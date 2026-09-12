"""Exercise durable historical reuse with deterministic providers and clocks."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from alembic.config import Config
from pandas.testing import assert_frame_equal

from alembic import command
from src.config import ProjectSettings
from src.data.base_client import BaseDataClient, DataFetchError
from src.data.cached_client import CachedHistoricalDataClient
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.quality import HistoricalQualityPolicy, QualityDecision
from src.data.quality_reporting import quality_observer
from src.data.repositories import MarketDataCacheKey, SQLiteDatabase, SQLiteMarketDataRepository

NOW = datetime(2026, 9, 5, tzinfo=UTC)
START = "2025-01-01"


def test_rejected_cache_refreshes_once_and_preserves_snapshot_on_failure(
    database: SQLiteDatabase, tmp_path: Path
) -> None:
    provider = FakeProvider()
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    key = MarketDataCacheKey("ABC", "Fixture", date(2025, 1, 1), None, "daily")
    bad = replace(provider.data, context=replace(provider.data.context, currency="USD"))
    repository.put(key, bad, fetch_completed_at=NOW)
    client = CachedHistoricalDataClient(
        provider,
        repository,
        request_variant="daily",
        ttl=None,
        clock=lambda: NOW,
        quality_policy=HistoricalQualityPolicy(expected_currency="CAD"),
    )
    decisions: list[QualityDecision] = []
    provider.error = DataFetchError("offline")
    with quality_observer(decisions.append), pytest.raises(DataFetchError, match="offline"):
        client.fetch_data("ABC", START)
    assert len(provider.calls) == 1
    assert decisions[0].rule_id == "historical.currency"
    stored = repository.get(key)
    assert stored is not None
    assert stored.data.context.currency == "USD"
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}"))
    repository = SQLiteMarketDataRepository(reopened)
    provider.error = None
    second = CachedHistoricalDataClient(
        provider,
        repository,
        request_variant="daily",
        ttl=None,
        clock=lambda: NOW,
        quality_policy=HistoricalQualityPolicy(expected_currency="CAD"),
    )
    try:
        assert_frame_equal(second.fetch_data("ABC", START), provider.data.frame)
        assert len(provider.calls) == 2
        stored = repository.get(key)
        assert stored is not None
        assert stored.data.context.currency == "CAD"
    finally:
        reopened.close()


def test_bypass_enforces_quality_even_with_broken_observer(database: SQLiteDatabase) -> None:
    provider = FakeProvider()
    provider.data.frame.index = provider.data.frame.index[::-1]
    client = CachedHistoricalDataClient(provider, SQLiteMarketDataRepository(database), request_variant=None, ttl=None)

    def broken(_decision: QualityDecision) -> None:
        raise RuntimeError("observer unavailable")

    with quality_observer(broken), pytest.raises(DataFetchError, match="dates"):
        client.fetch_data("ABC", START)
    assert len(provider.calls) == 1


def test_failed_quality_refresh_never_replaces_stored_snapshot(database: SQLiteDatabase) -> None:
    provider = FakeProvider()
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    key = MarketDataCacheKey("ABC", "Fixture", date(2025, 1, 1), None, "daily")
    repository.put(key, provider.data, fetch_completed_at=NOW)
    provider.data = replace(provider.data, context=replace(provider.data.context, price_adjustment="unadjusted"))
    client = CachedHistoricalDataClient(
        provider,
        repository,
        request_variant="daily",
        ttl=timedelta(0),
        clock=lambda: NOW + timedelta(seconds=1),
        quality_policy=HistoricalQualityPolicy(expected_adjustment="adjusted"),
    )
    with pytest.raises(DataFetchError, match="conflicts"):
        client.fetch_data("ABC", START)
    stored = repository.get(key)
    assert stored is not None
    assert stored.data.context.price_adjustment == "adjusted"


class FakeProvider(BaseDataClient):
    """Count independent historical and quote requests without network access."""

    def __init__(self) -> None:
        """Prepare an independent deterministic payload and call history."""
        self.identity: str | None = "Fixture"
        self.calls: list[tuple[str, str, str | None]] = []
        self.quotes: list[str] = []
        self.error: Exception | None = None
        self.data = HistoricalMarketData(
            pd.DataFrame({"Close": [12.0, 13.0]}, index=pd.date_range(START, periods=2)),
            MarketDataContext(
                provider_id="Original",
                currency="CAD",
                observation_interval="1d",
                price_adjustment="adjusted",
                observation_count=2,
                data_as_of=date(2025, 1, 2),
            ),
        )

    @property
    def provider_id(self) -> str | None:
        return self.identity

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self.fetch_historical_data(ticker, start_date, end_date).frame

    def fetch_historical_data(self, ticker: str, start_date: str, end_date: str | None = None) -> HistoricalMarketData:
        self.calls.append((ticker, start_date, end_date))
        if self.error is not None:
            raise self.error
        return self.data

    def fetch_current_price(self, ticker: str) -> float:
        self.quotes.append(ticker)
        if self.error is not None:
            raise self.error
        return 99.0


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


def test_hit_all_boundaries_and_reopen(database: SQLiteDatabase, tmp_path: Path) -> None:
    provider = FakeProvider()
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    client = CachedHistoricalDataClient(
        provider, repository, request_variant="1d:adjusted", ttl=None, clock=lambda: NOW
    )
    assert client.fetch_historical_data("ABC", START).frame is provider.data.frame
    assert_frame_equal(client.fetch_data(" abc ", START), provider.data.frame)
    assert client.fetch_data_with_context("ABC", START).context == provider.data.context
    assert client.provider_id == "Fixture"
    entry = repository.get(MarketDataCacheKey("ABC", "fixture", date(2025, 1, 1), None, "1d:adjusted"))
    assert entry is not None
    assert entry.fetch_completed_at == NOW
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}"))
    try:
        provider.error = DataFetchError("offline")
        second = CachedHistoricalDataClient(
            provider, SQLiteMarketDataRepository(reopened), request_variant="1d:adjusted", ttl=None
        )
        assert_frame_equal(second.fetch_data("ABC", START), provider.data.frame)
    finally:
        reopened.close()
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("ttl", "age", "calls"),
    [
        (None, 10000, 1),
        (10, 10, 1),
        (10, 11, 2),
        (0, 0, 1),
        (0, 1, 2),
        (0, -1, 1),
    ],
)
def test_ttl(database: SQLiteDatabase, ttl: int | None, age: int, calls: int) -> None:
    provider = FakeProvider()
    now = NOW
    client = CachedHistoricalDataClient(
        provider,
        SQLiteMarketDataRepository(database, clock=lambda: now),
        request_variant="daily",
        ttl=None if ttl is None else timedelta(seconds=ttl),
        clock=lambda: now,
    )
    client.fetch_data("ABC", START)
    now += timedelta(seconds=age)
    client.fetch_data("ABC", START)
    assert len(provider.calls) == calls


def test_ranges_and_configuration_are_independent(database: SQLiteDatabase) -> None:
    provider = FakeProvider()
    repository = SQLiteMarketDataRepository(database)
    for variant in ("daily", "weekly"):
        for identity in ("first", "second"):
            provider.identity = identity
            client = CachedHistoricalDataClient(provider, repository, request_variant=variant, ttl=None)
            for start, end in ((START, None), (START, "2025-01-03"), ("2025-01-02", "2025-01-03")):
                client.fetch_data("ABC", start, end)
                client.fetch_data("ABC", start, end)
    assert len(provider.calls) == 12


@pytest.mark.parametrize("failure", ["provider", "empty", "missing", "nan", "inf", "text"])
def test_failed_refresh_preserves_prior_snapshot(database: SQLiteDatabase, failure: str) -> None:
    provider = FakeProvider()
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    now = NOW
    client = CachedHistoricalDataClient(
        provider, repository, request_variant="daily", ttl=timedelta(0), clock=lambda: now
    )
    original = client.fetch_data("ABC", START).copy()
    now += timedelta(seconds=1)
    if failure == "provider":
        provider.error = DataFetchError("offline")
    elif failure == "empty":
        provider.data.frame.drop(provider.data.frame.index, inplace=True)
    elif failure == "missing":
        provider.data.frame.rename(columns={"Close": "Other"}, inplace=True)
    else:
        invalid_values: dict[str, float | str] = {"nan": float("nan"), "inf": float("inf"), "text": "bad"}
        provider.data.frame["Close"] = invalid_values[failure]
        provider.data.frame["Extra"] = 1  # Unsupported shape must not hide invalid values.
    with pytest.raises(DataFetchError, match="offline|Historical"):
        client.fetch_data("ABC", START)
    entry = repository.get(MarketDataCacheKey("ABC", "Fixture", date(2025, 1, 1), None, "daily"))
    assert entry is not None
    assert entry.cached_at == NOW
    assert_frame_equal(entry.data.frame, original)


@pytest.mark.parametrize("reason", ["provider", "variant", "shape"])
def test_valid_bypass(database: SQLiteDatabase, reason: str, caplog: pytest.LogCaptureFixture) -> None:
    provider = FakeProvider()
    variant: str | None = "daily"
    if reason == "provider":
        provider.identity = None
    elif reason == "variant":
        variant = None
    else:
        provider.data.frame.attrs["custom"] = "retained"
    client = CachedHistoricalDataClient(
        provider, SQLiteMarketDataRepository(database), request_variant=variant, ttl=None
    )
    with caplog.at_level("DEBUG", logger="src.data.cached_client"):
        assert client.fetch_historical_data("ABC", START).frame is provider.data.frame
        assert client.fetch_historical_data("ABC", START).frame is provider.data.frame
    assert len(provider.calls) == 2
    assert "cache bypassed" in caplog.text


def test_quotes_never_touch_storage(database: SQLiteDatabase) -> None:
    provider = FakeProvider()
    client = CachedHistoricalDataClient(
        provider, SQLiteMarketDataRepository(database), request_variant="daily", ttl=None
    )
    client.fetch_data("ABC", START)
    database.close()
    assert client.fetch_current_price("ABC") == 99.0
    provider.error = DataFetchError("quote unavailable")
    with pytest.raises(DataFetchError, match="quote unavailable"):
        client.fetch_current_price("ABC")
    assert provider.quotes == ["ABC", "ABC"]
    assert len(provider.calls) == 1


def test_invalid_policy_and_clock(database: SQLiteDatabase) -> None:
    repository = SQLiteMarketDataRepository(database)
    with pytest.raises(ValueError, match="non-negative"):
        CachedHistoricalDataClient(FakeProvider(), repository, request_variant="daily", ttl=timedelta(seconds=-1))
    client = CachedHistoricalDataClient(
        FakeProvider(), repository, request_variant="daily", ttl=None, clock=lambda: datetime(2025, 1, 1)
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        client.fetch_data("ABC", START)
