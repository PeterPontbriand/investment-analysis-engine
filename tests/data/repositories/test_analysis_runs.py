"""Verify Analysis Run insert/get/list/conflict/ordering/isolation/reopen through SQLite."""

import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from sqlalchemy import delete, select, update

from alembic import command
from src.config import ProjectSettings
from src.data.instrument_profile import InstrumentKind
from src.data.repositories.analysis_runs import AnalysisRunConflictError, SQLiteAnalysisRunRepository
from src.data.repositories.schema import (
    analysis_runs,
    market_data_cache_entries,
    resolved_input_cache,
    trajectory_events,
)
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import SQLiteWatchlistRepository
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.workspace.models import RunOutcome
from src.workspace.runs import AnalysisRun, RunQuery
from src.workspace.watchlists import WatchlistSpec
from tests.workspace.test_fcf_growth_codec import _run as _fcf_run
from tests.workspace.test_graham_growth_codec import _run as _graham_growth_run
from tests.workspace.test_graham_number_codec import _run as _graham_number_run
from tests.workspace.test_momentum_codec import _run as _momentum_run

MOMENTUM_ID = UUID("00000000-0000-4000-8000-000000000001")
GRAHAM_NUMBER_ID = UUID("00000000-0000-4000-8000-000000000002")
GRAHAM_GROWTH_ID = UUID("00000000-0000-4000-8000-000000000003")
FCF_ID = UUID("00000000-0000-4000-8000-000000000004")


def _four_runs() -> tuple[AnalysisRun, AnalysisRun, AnalysisRun, AnalysisRun]:
    """Four real, method-distinct runs sharing the codec fixtures' common STAMP."""
    return (
        _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID}),
        _graham_number_run().model_copy(update={"analysis_run_id": GRAHAM_NUMBER_ID}),
        _graham_growth_run().model_copy(update={"analysis_run_id": GRAHAM_GROWTH_ID}),
        _fcf_run().model_copy(update={"analysis_run_id": FCF_ID}),
    )


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'analysis_runs.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def repository(database: SQLiteDatabase) -> SQLiteAnalysisRunRepository:
    return SQLiteAnalysisRunRepository(database)


def test_four_typed_round_trips_after_reopen(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'reopen.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    runs = _four_runs()

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteAnalysisRunRepository(first_database)
        for run in runs:
            repository.insert(run)
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        reopened = SQLiteAnalysisRunRepository(second_database)
        for expected in runs:
            restored = reopened.get(expected.analysis_run_id)
            assert restored == expected
            assert restored is not expected
    finally:
        second_database.close()


def test_captured_instrument_profile_round_trips_after_reopen(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'reopen_profile.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    profile = fixture_instrument_profile("CNR.TO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID, "instrument_profile": profile})

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        SQLiteAnalysisRunRepository(first_database).insert(run)
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        restored = SQLiteAnalysisRunRepository(second_database).get(MOMENTUM_ID)
    finally:
        second_database.close()

    assert restored == run
    assert restored is not None
    assert restored.instrument_profile == profile


def test_insert_duplicate_id_is_a_conflict_and_leaves_storage_unchanged(
    database: SQLiteDatabase, repository: SQLiteAnalysisRunRepository
) -> None:
    run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID})
    repository.insert(run)
    with pytest.raises(AnalysisRunConflictError, match="already exists"):
        repository.insert(run)
    with database.read() as connection:
        rows = connection.execute(select(analysis_runs)).all()
        assert len(rows) == 1


def test_get_missing_id_returns_none(repository: SQLiteAnalysisRunRepository) -> None:
    assert repository.get(UUID("99999999-9999-4999-8999-999999999999")) is None


def test_get_detects_relational_column_disagreeing_with_a_valid_envelope(
    database: SQLiteDatabase, repository: SQLiteAnalysisRunRepository
) -> None:
    run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID})
    repository.insert(run)
    with database.transaction() as connection:
        connection.execute(
            update(analysis_runs).where(analysis_runs.c.analysis_run_id == str(MOMENTUM_ID)).values(ticker="OTHER")
        )
    with pytest.raises(ValueError, match="Malformed or inconsistent"):
        repository.get(MOMENTUM_ID)


