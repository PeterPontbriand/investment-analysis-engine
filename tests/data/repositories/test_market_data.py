"""Verify exact historical-frame snapshots through migrated SQLite storage."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pytest
from alembic.config import Config
from pandas.testing import assert_frame_equal
from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, OperationalError

from alembic import command
from src.config import ProjectSettings
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.repositories import (
    MarketDataCacheKey,
    SQLiteDatabase,
    SQLiteMarketDataRepository,
    UnsupportedHistoricalDataError,
)
from src.data.repositories.schema import market_data_cache_entries, market_price_observations, schema_metadata

NOW = datetime(2026, 9, 5, 12, 0, 0, 123456, tzinfo=UTC)


def test_list_keys_pages_preserve_full_identity(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData
) -> None:
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    assert repository.list_keys(limit=2) == ()
    keys = (
        replace(key, ticker="AAA", request_end=date(2025, 3, 10)),
        replace(key, ticker="AAA", request_variant="1wk", schema_version=2),
        replace(key, ticker="ZZZ", request_provider_id="other"),
    )
    for item in reversed(keys):
        repository.put(item, data)
    # Canonical ordering puts the quoted bounded date before JSON null.
    assert repository.list_keys(limit=2) == keys[:2]
    assert repository.list_keys(limit=2, offset=2) == keys[2:]
    assert repository.list_keys(limit=2, offset=3) == ()
    assert repository.list_keys(limit=1, offset=1) == keys[1:2]
    for item in keys:
        stored = repository.get(item)
        assert stored is not None
        assert stored.cached_at == NOW
        assert_frame_equal(stored.data.frame, data.frame)


@pytest.mark.parametrize(
    ("limit", "offset"), [(0, 0), (-1, 0), (True, 0), (1.5, 0), (None, 0), (1, -1), (1, False), (1, 0.5)]
)
def test_list_keys_rejects_invalid_bounds_before_io(tmp_path: Path, limit: Any, offset: Any) -> None:
    path = tmp_path / "not-created.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with pytest.raises(ValueError, match="limit|offset"):
            SQLiteMarketDataRepository(database).list_keys(limit=limit, offset=offset)
        assert not path.exists()
    finally:
        database.close()


@pytest.mark.parametrize("version", [None, 2])
def test_list_keys_requires_encoding(database: SQLiteDatabase, version: int | None) -> None:
    with database.transaction() as connection:
        if version is None:
            connection.execute(delete(schema_metadata))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=version))
    with pytest.raises(ValueError, match="encoding version"):
        SQLiteMarketDataRepository(database).list_keys(limit=1)


@pytest.mark.parametrize(("column", "value"), [("ticker", "other"), ("request_start", "not-a-date")])
def test_list_keys_rejects_malformed_selected_keys(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, column: str, value: str
) -> None:
    repository = SQLiteMarketDataRepository(database)
    repository.put(key, data)
    with database.transaction() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints = ON")
        connection.execute(update(market_data_cache_entries).values(**{column: value}))
    with pytest.raises(ValueError, match="Malformed|validation error"):
        repository.list_keys(limit=1)


def test_list_keys_does_not_decode_or_modify_frame_payload(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData
) -> None:
    repository = SQLiteMarketDataRepository(database)
    repository.put(key, data)
    with database.transaction() as connection:
        connection.execute(update(market_data_cache_entries).values(frame_metadata_json="{}"))
    with database.read() as connection:
        before = connection.execute(select(market_data_cache_entries)).all()
    assert repository.list_keys(limit=1) == (key,)
    with pytest.raises(ValueError, match="Malformed|validation error"):
        repository.get(key)
    with database.read() as connection:
        assert connection.execute(select(market_data_cache_entries)).all() == before


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'market.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def key() -> MarketDataCacheKey:
    return MarketDataCacheKey(" brk.b ", " Fixture ", date(2025, 3, 1), None, "1d:adjusted")


@pytest.fixture
def data() -> HistoricalMarketData:
    index = pd.date_range("2025-03-08T01:00:00.000000123", periods=3, freq="D", tz="America/New_York", name="Date")
    frame = pd.DataFrame(
        {
            "Volume": np.array([-(2**63), 2**60 + 1, 2**63 - 1], dtype="int64"),
            "Close": np.array([101.25, 102.5, 103.75], dtype="float64"),
            "Open": np.array([100, 101, 102], dtype="int64"),
            "Adj Close": np.array([99.5, 100.5, 102.5], dtype="float64"),
            "Low": np.array([99.0, 100.0, 101.0], dtype="float64"),
            "High": np.array([102.0, 103.0, 104.0], dtype="float64"),
        },
        index=index,
    )
    frame.columns.name = "Price"
    return HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="Fixture",
            observation_interval="1d",
            data_as_of=date(2025, 3, 10),
            currency="usd",
            observation_count=3,
            price_adjustment="adjusted",
        ),
    )


def test_complete_frame_reopens_with_exact_volume(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, tmp_path: Path
) -> None:
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    assert repository.get(key) is None
    original = data.frame.copy(deep=True)
    fetched = NOW - timedelta(seconds=2)
    repository.put(key, data, fetch_completed_at=fetched)
    assert_frame_equal(data.frame, original)
    with database.read() as connection:
        values = (
            connection.execute(
                select(market_price_observations.c.volume).order_by(market_price_observations.c.row_position)
            )
            .scalars()
            .all()
        )
    assert values == [-(2**63), 2**60 + 1, 2**63 - 1]
    assert all(type(value) is int for value in values)
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'market.sqlite3').as_posix()}"))
    try:
        result = SQLiteMarketDataRepository(reopened).get(key)
        assert result is not None
        assert result.key == key
        assert result.cached_at == NOW
        assert result.fetch_completed_at == fetched
        assert result.data.context == data.context
        assert_frame_equal(result.data.frame, original, check_exact=True)
    finally:
        reopened.close()


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "America/New_York", timezone(timedelta(hours=5, minutes=30))])
def test_datetime_units_and_timezones(
    database: SQLiteDatabase, key: MarketDataCacheKey, unit: Literal["s", "ms", "us", "ns"], zone: Any
) -> None:
    index = pd.date_range("2025-03-08", periods=3, freq="D", tz=zone, name="observed").as_unit(unit)
    frame = pd.DataFrame({"Close": [1.25, 2.5, 3.75]}, index=index)
    payload = HistoricalMarketData(frame, MarketDataContext())
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    repository.put(key, payload)
    result = repository.get(key)
    assert result is not None
    assert result.fetch_completed_at is None
    assert result.data.context == MarketDataContext()
    assert_frame_equal(result.data.frame, frame, check_exact=True)


def test_python_dates_and_optional_columns(database: SQLiteDatabase, key: MarketDataCacheKey) -> None:
    frame = pd.DataFrame(
        {"Close": np.array([2**60, 2**60 + 256], dtype="int64")},
        index=pd.Index([date(2025, 3, 8), date(2025, 3, 10)], name="calendar_date"),
    )
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    repository.put(key, HistoricalMarketData(frame, MarketDataContext()))
    result = repository.get(key)
    assert result is not None
    assert_frame_equal(result.data.frame, frame, check_exact=True)
    with database.read() as connection:
        assert connection.execute(select(market_price_observations.c.volume)).scalars().all() == [None, None]


def test_irregular_index_and_float_volume(database: SQLiteDatabase, key: MarketDataCacheKey) -> None:
    frame = pd.DataFrame(
        {"Volume": [0.0, 2.25], "Close": [1.5, 2.5]}, index=pd.DatetimeIndex(["2025-03-08", "2025-03-10"])
    )
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    repository.put(key, HistoricalMarketData(frame, MarketDataContext()))
    result = repository.get(key)
    assert result is not None
    assert_frame_equal(result.data.frame, frame, check_exact=True)


def test_replacement_and_overlapping_requests_are_isolated(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData
) -> None:
    now = NOW
    repository = SQLiteMarketDataRepository(database, clock=lambda: now)
    overlap = replace(key, request_start=date(2025, 3, 5), request_end=date(2025, 3, 12))
    repository.put(key, data, fetch_completed_at=NOW)
    repository.put(overlap, data, fetch_completed_at=NOW)
    now += timedelta(seconds=1)
    repository.put(key, data)
    repeated = repository.get(key)
    assert repeated is not None
    assert repeated.cached_at == now
    assert repeated.fetch_completed_at is None
    smaller = HistoricalMarketData(data.frame[["Close"]].iloc[:1], MarketDataContext())
    repository.put(key, smaller)
    replaced = repository.get(key)
    untouched = repository.get(overlap)
    assert replaced is not None
    assert untouched is not None
    assert_frame_equal(replaced.data.frame, smaller.frame)
    assert replaced.data.context == MarketDataContext()
    assert_frame_equal(untouched.data.frame, data.frame)
    assert untouched.cached_at == NOW
    assert untouched.fetch_completed_at == NOW
    with database.read() as connection:
        assert len(connection.execute(select(market_price_observations)).all()) == 4


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ticker", "OTHER"),
        ("request_provider_id", "other"),
        ("request_start", date(2025, 3, 2)),
        ("request_end", date(2025, 3, 12)),
        ("request_variant", "1d:unadjusted"),
        ("schema_version", 2),
    ],
)
def test_complete_request_identity(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, field: str, value: Any
) -> None:
    repository = SQLiteMarketDataRepository(database)
    repository.put(key, data)
    assert repository.get(replace(key, **{field: value})) is None
    assert repository.get(replace(key, ticker=" brk.b ", request_provider_id=" FIXTURE ")) is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ticker", " "),
        ("request_provider_id", ""),
        ("request_variant", " "),
        ("request_start", NOW),
        ("request_end", date(2025, 1, 1)),
        ("schema_version", 0),
    ],
)
def test_invalid_request_identity(key: MarketDataCacheKey, field: str, value: Any) -> None:
    with pytest.raises(ValueError, match="non-empty|calendar dates|precede|positive"):
        replace(key, **{field: value})


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_replacement_leaves_prior_snapshot(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, bad_value: float
) -> None:
    repository = SQLiteMarketDataRepository(database)
    repository.put(key, data)
    frame = data.frame.copy()
    frame.loc[frame.index[0], "Close"] = bad_value
    with pytest.raises(ValueError, match="finite"):
        repository.put(key, HistoricalMarketData(frame, data.context))
    result = repository.get(key)
    assert result is not None
    assert_frame_equal(result.data.frame, data.frame)


@pytest.mark.parametrize(
    "kind", ["attrs", "extra", "float32", "descending", "duplicate", "multiindex", "names", "lossy_price"]
)
def test_unsupported_frames_rejected(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, kind: str
) -> None:
    frame = data.frame.copy()
    if kind == "attrs":
        frame.attrs["provider_note"] = "retained outside this shape"
    elif kind == "extra":
        frame["Dividends"] = 0.0
    elif kind == "float32":
        frame["Close"] = frame["Close"].astype("float32")
    elif kind == "descending":
        frame = frame.iloc[::-1]
    elif kind == "duplicate":
        frame.index = pd.DatetimeIndex([frame.index[0]] * len(frame))
    elif kind == "multiindex":
        frame.index = pd.MultiIndex.from_product([["ACME"], [1, 2, 3]])
    elif kind == "names":
        frame.index.name = ("tuple", "name")
    else:
        frame["Close"] = np.array([2**60 + 1, 2, 3], dtype="int64")
    repository = SQLiteMarketDataRepository(database)
    with pytest.raises(UnsupportedHistoricalDataError):
        repository.put(key, HistoricalMarketData(frame, data.context))
    assert repository.get(key) is None


@pytest.mark.parametrize("empty", [False, True])
def test_missing_close_or_empty_is_invalid(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, empty: bool
) -> None:
    frame = data.frame.iloc[:0] if empty else data.frame.drop(columns="Close")
    with pytest.raises(ValueError, match="nonempty.*Close"):
        SQLiteMarketDataRepository(database).put(key, HistoricalMarketData(frame, data.context))


def test_failed_child_write_rolls_back_full_snapshot(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData
) -> None:
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    repository.put(key, data)
    with database.transaction() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_child BEFORE INSERT ON market_price_observations "
            "WHEN NEW.row_position = 1 BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    changed = data.frame.copy()
    changed["Close"] += 10
    with pytest.raises(IntegrityError, match="synthetic failure"):
        repository.put(key, HistoricalMarketData(changed, MarketDataContext()))
    result = repository.get(key)
    assert result is not None
    assert result.data.context == data.context
    assert_frame_equal(result.data.frame, data.frame)


@pytest.mark.parametrize("kind", ["count", "child", "metadata", "numeric", "position", "absent_column", "version"])
def test_corrupt_snapshots_raise(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, kind: str
) -> None:
    repository = SQLiteMarketDataRepository(database)
    payload = HistoricalMarketData(data.frame[["Close"]], data.context)
    repository.put(key, payload)
    with database.transaction() as connection:
        if kind == "count":
            connection.execute(update(market_data_cache_entries).values(row_count=8))
        elif kind == "child":
            connection.execute(delete(market_price_observations).where(market_price_observations.c.row_position == 1))
        elif kind == "metadata":
            connection.execute(update(market_data_cache_entries).values(frame_metadata_json="{}"))
        elif kind == "numeric":
            connection.execute(update(market_price_observations).values(close=float("inf")))
        elif kind == "position":
            connection.execute(
                update(market_price_observations)
                .where(market_price_observations.c.row_position == 2)
                .values(row_position=9)
            )
        elif kind == "absent_column":
            connection.execute(update(market_price_observations).values(open=9))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=2))
    with pytest.raises(ValueError, match="row count|validation errors|finite|contiguous|inconsistent|encoding version"):
        repository.get(key)


def test_timing_and_unknown_encoding_validation(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SQLiteMarketDataRepository(database, clock=lambda: NOW.replace(tzinfo=None)).put(key, data)
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.put(key, data, fetch_completed_at=NOW.replace(tzinfo=None))
    with database.transaction() as connection:
        connection.execute(update(schema_metadata).values(metadata_value=2))
    with pytest.raises(ValueError, match="encoding version"):
        repository.put(key, data)
    with database.read() as connection:
        assert connection.execute(select(market_data_cache_entries)).all() == []


def test_lazy_unmigrated_database(tmp_path: Path, key: MarketDataCacheKey, data: HistoricalMarketData) -> None:
    path = tmp_path / "unmigrated.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    repository = SQLiteMarketDataRepository(database)
    assert not path.exists()
    try:
        with pytest.raises(OperationalError):
            repository.put(key, data)
    finally:
        database.close()


def test_parent_and_children_share_one_snapshot(
    database: SQLiteDatabase, key: MarketDataCacheKey, data: HistoricalMarketData, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SQLiteMarketDataRepository(database, clock=lambda: NOW)
    repository.put(key, data)
    replacement = HistoricalMarketData(data.frame[["Close"]].iloc[:1], MarketDataContext())
    original_read = database.read
    switched = False

    @contextmanager
    def read_with_concurrent_commit() -> Iterator[Connection]:
        nonlocal switched
        with original_read() as connection:
            original_execute = connection.execute

            def execute(statement: Any, *args: Any, **kwargs: Any) -> Any:
                nonlocal switched
                result = original_execute(statement, *args, **kwargs)
                if not switched and "market_data_cache_entries" in str(statement):
                    switched = True
                    repository.put(key, replacement)
                return result

            monkeypatch.setattr(connection, "execute", execute)
            yield connection

    monkeypatch.setattr(database, "read", read_with_concurrent_commit)
    old = repository.get(key)
    assert switched
    assert old is not None
    assert old.data.context == data.context
    assert_frame_equal(old.data.frame, data.frame)
    current = repository.get(key)
    assert current is not None
    assert_frame_equal(current.data.frame, replacement.frame)
