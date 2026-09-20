"""Verify watchlist create/entry-edit/idempotence/conflict/order/reopen through SQLite."""

import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from sqlalchemy import select

from alembic import command
from src.config import ProjectSettings
from src.data.repositories.schema import watchlist_entries, watchlists
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import (
    SQLiteWatchlistRepository,
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
    WatchlistNotFoundError,
)
from src.workspace.requests import GrahamGrowthSelection, GrahamNumberSelection
from src.workspace.watchlists import WatchlistSpec

NOW = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 18, 12, 5, 0, tzinfo=UTC)
FIRST_ID = UUID("11111111-1111-4111-8111-111111111111")
SECOND_ID = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'watchlists.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def repository(database: SQLiteDatabase) -> SQLiteWatchlistRepository:
    ids = iter([FIRST_ID, SECOND_ID])
    return SQLiteWatchlistRepository(database, clock=lambda: NOW, id_factory=lambda: next(ids))


def test_create_materializes_no_entries(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="  Dividend Growth  "))
    assert watchlist.watchlist_id == FIRST_ID
    assert watchlist.display_name == "Dividend Growth"
    assert watchlist.normalized_name == "dividend growth"
    assert watchlist.created_at == NOW
    assert watchlist.updated_at is None
    assert watchlist.entries == ()


def test_create_rejects_blank_display_name(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(ValueError, match="blank"):
        repository.create(WatchlistSpec(display_name="   "))


def test_touch_rejects_a_naive_clock(database: SQLiteDatabase) -> None:
    aware_repository = SQLiteWatchlistRepository(database, clock=lambda: NOW, id_factory=lambda: FIRST_ID)
    watchlist = aware_repository.create(WatchlistSpec(display_name="Watch"))
    naive_clock = lambda: datetime(2026, 9, 18, 12, 5, 0)  # noqa: E731
    naive_repository = SQLiteWatchlistRepository(database, clock=naive_clock)
    with pytest.raises(ValueError, match="timezone-aware"):
        naive_repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])


