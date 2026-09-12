"""Typed data-access / repository layer (market data, trajectories, metadata)."""

from src.data.repositories.market_data import (
    MarketDataCacheEntry,
    MarketDataCacheKey,
    SQLiteMarketDataRepository,
    UnsupportedHistoricalDataError,
)
from src.data.repositories.readiness import (
    DatabaseInspection,
    DatabaseReadinessError,
    DatabaseState,
    ReadinessOutcome,
    ReadinessReason,
    ensure_database_ready,
    inspect_database,
    upgrade_database,
)
from src.data.repositories.resolved_input_cache import SQLiteResolvedInputCache
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.trajectory import SQLiteTrajectoryRepository

__all__ = [
    "DatabaseInspection",
    "DatabaseState",
    "DatabaseReadinessError",
    "MarketDataCacheEntry",
    "MarketDataCacheKey",
    "ReadinessOutcome",
    "ReadinessReason",
    "SQLiteDatabase",
    "SQLiteMarketDataRepository",
    "SQLiteResolvedInputCache",
    "SQLiteTrajectoryRepository",
    "UnsupportedHistoricalDataError",
    "ensure_database_ready",
    "inspect_database",
    "upgrade_database",
]
