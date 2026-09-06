"""Atomic historical OHLCV snapshots with explicit frame representation."""

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy import BigInteger, Float, bindparam, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection

from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.repositories.schema import market_data_cache_entries, market_price_observations, schema_metadata
from src.data.repositories.sqlite import SQLiteDatabase

_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}
_CONTEXT_COLUMNS = {
    "provider_id": "context_provider_id",
    "observation_interval": "observation_interval",
    "data_as_of": "data_as_of",
    "currency": "currency",
    "observation_count": "observation_count",
    "price_adjustment": "price_adjustment",
}
_CONTEXT_ADAPTER = TypeAdapter(MarketDataContext)
_Name = str | int | float | bool | None


class UnsupportedHistoricalDataError(ValueError):
    """A frame cannot be represented by the supported historical storage shape."""


@dataclass(frozen=True)
class MarketDataCacheKey:
    """Exact request identity; overlapping requests retain separate snapshots.

    Bounds are calendar dates, with None retaining an open end. The caller
    supplies a stable provider and configuration variant; neither is inferred.
    """

    ticker: str
    request_provider_id: str
    request_start: date
    request_end: date | None
    request_variant: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        """Normalize identifiers and validate calendar bounds and version."""
        for name, value in (
            ("ticker", self.ticker.strip().upper()),
            ("request_provider_id", self.request_provider_id.strip().lower()),
            ("request_variant", self.request_variant.strip()),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty.")
            object.__setattr__(self, name, value)
        if type(self.request_start) is not date or (
            self.request_end is not None and type(self.request_end) is not date
        ):
            raise ValueError("Request bounds must be calendar dates.")
        if self.request_end is not None and self.request_end < self.request_start:
            raise ValueError("Request end must not precede start.")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("schema_version must be a positive integer.")


@dataclass(frozen=True)
class MarketDataCacheEntry:
    """One stored request snapshot and its original cache/retrieval timing."""

    key: MarketDataCacheKey
    data: HistoricalMarketData
    cached_at: datetime
    fetch_completed_at: datetime | None = None


_KEY_ADAPTER = TypeAdapter(MarketDataCacheKey)


class _FrameMetadata(BaseModel):
    """Versioned structural metadata; observation values stay relational."""

    model_config = ConfigDict(extra="forbid", strict=True)

    columns: list[str]
    dtypes: list[Literal["float64", "int64"]]
    columns_name: _Name
    index_kind: Literal["datetime", "date"]
    index_name: _Name
    index_dtype: str
    index_timezone: str | None
    index_frequency: str | None


def _json(value: object) -> str:
    """Encode canonical Unicode JSON without non-finite values."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _utc(value: datetime) -> str:
    """Encode a timezone-aware instant without guessing a missing timezone."""
    if value.utcoffset() is None:
        raise ValueError("Storage timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _key_row(key: MarketDataCacheKey) -> dict[str, Any]:
    """Encode all request identity fields, including the open-ended boundary."""
    row = asdict(key)
    row["request_start"] = key.request_start.isoformat()
    row["request_end"] = None if key.request_end is None else key.request_end.isoformat()
    row["entry_key"] = _json(list(row.values()))
    return row


def _name(value: object) -> _Name:
    """Accept losslessly representable scalar axis names."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise UnsupportedHistoricalDataError("Axis names must be finite JSON scalars or None.")


def _index_storage(index: pd.Index[Any]) -> tuple[dict[str, Any], list[str]]:
    """Encode ordered date/datetime indexes without changing their resolution."""
    if isinstance(index, pd.MultiIndex):
        raise UnsupportedHistoricalDataError("Historical index must be single-level.")
    if not index.is_unique or not index.is_monotonic_increasing or index.hasnans:
        raise UnsupportedHistoricalDataError("Historical index must be unique, ascending, and non-null.")
    if isinstance(index, pd.DatetimeIndex):
        index_kind = "datetime"
        ticks = [str(value) for value in index.view("int64")]
        zone = None if index.tz is None else str(index.tz)
        frequency = index.freqstr
    elif all(type(value) is date for value in index):
        index_kind = "date"
        ticks = [value.isoformat() for value in index]
        zone = None
        frequency = None
    else:
        raise UnsupportedHistoricalDataError("Historical index must contain datetimes or Python dates.")
    return {
        "index_kind": index_kind,
        "index_name": _name(index.name),
        "index_dtype": str(index.dtype),
        "index_timezone": zone,
        "index_frequency": frequency,
    }, ticks


def _frame_rows(frame: pd.DataFrame, entry_key: str) -> tuple[_FrameMetadata, list[dict[str, Any]]]:
    """Validate the approved frame shape and retain native numeric values."""
    if frame.empty or "Close" not in frame.columns:
        raise ValueError("Historical data must be nonempty and contain Close.")
    if isinstance(frame.columns, pd.MultiIndex) or not frame.columns.is_unique:
        raise UnsupportedHistoricalDataError("Historical columns must be unique and single-level.")
    if frame.attrs or any(column not in _COLUMNS for column in frame.columns):
        raise UnsupportedHistoricalDataError("Only OHLCV columns and empty frame attrs are supported.")
    dtypes = [str(dtype) for dtype in frame.dtypes]
    if any(dtype not in ("float64", "int64") for dtype in dtypes):
        raise UnsupportedHistoricalDataError("Only NumPy float64/int64 columns are supported.")
    index_metadata, ticks = _index_storage(frame.index)
    metadata = _FrameMetadata.model_validate(
        {
            "columns": list(frame.columns),
            "dtypes": dtypes,
            "columns_name": _name(frame.columns.name),
            **index_metadata,
        }
    )
    values: dict[str, list[Any]] = {}
    for column, dtype in zip(metadata.columns, metadata.dtypes, strict=True):
        if not np.isfinite(frame[column].to_numpy()).all():
            raise ValueError("Historical observations must be finite and non-null.")
        native = frame[column].tolist()
        if dtype == "int64" and column != "Volume" and any(int(float(value)) != value for value in native):
            raise UnsupportedHistoricalDataError("Integer prices must round-trip exactly through SQLite REAL.")
        values[column] = native
    rows: list[dict[str, Any]] = [dict.fromkeys(_COLUMNS.values()) for _ in ticks]
    for position, (row, tick) in enumerate(zip(rows, ticks, strict=True)):
        row.update(entry_key=entry_key, row_position=position, index_value=tick)
        row.update({_COLUMNS[column]: values[column][position] for column in metadata.columns})
    return metadata, rows


def _restore_index(metadata: _FrameMetadata, rows: list[dict[str, Any]]) -> pd.Index[Any]:
    """Restore local calendar dates or datetime ticks in their original unit."""
    index: pd.Index[Any]
    if metadata.index_kind == "date":
        index = pd.Index(
            [date.fromisoformat(row["index_value"]) for row in rows], dtype="object", name=metadata.index_name
        )
    else:
        if metadata.index_timezone is None:
            dtype = np.dtype(metadata.index_dtype)
            if dtype.kind != "M":
                raise ValueError("Malformed datetime index dtype.")
            unit = np.datetime_data(dtype)[0]
        else:
            timezone_dtype = pd.DatetimeTZDtype.construct_from_string(metadata.index_dtype)
            if not isinstance(timezone_dtype, pd.DatetimeTZDtype):
                raise ValueError("Malformed timezone-aware index dtype.")
            unit = timezone_dtype.unit
        if unit not in ("s", "ms", "us", "ns"):
            raise ValueError("Unsupported datetime index unit.")
        ticks = np.array([int(row["index_value"]) for row in rows], dtype="int64")
        datetimes = pd.DatetimeIndex(ticks.view(f"datetime64[{unit}]"))
        if metadata.index_timezone is not None:
            datetimes = datetimes.tz_localize(UTC).tz_convert(metadata.index_timezone)
        index = pd.DatetimeIndex(datetimes, name=metadata.index_name)
        if metadata.index_frequency is not None:
            index = pd.DatetimeIndex(datetimes, name=metadata.index_name, freq=metadata.index_frequency)
    return index


def _restore_frame(metadata: _FrameMetadata, rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Rebuild index and columns without inferring or coercing missing values."""
    if (
        not rows
        or len(metadata.columns) != len(metadata.dtypes)
        or len(set(metadata.columns)) != len(metadata.columns)
        or "Close" not in metadata.columns
        or any(column not in _COLUMNS for column in metadata.columns)
    ):
        raise ValueError("Malformed historical frame metadata.")
    if [row["row_position"] for row in rows] != list(range(len(rows))):
        raise ValueError("Historical row positions must be contiguous.")
    index = _restore_index(metadata, rows)
    columns: dict[str, Any] = {}
    for column, dtype_name in zip(metadata.columns, metadata.dtypes, strict=True):
        values = [row[_COLUMNS[column]] for row in rows]
        for value in values:
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Stored historical observations must be finite and non-null.")
            if dtype_name == "int64" and (int(value) != value or not -(2**63) <= int(value) < 2**63):
                raise ValueError("Stored observation cannot be represented as int64.")
        columns[column] = np.array(values, dtype=dtype_name)
    frame = pd.DataFrame(columns, index=index)
    frame.columns.name = metadata.columns_name
    return frame


def _parent(entry: MarketDataCacheEntry, metadata: _FrameMetadata) -> dict[str, Any]:
    """Encode snapshot and context metadata independently of observations."""
    row = _key_row(entry.key)
    context = _CONTEXT_ADAPTER.validate_python(asdict(entry.data.context))
    row.update({column: getattr(context, name) for name, column in _CONTEXT_COLUMNS.items()})
    row["data_as_of"] = None if context.data_as_of is None else context.data_as_of.isoformat()
    row.update(
        cached_at=_utc(entry.cached_at),
        fetch_completed_at=None if entry.fetch_completed_at is None else _utc(entry.fetch_completed_at),
        row_count=len(entry.data.frame),
        frame_metadata_json=_json(metadata.model_dump()),
    )
    return row


def _check_encoding(connection: Connection) -> None:
    """Require the supported migration-owned persistence encoding."""
    version = connection.execute(
        select(schema_metadata.c.metadata_value).where(schema_metadata.c.metadata_key == "persistence_encoding_version")
    ).scalar_one_or_none()
    if version != 1:
        raise ValueError("Unsupported or missing historical persistence encoding version.")


class SQLiteMarketDataRepository:
    """Persist exact historical request snapshots in a borrowed migrated database.

    No provider calls, TTL selection, or cross-request stitching occur here.
    The injected clock supplies cache timing; imported data has no invented
    fetch completion timestamp. Unsupported frames raise explicitly.
    """

    def __init__(self, database: SQLiteDatabase, *, clock: Callable[[], datetime] | None = None) -> None:
        """Retain a caller-owned database without opening it or migrating."""
        self._database = database
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def put(
        self, key: MarketDataCacheKey, data: HistoricalMarketData, *, fetch_completed_at: datetime | None = None
    ) -> None:
        """Validate then atomically replace one parent and all observation rows."""
        key = _KEY_ADAPTER.validate_python(asdict(key))
        metadata, rows = _frame_rows(data.frame, _key_row(key)["entry_key"])
        # Prove structural reconstruction before publication, including timezone
        # identifiers that pandas may not support as portable text.
        restored_metadata, restored_rows = _frame_rows(_restore_frame(metadata, rows), rows[0]["entry_key"])
        if restored_metadata != metadata or restored_rows != rows:
            raise UnsupportedHistoricalDataError("Historical frame does not round-trip through the supported encoding.")
        entry = MarketDataCacheEntry(key, data, self._clock(), fetch_completed_at)
        parent = _parent(entry, metadata)
        statement = insert(market_data_cache_entries).values(**parent)
        volume_type = (
            BigInteger() if "Volume" in metadata.columns and str(data.frame["Volume"].dtype) == "int64" else Float()
        )
        with self._database.transaction() as connection:
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=["entry_key"],
                    set_={name: statement.excluded[name] for name in parent if name != "entry_key"},
                )
            )
            _check_encoding(connection)
            connection.execute(
                delete(market_price_observations).where(market_price_observations.c.entry_key == parent["entry_key"])
            )
            connection.execute(
                market_price_observations.insert().values(volume=bindparam("volume", type_=volume_type)), rows
            )

    def get(self, key: MarketDataCacheKey) -> MarketDataCacheEntry | None:
        """Return a fully validated snapshot or None for an exact-key miss."""
        key = _KEY_ADAPTER.validate_python(asdict(key))
        with self._database.read() as connection:
            _check_encoding(connection)
            parent = (
                connection.execute(
                    select(market_data_cache_entries).where(
                        market_data_cache_entries.c.entry_key == _key_row(key)["entry_key"]
                    )
                )
                .mappings()
                .one_or_none()
            )
            if parent is None:
                return None
            rows = [
                dict(row)
                for row in connection.execute(
                    select(market_price_observations)
                    .where(market_price_observations.c.entry_key == parent["entry_key"])
                    .order_by(market_price_observations.c.row_position)
                ).mappings()
            ]
        return self._decode(dict(parent), rows)

    @staticmethod
    def _decode(parent: Mapping[str, Any], rows: list[dict[str, Any]]) -> MarketDataCacheEntry:
        """Validate complete storage representation before returning domain data."""
        if len(rows) != parent["row_count"]:
            raise ValueError("Historical snapshot row count does not match its observations.")
        key = _KEY_ADAPTER.validate_python({name: parent[name] for name in MarketDataCacheKey.__dataclass_fields__})
        metadata = _FrameMetadata.model_validate_json(parent["frame_metadata_json"])
        frame = _restore_frame(metadata, rows)
        context = _CONTEXT_ADAPTER.validate_python({name: parent[column] for name, column in _CONTEXT_COLUMNS.items()})
        entry = MarketDataCacheEntry(
            key,
            HistoricalMarketData(frame, context),
            datetime.fromisoformat(parent["cached_at"]),
            None if parent["fetch_completed_at"] is None else datetime.fromisoformat(parent["fetch_completed_at"]),
        )
        actual_metadata, actual_rows = _frame_rows(frame, parent["entry_key"])
        if _parent(entry, actual_metadata) != dict(parent) or actual_rows != rows:
            raise ValueError("Malformed or inconsistent historical snapshot encoding.")
        return entry
