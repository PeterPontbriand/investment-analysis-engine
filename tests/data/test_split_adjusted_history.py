"""The split-adjusted close and split history: types, the Yahoo request, the cache and the unchanged Momentum series."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import BaseDataClient, DataFetchError
from investment_analysis_engine.data.cached_client import CachedHistoricalDataClient
from investment_analysis_engine.data.financial.provenance import SourceKind
from investment_analysis_engine.data.market_data import (
    SPLIT_ADJUSTED_PRICE,
    HistoricalMarketData,
    MarketDataContext,
    NoEligibleObservationsError,
    SplitAdjustedHistory,
    SplitAdjustedHistoryProvider,
    SplitEvent,
    SplitHistoryEndsBeforeRequestError,
    split_adjusted_close_on_or_before,
)
from investment_analysis_engine.data.repositories.market_data import MarketDataCacheKey, SQLiteMarketDataRepository
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from tests._migrated_database import DATABASE_FILE_NAME

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "split_history"
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
VARIANT = "1d:split_adjusted"
START = "2024-04-01"


def _history(name: str = "nvda", **changes: Any) -> SplitAdjustedHistory:
    document = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    frame = pd.DataFrame(
        {"Close": [float(value) for _day, value in document["close"]]},
        index=pd.DatetimeIndex([day for day, _value in document["close"]]),
    )
    history = SplitAdjustedHistory(
        close=frame,
        events=tuple(SplitEvent(date.fromisoformat(day), ratio) for day, ratio in document["events"]),
        context=MarketDataContext(
            provider_id="yfinance",
            observation_interval="1d",
            data_as_of=frame.index[-1].date(),
            currency=document["currency"],
            observation_count=len(frame),
            price_adjustment=SPLIT_ADJUSTED_PRICE,
        ),
        adjustment_date=date.fromisoformat(document["adjustment_date"]),
    )
    return replace(history, **changes)


def test_the_fixture_checksums_match_the_files() -> None:
    lines = (FIXTURES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ")[1]: line.split("  ")[0] for line in lines}
    assert set(listed) == {path.name for path in FIXTURES.glob("*.json")}
    for name, digest in listed.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


# --- the types ------------------------------------------------------------


def test_a_history_holds_one_close_column_ordered_events_and_the_split_only_basis() -> None:
    history = _history()
    assert list(history.close.columns) == ["Close"]
    assert history.events == (SplitEvent(date(2024, 6, 10), 10.0),)
    assert history.context.price_adjustment == "split_adjusted"
    assert history.adjustment_date == date(2026, 10, 26)


def test_a_malformed_history_is_refused() -> None:
    good = _history()
    frame = good.close
    for change, message in (
        ({"close": frame.assign(Open=1.0)}, "single column Close"),
        ({"close": frame.iloc[0:0]}, "single column Close"),
        ({"close": frame.iloc[::-1]}, "ascending"),
        ({"close": frame.assign(Close=float("nan"))}, "finite"),
        ({"close": frame.set_axis(range(len(frame)))}, "ascending date-like"),
        ({"context": replace(good.context, price_adjustment="adjusted")}, "split-only"),
        ({"adjustment_date": datetime(2026, 10, 26)}, "calendar date"),
        ({"events": (SplitEvent(date(2024, 6, 10), 2.0), SplitEvent(date(2024, 6, 10), 3.0))}, "ordered by ex-date"),
        ({"events": (SplitEvent(date(2024, 7, 1), 2.0), SplitEvent(date(2024, 6, 10), 3.0))}, "ordered by ex-date"),
        ({"events": (SplitEvent(date(2027, 1, 1), 2.0),)}, "follow the adjustment date"),
    ):
        with pytest.raises(ValueError, match=message):
            replace(good, **change)


def test_the_close_is_the_last_session_on_or_before_the_requested_day() -> None:
    history = _history()
    session, close = split_adjusted_close_on_or_before(history, date(2024, 4, 30))
    assert session == date(2024, 4, 30)
    assert close == pytest.approx(86.402, abs=1e-3)
    assert split_adjusted_close_on_or_before(history, date(2024, 4, 28))[0] == date(2024, 4, 26)
    assert split_adjusted_close_on_or_before(history, date(2026, 10, 26))[0] == date(2024, 6, 11)
    with pytest.raises(NoEligibleObservationsError, match="No close exists on or before 2024-04-25"):
        split_adjusted_close_on_or_before(history, date(2024, 4, 25))


def test_the_close_of_a_frame_indexed_by_python_dates_is_found_too() -> None:
    history = _history()
    plain = replace(history, close=history.close.set_axis([ts.date() for ts in history.close.index]))
    assert split_adjusted_close_on_or_before(plain, date(2024, 5, 1))[0] == date(2024, 5, 1)


# --- the Yahoo request ------------------------------------------------------------


def _download_frame(*, splits: list[float] | None = None, close: list[float] | None = None) -> pd.DataFrame:
    close = close or [100.0, 101.0, 102.0]
    return pd.DataFrame(
        {
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Adj Close": [value * 0.9 for value in close],
            "Volume": [1] * len(close),
            "Dividends": [0.0] * len(close),
            "Stock Splits": splits if splits is not None else [0.0] * len(close),
        },
        index=pd.to_datetime(["2026-10-22", "2026-10-23", "2026-10-26"]),
    )


def _fetch(frame: object, *, ticker: str = "TEST") -> SplitAdjustedHistory:
    client = YFinanceClient(clock=lambda: NOW)
    with (
        patch("investment_analysis_engine.data.yfinance.client.yf.download", return_value=frame) as download,
        patch("investment_analysis_engine.data.yfinance.client.yf.Ticker") as mock_ticker,
    ):
        mock_ticker.return_value.fast_info = {"currency": "usd"}
        result = client.fetch_split_adjusted_history(ticker, "2026-01-01")
    arguments = download.call_args.kwargs
    assert arguments["auto_adjust"] is False
    assert arguments["actions"] is True
    assert arguments["interval"] == "1d"
    assert "end" not in arguments
    return result


def test_the_close_is_read_from_an_unadjusted_download_and_adj_close_is_never_used() -> None:
    result = _fetch(_download_frame(splits=[0.0, 2.0, 0.0]))

    assert list(result.close.columns) == ["Close"]
    assert result.close["Close"].tolist() == [100.0, 101.0, 102.0]
    assert result.events == (SplitEvent(date(2026, 10, 23), 2.0),)
    assert result.adjustment_date == date(2026, 10, 26)
    assert (result.context.price_adjustment, result.context.currency, result.context.data_as_of) == (
        "split_adjusted",
        "USD",
        date(2026, 10, 26),
    )
    assert result.resolution is not None
    assert result.resolution.source_kind is SourceKind.PROVIDER
    # Adj Close differs from Close in the mock: reading it would have changed the closes.
    assert not (result.close["Close"] == _download_frame()["Adj Close"]).any()


def test_a_download_without_a_split_has_an_empty_event_list_and_a_flattened_frame_is_read() -> None:
    assert _fetch(_download_frame()).events == ()
    frame = _download_frame()
    frame.columns = pd.MultiIndex.from_product([frame.columns, ["TEST"]])
    assert _fetch(frame).close["Close"].tolist() == [100.0, 101.0, 102.0]


def test_a_stock_dividend_is_a_fractional_split_and_nan_closes_are_dropped() -> None:
    result = _fetch(_download_frame(splits=[0.0, 1.05, 0.0], close=[100.0, float("nan"), 102.0]))
    assert result.events == (SplitEvent(date(2026, 10, 23), 1.05),)
    assert result.close["Close"].tolist() == [100.0, 102.0]


@pytest.mark.parametrize("missing", ["Close", "Stock Splits"])
def test_a_download_missing_a_required_column_is_an_unexpected_response_not_no_splits(missing: str) -> None:
    with pytest.raises(DataFetchError, match=f"missing columns: {missing}") as raised:
        _fetch(_download_frame().drop(columns=[missing]))
    assert raised.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


def test_an_unusable_ratio_or_an_empty_or_non_frame_answer_is_classified() -> None:
    for splits in ([0.0, -2.0, 0.0], [0.0, float("inf"), 0.0]):
        with pytest.raises(DataFetchError) as raised:
            _fetch(_download_frame(splits=splits))
        assert raised.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE
    for answer, kind in (
        (pd.DataFrame(), ProviderFailureKind.NO_DATA),
        (None, ProviderFailureKind.NO_DATA),
        (_download_frame(close=[float("nan")] * 3), ProviderFailureKind.NO_DATA),
        ("not a frame", ProviderFailureKind.UNEXPECTED_RESPONSE),
    ):
        with pytest.raises(DataFetchError) as raised:
            _fetch(answer)
        assert raised.value.kind is kind


def test_a_failed_download_keeps_the_classified_provider_failure() -> None:
    with (
        patch("investment_analysis_engine.data.yfinance.client.yf.download", side_effect=YFRateLimitError()),
        pytest.raises(DataFetchError) as raised,
    ):
        YFinanceClient().fetch_split_adjusted_history("TEST", "2026-01-01")
    assert raised.value.kind is ProviderFailureKind.RATE_LIMITED


def test_momentums_series_is_still_the_dividend_adjusted_one() -> None:
    frame = _download_frame()[["Open", "High", "Low", "Close", "Volume"]]
    with (
        patch("investment_analysis_engine.data.yfinance.client.yf.download", return_value=frame) as download,
        patch("investment_analysis_engine.data.yfinance.client.yf.Ticker") as mock_ticker,
    ):
        mock_ticker.return_value.fast_info = {"currency": "USD"}
        data = YFinanceClient().fetch_data_with_context("TEST", "2026-01-01")
    assert download.call_args.kwargs["auto_adjust"] is True
    assert "actions" not in download.call_args.kwargs
    assert data.context.price_adjustment == "adjusted"


# --- the cache ------------------------------------------------------------


class _Provider(BaseDataClient):
    """A provider that serves a split-adjusted history and counts the requests."""

    def __init__(self, history: SplitAdjustedHistory) -> None:
        self.history = history
        self.calls = 0

    @property
    def provider_id(self) -> str:
        return "yfinance"

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:  # noqa: ARG002
        raise AssertionError(f"unused {self!r}")

    def fetch_current_price(self, ticker: str) -> float:  # noqa: ARG002
        raise AssertionError(f"unused {self!r}")

    def fetch_split_adjusted_history(self, ticker: str, start_date: str, *, use_cache: bool) -> SplitAdjustedHistory:
        assert isinstance(use_cache, bool)
        assert ticker
        assert start_date
        self.calls += 1
        return replace(self.history, resolution=None)


def _client(
    provider: BaseDataClient,
    database: SQLiteDatabase,
    *,
    clock: datetime = NOW,
    ttl: timedelta | None = None,
    variant: str | None = VARIANT,
) -> CachedHistoricalDataClient:
    return CachedHistoricalDataClient(
        provider,
        SQLiteMarketDataRepository(database, clock=lambda: clock),
        request_variant="1d:adjusted",
        ttl=ttl,
        clock=lambda: clock,
        split_request_variant=variant,
    )


def test_a_cached_response_is_returned_with_its_original_adjustment_date(migrated_database: SQLiteDatabase) -> None:
    provider = _Provider(_history())
    first = _client(provider, migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)
    later = _client(provider, migrated_database, clock=NOW + timedelta(days=30)).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True
    )

    assert provider.calls == 1
    assert first.resolution is not None
    assert first.resolution.source_kind is SourceKind.PROVIDER
    assert later.resolution is not None
    assert later.resolution.source_kind is SourceKind.CACHE
    assert later.resolution.cache_schema_version == 1
    assert later.adjustment_date == date(2026, 10, 26)
    assert later.events == first.events == (SplitEvent(date(2024, 6, 10), 10.0),)
    pd.testing.assert_frame_equal(later.close, first.close, check_freq=False)
    assert later.context == first.context


def test_the_live_path_refuses_a_response_adjusted_on_another_day(migrated_database: SQLiteDatabase) -> None:
    provider = _Provider(_history())
    _client(provider, migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)

    same_day = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, adjusted_on=date(2026, 10, 26)
    )
    assert same_day.resolution is not None
    assert same_day.resolution.source_kind is SourceKind.CACHE
    assert provider.calls == 1

    next_day = date(2026, 10, 27)
    fetched = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, adjusted_on=next_day
    )
    assert provider.calls == 2
    assert fetched.resolution is not None
    assert fetched.resolution.source_kind is SourceKind.PROVIDER


def test_the_two_adjustment_modes_never_share_an_entry(migrated_database: SQLiteDatabase) -> None:
    repository = SQLiteMarketDataRepository(migrated_database, clock=lambda: NOW)
    history = _history()
    dividend_adjusted = HistoricalMarketData(
        history.close.assign(Open=1.0, High=1.0, Low=1.0, Volume=1.0),
        replace(history.context, price_adjustment="adjusted"),
    )
    start = date(2024, 4, 1)
    repository.put(MarketDataCacheKey("NVDA", "yfinance", start, None, "1d:adjusted"), dividend_adjusted)
    provider = _Provider(history)
    fetched = _client(provider, migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)

    assert provider.calls == 1
    assert fetched.context.price_adjustment == "split_adjusted"
    plain = repository.get(MarketDataCacheKey("NVDA", "yfinance", start, None, "1d:adjusted"))
    split = repository.get(MarketDataCacheKey("NVDA", "yfinance", start, None, VARIANT))
    assert plain is not None
    assert plain.split_history is None
    assert plain.data.context.price_adjustment == "adjusted"
    assert split is not None
    assert split.data.context.price_adjustment == "split_adjusted"
    assert split.split_history is not None
    assert split.split_history.adjustment_date == date(2026, 10, 26)

    # An ordinary entry under the split variant (a mistake of composition) is not read as a split history.
    key = MarketDataCacheKey("WMT", "yfinance", start, None, VARIANT)
    repository.put(key, dividend_adjusted)
    provider.history = _history("wmt")
    result = _client(provider, migrated_database).fetch_split_adjusted_history("WMT", START, use_cache=True)
    assert provider.calls == 2
    assert result.events == (SplitEvent(date(2024, 2, 26), 3.0),)


def test_a_stored_response_survives_reopening_the_database(migrated_database: SQLiteDatabase, tmp_path: Path) -> None:
    provider = _Provider(_history())
    _client(provider, migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)
    migrated_database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / DATABASE_FILE_NAME).as_posix()}"))
    try:
        again = _client(provider, reopened).fetch_split_adjusted_history("NVDA", START, use_cache=True)
        assert provider.calls == 1
        assert again.events == (SplitEvent(date(2024, 6, 10), 10.0),)
        assert again.close.index[0] == pd.Timestamp("2024-04-26")
    finally:
        reopened.close()


def test_an_expired_response_is_fetched_again(migrated_database: SQLiteDatabase) -> None:
    provider = _Provider(_history())
    ttl = timedelta(days=1)
    _client(provider, migrated_database, ttl=ttl).fetch_split_adjusted_history("NVDA", START, use_cache=True)
    _client(provider, migrated_database, ttl=ttl, clock=NOW + timedelta(hours=2)).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True
    )
    assert provider.calls == 1
    _client(provider, migrated_database, ttl=ttl, clock=NOW + timedelta(days=2)).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True
    )
    assert provider.calls == 2


def test_caching_off_or_no_variant_always_fetches_and_stores_nothing(migrated_database: SQLiteDatabase) -> None:
    provider = _Provider(_history())
    for client, use_cache in (
        (_client(provider, migrated_database), False),
        (_client(provider, migrated_database, variant=None), True),
        (_client(provider, migrated_database, variant=" "), True),
    ):
        result = client.fetch_split_adjusted_history("NVDA", START, use_cache=use_cache)
        assert result.resolution is not None
        assert result.resolution.source_kind is SourceKind.PROVIDER
    assert provider.calls == 3
    repository = SQLiteMarketDataRepository(migrated_database)
    assert repository.list_keys(limit=10) == ()


def test_a_provider_without_the_capability_is_a_defect_not_an_empty_answer(migrated_database: SQLiteDatabase) -> None:
    class Plain(BaseDataClient):
        def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:  # noqa: ARG002
            raise AssertionError(f"unused {self!r}")

        def fetch_current_price(self, ticker: str) -> float:  # noqa: ARG002
            raise AssertionError(f"unused {self!r}")

    assert not isinstance(Plain(), SplitAdjustedHistoryProvider)
    with pytest.raises(TypeError, match="no split-adjusted history"):
        _client(Plain(), migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)


def test_a_request_later_than_the_adjustment_date_is_refused_not_answered_with_an_older_session() -> None:
    history = _history()
    with pytest.raises(
        SplitHistoryEndsBeforeRequestError,
        match="ends at its adjustment date 2026-10-26, before the requested 2026-10-27",
    ):
        split_adjusted_close_on_or_before(history, date(2026, 10, 27))
    ended = replace(history, adjustment_date=date(2024, 6, 12))
    assert split_adjusted_close_on_or_before(ended, date(2024, 6, 12))[0] == date(2024, 6, 11)
    with pytest.raises(SplitHistoryEndsBeforeRequestError):
        split_adjusted_close_on_or_before(ended, date(2024, 6, 13))


def test_a_stored_response_is_reused_for_an_as_of_only_when_it_was_adjusted_on_or_after_it(
    migrated_database: SQLiteDatabase,
) -> None:
    provider = _Provider(_history())
    _client(provider, migrated_database).fetch_split_adjusted_history("NVDA", START, use_cache=True)
    assert provider.calls == 1

    covered = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, as_of=date(2026, 10, 26)
    )
    assert provider.calls == 1
    assert covered.resolution is not None
    assert covered.resolution.source_kind is SourceKind.CACHE
    earlier = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, as_of=date(2024, 4, 30)
    )
    assert provider.calls == 1
    assert earlier.resolution is not None
    assert earlier.resolution.source_kind is SourceKind.CACHE

    # The stored response was adjusted on 2026-10-26; a run at a later day does not reuse it and fetches again.
    provider.history = _history(adjustment_date=date(2026, 10, 28))
    later = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, as_of=date(2026, 10, 27)
    )
    assert provider.calls == 2
    assert later.resolution is not None
    assert later.resolution.source_kind is SourceKind.PROVIDER
    assert later.adjustment_date == date(2026, 10, 28)
    # The new response replaced the stored one, so the same request is now served from storage.
    again = _client(provider, migrated_database).fetch_split_adjusted_history(
        "NVDA", START, use_cache=True, as_of=date(2026, 10, 27)
    )
    assert provider.calls == 2
    assert again.adjustment_date == date(2026, 10, 28)
