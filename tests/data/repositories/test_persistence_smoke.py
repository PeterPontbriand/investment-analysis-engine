"""Exercise the complete persistence lifecycle in one disposable offline database."""

import socket
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from pandas.testing import assert_frame_equal

from alembic import command
from src.config import ProjectSettings
from src.core.telemetry.models import TelemetryMode, TrajectoryEvent, TrajectoryEventType
from src.core.telemetry.sinks import SQLiteTrajectorySink, read_trajectory
from src.data.financial.cache import ResolvedInputCacheEntry, ResolvedInputCacheKey
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.repositories import (
    MarketDataCacheEntry,
    MarketDataCacheKey,
    SQLiteDatabase,
    SQLiteMarketDataRepository,
    SQLiteResolvedInputCache,
    SQLiteTrajectoryRepository,
)
from src.evaluation.fixtures.market_data import momentum_success_frame


def test_fresh_database_persistence_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrate, write all payload families, reopen, downgrade, and recreate offline."""

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Persistence smoke test must not access network or LLM endpoints")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    path = tmp_path / "smoke.sqlite3"
    settings = ProjectSettings(database_url=f"sqlite:///{path.as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    assert not path.exists()
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    now = datetime(2026, 9, 6, tzinfo=UTC)
    event = TrajectoryEvent(
        run_id=uuid4(),
        session_id=uuid4(),
        span_id=uuid4(),
        sequence=1,
        timestamp=now,
        event_type=TrajectoryEventType.TOOL_RESULT,
        component="smoke",
        mode=TelemetryMode.FULL,
        tool_name="synthetic_analysis",
        tool_result_summary={"value": 4.5},
    )
    fact = ResolvedInput(
        field_name="eps",
        value=4.5,
        source_kind=SourceKind.PROVIDER,
        resolved_at=now,
        provider_id="fixture",
        provider_field="annual_eps",
        basis="annual",
        units="USD/share",
        currency="USD",
        available_at=now,
        retrieved_at=now,
        notes=("synthetic",),
    )
    fact_key = ResolvedInputCacheKey(FinancialSubjectKind.SECURITY, "ACME", "eps", "annual", "fixture", None, 1)
    history = HistoricalMarketData(
        momentum_success_frame(),
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            currency="USD",
            observation_count=5,
            price_adjustment="adjusted",
            data_as_of=date(2026, 1, 6),
        ),
    )
    history_key = MarketDataCacheKey("ACME", "fixture", date(2026, 1, 1), None, "1d:adjusted")
    database = SQLiteDatabase(settings)
    try:
        sink = SQLiteTrajectorySink(database)
        sink.record(event)
        sink.close()
        SQLiteResolvedInputCache(database, clock=lambda: now).put(fact_key, fact)
        SQLiteMarketDataRepository(database, clock=lambda: now).put(history_key, history, fetch_completed_at=now)
        assert SQLiteTrajectoryRepository(database).read_trajectory(event.run_id) == [event]
        assert SQLiteResolvedInputCache(database).list_keys(limit=1) == (fact_key,)
        assert SQLiteMarketDataRepository(database).list_keys(limit=1) == (history_key,)
    finally:
        database.close()
    _assert_reopened(
        settings,
        event,
        ResolvedInputCacheEntry(fact_key, fact, now),
        MarketDataCacheEntry(history_key, history, now, now),
    )
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    _assert_empty(settings, event, fact_key, history_key)


def _assert_reopened(
    settings: ProjectSettings,
    event: TrajectoryEvent,
    expected_fact: ResolvedInputCacheEntry,
    expected_history: MarketDataCacheEntry,
) -> None:
    """Verify durable payloads and administrative inspection after reopening."""
    fact_key, fact, now = expected_fact.key, expected_fact.resolved_input, expected_fact.cached_at
    history_key, history = expected_history.key, expected_history.data
    reopened = SQLiteDatabase(settings)
    try:
        assert read_trajectory(reopened, event.run_id) == [event]
        stored_fact = SQLiteResolvedInputCache(reopened).get(fact_key)
        assert stored_fact is not None
        assert stored_fact.resolved_input == fact
        assert stored_fact.cached_at == now
        inspector = SQLiteResolvedInputCache(reopened, clock=lambda: now + timedelta(days=1), ttl=timedelta(seconds=1))
        assert inspector.get(fact_key) is None
        assert inspector.list_keys(limit=1) == (fact_key,)
        assert inspector.inspect(fact_key) == stored_fact
        assert inspector.list_keys(limit=1, offset=1) == ()
        # Administrative inspection does not change eligibility or stored age.
        assert inspector.get(fact_key) is None
        assert SQLiteResolvedInputCache(reopened).get(fact_key) == stored_fact
        assert SQLiteTrajectoryRepository(reopened).read_trajectory(event.run_id) == [event]
        assert SQLiteMarketDataRepository(reopened).list_keys(limit=1) == (history_key,)
        stored_history = SQLiteMarketDataRepository(reopened).get(history_key)
        assert stored_history is not None
        assert stored_history.data.context == history.context
        assert stored_history.fetch_completed_at == now
        assert stored_history.cached_at == now
        assert_frame_equal(stored_history.data.frame, history.frame, check_exact=True)
        with reopened.read() as connection:
            assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        reopened.close()


def _assert_empty(
    settings: ProjectSettings, event: TrajectoryEvent, fact_key: ResolvedInputCacheKey, history_key: MarketDataCacheKey
) -> None:
    """Confirm re-upgrade recreates empty stores after the destructive downgrade."""
    empty = SQLiteDatabase(settings)
    try:
        assert read_trajectory(empty, event.run_id) == []
        assert SQLiteResolvedInputCache(empty).get(fact_key) is None
        assert SQLiteMarketDataRepository(empty).get(history_key) is None
        assert SQLiteTrajectoryRepository(empty).read_trajectory(event.run_id) == []
        assert SQLiteResolvedInputCache(empty).inspect(fact_key) is None
        assert SQLiteResolvedInputCache(empty).list_keys(limit=1) == ()
        assert SQLiteMarketDataRepository(empty).list_keys(limit=1) == ()
    finally:
        empty.close()
