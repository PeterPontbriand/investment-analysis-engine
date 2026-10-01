"""An ``--as-of`` Momentum run fetches history only up to the boundary (ESC-22).

The production historical cache client validates every frame it fetches, so a run that fetched the
whole history would fail on an invalid bar dated after the boundary even though that bar never reaches
the calculation. The resolver therefore asks the provider for a window that ends the day after the
boundary's UTC date (providers treat the end date as exclusive); the strict truncation to bars at or
before the boundary stays.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from alembic.config import Config

from alembic import command
from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from src.config import ProjectSettings
from src.data.base_client import BaseDataClient
from src.data.cached_client import CachedHistoricalDataClient
from src.data.market_data import HistoricalMarketData, MarketDataContext, NoEligibleObservationsError
from src.data.quality import HistoricalDataQualityError
from src.data.repositories import MarketDataCacheKey, SQLiteDatabase, SQLiteMarketDataRepository

START = "2026-01-01"
VARIANT = "1d:adjusted"
EXECUTED_AT = datetime(2026, 3, 1, tzinfo=UTC)
CONFIG = MomentumConfig(short_window=2, long_window=5, rsi_period=2)
BAR_COUNT = 20
BOUNDARY_DAY = 10  # the bar dated 2026-01-11
BOUNDARY = datetime(2026, 1, 11, 23, 59, 59, tzinfo=UTC)


class _EndDateProvider(BaseDataClient):
    """Daily bars with Yahoo's semantics: ``end_date`` is exclusive, and ``None`` means everything."""

    def __init__(self, closes: list[float], *, stamp_offset: timedelta = timedelta(0)) -> None:
        index = pd.DatetimeIndex(pd.date_range(START, periods=len(closes))) + stamp_offset
        self._frame = pd.DataFrame({"Close": closes}, index=index)
        self.calls: list[tuple[str, str, str | None]] = []

    @property
    def provider_id(self) -> str:
        return "Fixture"

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self.fetch_historical_data(ticker, start_date, end_date, use_cache=True).frame

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool = True
    ) -> HistoricalMarketData:
        del use_cache
        self.calls.append((ticker, start_date, end_date))
        frame = self._frame
        if end_date is not None:
            frame = frame.loc[frame.index < pd.Timestamp(end_date)]
        frame = frame.copy()
        return HistoricalMarketData(
            frame,
            MarketDataContext(
                provider_id="Fixture",
                observation_interval="1d",
                data_as_of=frame.index[-1].date() if len(frame) else None,
                currency="USD",
                observation_count=len(frame),
                price_adjustment="adjusted",
            ),
        )

    def fetch_current_price(self, ticker: str) -> float:
        raise NotImplementedError


def _closes(*, bad_at: int | None = None) -> list[float]:
    closes = [float(10 + day) for day in range(BAR_COUNT)]
    if bad_at is not None:
        closes[bad_at] = float("nan")
    return closes


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


def _client(provider: _EndDateProvider, database: SQLiteDatabase) -> CachedHistoricalDataClient:
    repository = SQLiteMarketDataRepository(database, clock=lambda: EXECUTED_AT)
    return CachedHistoricalDataClient(
        provider, repository, request_variant=VARIANT, ttl=None, clock=lambda: EXECUTED_AT
    )


def _run(client: CachedHistoricalDataClient, *, as_of: datetime | None, use_cache: bool = True) -> MomentumRun:
    analyzer = MomentumAnalyzer(market_data_provider=client, start_date=START)
    context = AnalysisContext(as_of=as_of, executed_at=EXECUTED_AT, use_cache=use_cache)
    return analyzer.run_analysis("ACME", CONFIG, context)


def _stored(database: SQLiteDatabase, end: date | None) -> pd.DataFrame | None:
    repository = SQLiteMarketDataRepository(database, clock=lambda: EXECUTED_AT)
    entry = repository.get(MarketDataCacheKey("ACME", "Fixture", date.fromisoformat(START), end, VARIANT))
    return None if entry is None else entry.data.frame


def test_an_invalid_bar_after_the_boundary_does_not_fail_an_as_of_run_on_a_cache_miss(
    database: SQLiteDatabase,
) -> None:
    provider = _EndDateProvider(_closes(bad_at=BAR_COUNT - 1))

    run = _run(_client(provider, database), as_of=BOUNDARY)

    assert run.metrics.current_price == 20.0  # the 2026-01-11 close
    assert provider.calls == [("ACME", START, "2026-01-12")]


def test_an_invalid_bar_after_the_boundary_does_not_fail_an_as_of_run_on_a_cache_hit(
    database: SQLiteDatabase,
) -> None:
    provider = _EndDateProvider(_closes(bad_at=BAR_COUNT - 1))
    client = _client(provider, database)
    first = _run(client, as_of=BOUNDARY)

    second = _run(client, as_of=BOUNDARY)

    assert len(provider.calls) == 1
    assert second.metrics.current_price == first.metrics.current_price == 20.0
    assert second.price_inputs[-1].source_kind.value == "cache"