def test_insert_rejects_a_naive_completion_timestamp(repository: SQLiteAnalysisRunRepository) -> None:
    run = _momentum_run().model_copy(
        update={"analysis_run_id": MOMENTUM_ID, "completed_at": datetime(2026, 9, 10, 12, 0, 0)}
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.insert(run)


def test_get_detects_corrupted_envelope_but_list_still_reports_it(
    database: SQLiteDatabase, repository: SQLiteAnalysisRunRepository
) -> None:
    run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID})
    repository.insert(run)
    with database.transaction() as connection:
        connection.execute(
            update(analysis_runs)
            .where(analysis_runs.c.analysis_run_id == str(MOMENTUM_ID))
            .values(envelope_json='{"ticker": "MISMATCHED"}')
        )
    with pytest.raises(ValueError, match="validation error"):
        repository.get(MOMENTUM_ID)
    summaries = repository.list(RunQuery())
    assert [summary.analysis_run_id for summary in summaries] == [MOMENTUM_ID]


def test_list_orders_by_completion_desc_then_id_desc_and_filters_combine_with_and(
    repository: SQLiteAnalysisRunRepository,
) -> None:
    earlier = datetime(2026, 9, 1, tzinfo=UTC)
    later = datetime(2026, 9, 10, 12, tzinfo=UTC)
    low_id = UUID("00000000-0000-4000-8000-000000000001")
    high_id = UUID("00000000-0000-4000-8000-000000000002")

    same_time_low = _momentum_run().model_copy(update={"analysis_run_id": low_id})
    same_time_high = _graham_number_run().model_copy(update={"analysis_run_id": high_id})
    earlier_run = _graham_growth_run().model_copy(
        update={"analysis_run_id": FCF_ID, "started_at": earlier, "completed_at": earlier}
    )
    for run in (same_time_low, same_time_high, earlier_run):
        repository.insert(run)

    all_summaries = repository.list(RunQuery())
    assert [s.analysis_run_id for s in all_summaries] == [high_id, low_id, FCF_ID]
    assert same_time_high.completed_at == same_time_low.completed_at == later

    by_ticker = repository.list(RunQuery(ticker="KO"))
    assert [s.analysis_run_id for s in by_ticker] == [high_id, FCF_ID]

    by_ticker_and_method = repository.list(RunQuery(ticker="KO", method_id="graham_number"))
    assert [s.analysis_run_id for s in by_ticker_and_method] == [high_id]

    by_outcome = repository.list(RunQuery(status=RunOutcome.COMPLETED))
    assert len(by_outcome) == 3

    assert repository.list(RunQuery(refresh_id=UUID("11111111-1111-4111-8111-111111111111"))) == ()


def test_list_limit_and_offset_page_a_read_snapshot(repository: SQLiteAnalysisRunRepository) -> None:
    for run in _four_runs():
        repository.insert(run)

    query = RunQuery()
    assert query.limit == 20
    assert query.offset == 0

    first_page = repository.list(RunQuery(limit=2))
    second_page = repository.list(RunQuery(limit=2, offset=2))
    assert len(first_page) == 2
    assert len(second_page) == 2
    assert {s.analysis_run_id for s in first_page} | {s.analysis_run_id for s in second_page} == {
        MOMENTUM_ID,
        GRAHAM_NUMBER_ID,
        GRAHAM_GROWTH_ID,
        FCF_ID,
    }
    assert repository.list(RunQuery(limit=1, offset=4)) == ()


def test_independent_cache_and_telemetry_deletion_cannot_erase_runs(
    database: SQLiteDatabase, repository: SQLiteAnalysisRunRepository
) -> None:
    run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID})
    repository.insert(run)
    watchlist_repository = SQLiteWatchlistRepository(database)
    watchlist_repository.create(WatchlistSpec(display_name="Unrelated Watchlist"))

    with database.transaction() as connection:
        connection.execute(delete(trajectory_events))
        connection.execute(delete(resolved_input_cache))
        connection.execute(delete(market_data_cache_entries))

    assert repository.get(MOMENTUM_ID) == run
    assert [s.analysis_run_id for s in repository.list(RunQuery())] == [MOMENTUM_ID]
    assert watchlist_repository.get("Unrelated Watchlist") is not None


def test_no_network_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Analysis Run repository must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    url = f"sqlite:///{(tmp_path / 'offline.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteAnalysisRunRepository(database)
        run = _momentum_run().model_copy(update={"analysis_run_id": MOMENTUM_ID})
        repository.insert(run)
        assert repository.get(MOMENTUM_ID) == run
        repository.list(RunQuery())
    finally:
        database.close()