def test_create_duplicate_name_is_a_conflict_and_leaves_storage_unchanged(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Dividend Growth"))
    repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    with pytest.raises(WatchlistConflictError, match="already exists"):
        repository.create(WatchlistSpec(display_name="  dividend growth  "))
    with database.read() as connection:
        rows = connection.execute(select(watchlists)).all()
        assert len(rows) == 1
        entry_rows = connection.execute(select(watchlist_entries)).all()
        assert len(entry_rows) == 1


def test_get_is_case_and_whitespace_insensitive(repository: SQLiteWatchlistRepository) -> None:
    repository.create(WatchlistSpec(display_name="Dividend Growth"))
    assert repository.get("  DIVIDEND growth ") is not None
    assert repository.get("nonexistent") is None


def test_list_orders_by_creation_and_reports_entry_count(repository: SQLiteWatchlistRepository) -> None:
    repository.create(WatchlistSpec(display_name="Second"))
    first = repository.create(WatchlistSpec(display_name="First"))
    repository.add_entries(first.display_name, [("KO", GrahamNumberSelection()), ("PFE", GrahamNumberSelection())])
    summaries = repository.list()
    assert [summary.display_name for summary in summaries] == ["Second", "First"]
    assert summaries[1].entry_count == 2


def test_add_entries_preserves_order_and_appends_after_current_max(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    momentum = GrahamNumberSelection()
    updated = repository.add_entries(watchlist.display_name, [(" ko ", momentum), ("pfe", momentum)])
    assert [(entry.ticker, entry.selection.method_id) for entry in updated.entries] == [
        ("KO", "graham_number"),
        ("PFE", "graham_number"),
    ]
    again = repository.add_entries(updated.display_name, [("AAPL", momentum)])
    assert [entry.ticker for entry in again.entries] == ["KO", "PFE", "AAPL"]


def test_add_entries_allows_the_same_method_twice_for_one_ticker_with_different_config(
    repository: SQLiteWatchlistRepository,
) -> None:
    """Amendment A1: comparing two configurations of the same method is now supported."""
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    via_sec = GrahamNumberSelection(security_provider_id="sec_edgar")
    via_massive = GrahamNumberSelection(security_provider_id="massive", bvps_override=12.5)
    updated = repository.add_entries(watchlist.display_name, [("AAPL", via_sec), ("AAPL", via_massive)])
    assert len(updated.entries) == 2
    assert all(entry.ticker == "AAPL" for entry in updated.entries)
    assert all(entry.selection.method_id == "graham_number" for entry in updated.entries)
    providers = set[str]()
    for entry in updated.entries:
        assert isinstance(entry.selection, GrahamNumberSelection)
        providers.add(entry.selection.security_provider_id)
    assert providers == {"sec_edgar", "massive"}


def test_add_entries_validates_before_writing_anything(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    with pytest.raises(ValueError, match="must not be empty"):
        repository.add_entries(
            watchlist.display_name, [("KO", GrahamNumberSelection()), ("   ", GrahamNumberSelection())]
        )
    with database.read() as connection:
        assert connection.execute(select(watchlist_entries)).all() == []


def test_add_entries_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.add_entries("nonexistent", [("KO", GrahamNumberSelection())])


def test_add_entries_with_empty_sequence_is_a_no_op(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    unchanged = repository.add_entries(watchlist.display_name, [])
    assert unchanged.entries == ()
    assert unchanged.updated_at is None


def test_remove_entry_removes_by_position_and_renumbers_survivors(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    selection = GrahamNumberSelection()
    watchlist = repository.add_entries(
        watchlist.display_name, [("KO", selection), ("PFE", selection), ("AAPL", selection)]
    )
    updated = repository.remove_entry(watchlist.display_name, 1)
    assert [entry.ticker for entry in updated.entries] == ["KO", "AAPL"]
    # The survivor that used to be at position 2 is now at position 1 (renumbered, no gap).
    with_ko_removed = repository.remove_entry(updated.display_name, 0)
    assert [entry.ticker for entry in with_ko_removed.entries] == ["AAPL"]
    emptied = repository.remove_entry(with_ko_removed.display_name, 0)
    assert emptied.entries == ()


def test_remove_entry_out_of_range_raises_and_leaves_storage_unchanged(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    with pytest.raises(WatchlistEntryNotFoundError):
        repository.remove_entry(watchlist.display_name, 5)
    with database.read() as connection:
        assert len(connection.execute(select(watchlist_entries)).all()) == 1


def test_remove_entry_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.remove_entry("nonexistent", 0)


def test_remove_entries_for_ticker_is_idempotent_for_absent_tickers(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    selection = GrahamNumberSelection()
    watchlist = repository.add_entries(
        watchlist.display_name, [("KO", selection), ("PFE", selection), ("AAPL", selection)]
    )
    updated = repository.remove_entries_for_ticker(watchlist.display_name, ["PFE", "NOTHERE"])
    assert [entry.ticker for entry in updated.entries] == ["KO", "AAPL"]
    again = repository.remove_entries_for_ticker(updated.display_name, ["PFE"])
    assert [entry.ticker for entry in again.entries] == ["KO", "AAPL"]


def test_remove_entries_for_ticker_removes_every_entry_for_that_ticker(
    repository: SQLiteWatchlistRepository,
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(
        watchlist.display_name,
        [
            ("AAPL", GrahamNumberSelection(security_provider_id="sec_edgar")),
            ("AAPL", GrahamNumberSelection(security_provider_id="massive", bvps_override=1.0)),
            ("KO", GrahamNumberSelection()),
        ],
    )
    updated = repository.remove_entries_for_ticker(watchlist.display_name, ["AAPL"])
    assert [entry.ticker for entry in updated.entries] == ["KO"]


def test_remove_entries_for_ticker_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.remove_entries_for_ticker("nonexistent", ["KO"])


def test_remove_entries_for_ticker_with_empty_sequence_is_a_no_op(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    unchanged = repository.remove_entries_for_ticker(watchlist.display_name, [])
    assert [entry.ticker for entry in unchanged.entries] == ["KO"]


def test_remove_entries_for_method_is_idempotent_for_absent_method(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(
        watchlist.display_name,
        [
            ("KO", GrahamNumberSelection()),
            ("KO", GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5)),
        ],
    )
    unchanged = repository.remove_entries_for_method(watchlist.display_name, "sma_crossover")
    assert [entry.selection.method_id for entry in unchanged.entries] == ["graham_number", "graham_growth_value"]
    reduced = repository.remove_entries_for_method(unchanged.display_name, "graham_number")
    assert [entry.selection.method_id for entry in reduced.entries] == ["graham_growth_value"]
    again = repository.remove_entries_for_method(reduced.display_name, "graham_number")
    assert [entry.selection.method_id for entry in again.entries] == ["graham_growth_value"]


def test_remove_entries_for_method_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.remove_entries_for_method("nonexistent", "graham_number")


def test_mutations_bump_updated_at_only_when_something_changes(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    assert watchlist.updated_at is None
    clocked = SQLiteWatchlistRepository(database, clock=lambda: LATER, id_factory=lambda: SECOND_ID)
    unchanged = clocked.remove_entries_for_ticker(watchlist.display_name, ["NOTHERE"])
    assert unchanged.updated_at is None
    changed = clocked.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    assert changed.updated_at == LATER


def test_reopen_preserves_full_watchlist_state(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'reopen.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteWatchlistRepository(first_database, clock=lambda: NOW, id_factory=lambda: FIRST_ID)
        created = repository.create(WatchlistSpec(display_name="Persisted"))
        repository.add_entries(
            created.display_name,
            [("KO", GrahamNumberSelection()), ("PFE", GrahamNumberSelection(bvps_override=9.0))],
        )
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        reopened = SQLiteWatchlistRepository(second_database).get("persisted")
        assert reopened is not None
        assert reopened.watchlist_id == FIRST_ID
        assert [entry.ticker for entry in reopened.entries] == ["KO", "PFE"]
        pfe_selection = reopened.entries[1].selection
        assert isinstance(pfe_selection, GrahamNumberSelection)
        assert pfe_selection.bvps_override == 9.0
    finally:
        second_database.close()


def test_no_network_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Watchlist repository must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    url = f"sqlite:///{(tmp_path / 'offline.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteWatchlistRepository(database, clock=lambda: NOW, id_factory=lambda: FIRST_ID)
        watchlist = repository.create(WatchlistSpec(display_name="Offline"))
        repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
        repository.list()
        assert repository.get("offline") is not None
    finally:
        database.close()