def test_an_invalid_bar_after_the_boundary_does_not_fail_an_as_of_run_with_no_cache(
    database: SQLiteDatabase,
) -> None:
    provider = _EndDateProvider(_closes(bad_at=BAR_COUNT - 1))

    run = _run(_client(provider, database), as_of=BOUNDARY, use_cache=False)

    assert run.metrics.current_price == 20.0
    assert provider.calls == [("ACME", START, "2026-01-12")]
    assert _stored(database, date(2026, 1, 12)) is None


@pytest.mark.parametrize("bad_at", [BOUNDARY_DAY, BOUNDARY_DAY - 3, 0])
@pytest.mark.parametrize("use_cache", [True, False])
def test_an_invalid_bar_at_or_before_the_boundary_still_fails_the_run(
    database: SQLiteDatabase, bad_at: int, use_cache: bool
) -> None:
    provider = _EndDateProvider(_closes(bad_at=bad_at))

    with pytest.raises(HistoricalDataQualityError):
        _run(_client(provider, database), as_of=BOUNDARY, use_cache=use_cache)


def test_a_cached_as_of_window_holds_no_bar_after_the_boundary(database: SQLiteDatabase) -> None:
    provider = _EndDateProvider(_closes())

    _run(_client(provider, database), as_of=BOUNDARY)

    stored = _stored(database, date(2026, 1, 12))
    assert stored is not None
    assert len(stored) == BOUNDARY_DAY + 1
    assert stored.index.max() <= pd.Timestamp(BOUNDARY.replace(tzinfo=None))
    assert _stored(database, None) is None


def test_a_live_run_fetches_and_caches_the_full_history_separately(database: SQLiteDatabase) -> None:
    provider = _EndDateProvider(_closes())
    client = _client(provider, database)

    _run(client, as_of=BOUNDARY)
    live = _run(client, as_of=None)

    assert provider.calls == [("ACME", START, "2026-01-12"), ("ACME", START, None)]
    assert live.metrics.current_price == 29.0
    full = _stored(database, None)
    assert full is not None
    assert len(full) == BAR_COUNT
    bounded = _stored(database, date(2026, 1, 12))
    assert bounded is not None
    assert len(bounded) == BOUNDARY_DAY + 1


UTC_MINUS_FIVE = timezone(timedelta(hours=-5))


@pytest.mark.parametrize(
    ("as_of", "expected_end"),
    [
        (datetime(2026, 1, 11, tzinfo=UTC), "2026-01-12"),
        (datetime(2026, 1, 11, 23, 59, 59, tzinfo=UTC), "2026-01-12"),
        (datetime(2026, 1, 11, 18, 59, 59, tzinfo=UTC_MINUS_FIVE), "2026-01-12"),
        (datetime(2026, 1, 11, 19, 0, tzinfo=UTC_MINUS_FIVE), "2026-01-13"),
    ],
)
def test_the_requested_window_ends_the_day_after_the_boundarys_utc_date(
    database: SQLiteDatabase, as_of: datetime, expected_end: str
) -> None:
    provider = _EndDateProvider(_closes())

    _run(_client(provider, database), as_of=as_of)

    assert provider.calls[0][2] == expected_end


def test_a_boundary_on_the_last_day_of_a_month_rolls_the_end_date_over() -> None:
    provider = _EndDateProvider(_closes())
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date=START)

    analyzer.run_analysis(
        "ACME",
        CONFIG,
        AnalysisContext(as_of=datetime(2026, 1, 31, tzinfo=UTC), executed_at=EXECUTED_AT, use_cache=True),
    )

    assert provider.calls[0][2] == "2026-02-01"


def test_an_invalid_bar_dated_on_the_boundary_day_but_stamped_after_the_boundary_instant_still_fails(
    database: SQLiteDatabase,
) -> None:
    """The one remaining case (ESC-22).

    Daily bars are stamped at midnight, which is never after a boundary on the same date, so this cannot
    occur for them. A provider that stamps a daily bar later in its date can return one that is fetched
    (it falls inside the requested window) yet truncated, and an invalid one still stops the run.
    """
    provider = _EndDateProvider(_closes(bad_at=BOUNDARY_DAY), stamp_offset=timedelta(hours=12))
    boundary = datetime(2026, 1, 11, 6, tzinfo=UTC)

    with pytest.raises(HistoricalDataQualityError):
        _run(_client(provider, database), as_of=boundary)


def test_a_valid_bar_dated_on_the_boundary_day_but_stamped_after_the_boundary_instant_is_dropped(
    database: SQLiteDatabase,
) -> None:
    provider = _EndDateProvider(_closes(), stamp_offset=timedelta(hours=12))

    run = _run(_client(provider, database), as_of=datetime(2026, 1, 11, 6, tzinfo=UTC))

    assert run.metrics.current_price == 19.0  # the 2026-01-10 bar; the 2026-01-11 12:00 bar is later


@pytest.mark.parametrize("use_cache", [True, False])
def test_a_boundary_before_the_series_start_date_reports_no_eligible_observations(
    database: SQLiteDatabase, use_cache: bool
) -> None:
    """Such a window cannot be requested, so the run fetches as a live run does and nothing is eligible."""
    provider = _EndDateProvider(_closes())

    with pytest.raises(NoEligibleObservationsError, match="No price history is available at or before"):
        _run(_client(provider, database), as_of=datetime(1990, 1, 1, tzinfo=UTC), use_cache=use_cache)

    assert provider.calls == [("ACME", START, None)]
