"""Verify watchlist create/entry-edit/idempotence/conflict/order/reopen through SQLite."""

import json
import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from src.config import ProjectSettings
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.schema import analysis_runs, watchlist_entries, watchlists
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import (
    DeletedWatchlist,
    SQLiteWatchlistRepository,
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.momentum.execution import run_momentum
from src.strategies.momentum.selection import MomentumSelection
from src.strategy_wiring import RUN_SPECS_BY_KEY
from src.workspace.capture import ExecutionCapture
from src.workspace.models import RunOutcome
from src.workspace.refresh import refresh_watchlist
from src.workspace.runs import Watchlist
from src.workspace.strategy_types import AnalysisSelection
from src.workspace.watchlists import StoredSelectionError, WatchlistNotFoundError, WatchlistSpec
from tests._wiring import alias_for, failure_code

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
    return SQLiteWatchlistRepository(database, clock=lambda: NOW, id_factory=lambda: next(ids), alias_for=alias_for)


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
    aware_repository = SQLiteWatchlistRepository(
        database, clock=lambda: NOW, id_factory=lambda: FIRST_ID, alias_for=alias_for
    )
    watchlist = aware_repository.create(WatchlistSpec(display_name="Watch"))
    naive_clock = lambda: datetime(2026, 9, 18, 12, 5, 0)  # noqa: E731
    naive_repository = SQLiteWatchlistRepository(database, clock=naive_clock, alias_for=alias_for)
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


def _read(repository: SQLiteWatchlistRepository, name: str) -> Watchlist:
    """Read a watchlist back after a removal, which returns nothing."""
    watchlist = repository.get(name)
    assert watchlist is not None
    return watchlist


def test_remove_entry_removes_by_position_and_renumbers_survivors(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    selection = GrahamNumberSelection()
    watchlist = repository.add_entries(
        watchlist.display_name, [("KO", selection), ("PFE", selection), ("AAPL", selection)]
    )
    assert repository.remove_entry(watchlist.display_name, 1) == 1
    updated = _read(repository, watchlist.display_name)
    assert [entry.ticker for entry in updated.entries] == ["KO", "AAPL"]
    # The survivor that used to be at position 2 is now at position 1 (renumbered, no gap).
    repository.remove_entry(updated.display_name, 0)
    with_ko_removed = _read(repository, updated.display_name)
    assert [entry.ticker for entry in with_ko_removed.entries] == ["AAPL"]
    repository.remove_entry(with_ko_removed.display_name, 0)
    assert _read(repository, with_ko_removed.display_name).entries == ()


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
    assert repository.remove_entries_for_ticker(watchlist.display_name, ["PFE", "NOTHERE"]) == 1
    updated = _read(repository, watchlist.display_name)
    assert [entry.ticker for entry in updated.entries] == ["KO", "AAPL"]
    assert repository.remove_entries_for_ticker(updated.display_name, ["PFE"]) == 0
    again = _read(repository, updated.display_name)
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
    assert repository.remove_entries_for_ticker(watchlist.display_name, ["AAPL"]) == 2
    assert [entry.ticker for entry in _read(repository, watchlist.display_name).entries] == ["KO"]


def test_remove_entries_for_ticker_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.remove_entries_for_ticker("nonexistent", ["KO"])


def test_remove_entries_for_ticker_with_empty_sequence_is_a_no_op(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    assert repository.remove_entries_for_ticker(watchlist.display_name, []) == 0
    assert [entry.ticker for entry in _read(repository, watchlist.display_name).entries] == ["KO"]


def test_remove_entries_for_method_is_idempotent_for_absent_method(repository: SQLiteWatchlistRepository) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    watchlist = repository.add_entries(
        watchlist.display_name,
        [
            ("KO", GrahamNumberSelection()),
            ("KO", GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5)),
        ],
    )
    assert repository.remove_entries_for_method(watchlist.display_name, "sma_crossover") == 0
    unchanged = _read(repository, watchlist.display_name)
    assert [entry.selection.method_id for entry in unchanged.entries] == ["graham_number", "graham_growth_value"]
    assert repository.remove_entries_for_method(unchanged.display_name, "graham_number") == 1
    reduced = _read(repository, unchanged.display_name)
    assert [entry.selection.method_id for entry in reduced.entries] == ["graham_growth_value"]
    assert repository.remove_entries_for_method(reduced.display_name, "graham_number") == 0
    again = _read(repository, reduced.display_name)
    assert [entry.selection.method_id for entry in again.entries] == ["graham_growth_value"]


def test_remove_entries_for_method_missing_watchlist_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.remove_entries_for_method("nonexistent", "graham_number")


def test_mutations_bump_updated_at_only_when_something_changes(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Watch"))
    assert watchlist.updated_at is None
    clocked = SQLiteWatchlistRepository(
        database, clock=lambda: LATER, id_factory=lambda: SECOND_ID, alias_for=alias_for
    )
    clocked.remove_entries_for_ticker(watchlist.display_name, ["NOTHERE"])
    assert _read(clocked, watchlist.display_name).updated_at is None
    changed = clocked.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
    assert changed.updated_at == LATER


def test_reopen_preserves_full_watchlist_state(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'reopen.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteWatchlistRepository(
            first_database, clock=lambda: NOW, id_factory=lambda: FIRST_ID, alias_for=alias_for
        )
        created = repository.create(WatchlistSpec(display_name="Persisted"))
        repository.add_entries(
            created.display_name,
            [("KO", GrahamNumberSelection()), ("PFE", GrahamNumberSelection(bvps_override=9.0))],
        )
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        reopened = SQLiteWatchlistRepository(second_database, alias_for=alias_for).get("persisted")
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
        repository = SQLiteWatchlistRepository(
            database, clock=lambda: NOW, id_factory=lambda: FIRST_ID, alias_for=alias_for
        )
        watchlist = repository.create(WatchlistSpec(display_name="Offline"))
        repository.add_entries(watchlist.display_name, [("KO", GrahamNumberSelection())])
        repository.list()
        assert repository.get("offline") is not None
    finally:
        database.close()


def _store_raw_entry(database: SQLiteDatabase, watchlist_id: UUID, *, method_id: str) -> None:
    with database.transaction() as connection:
        connection.execute(
            watchlist_entries.insert().values(
                watchlist_id=str(watchlist_id),
                position=0,
                ticker="KO",
                method_id=method_id,
                config_schema_version=1,
                selection_json="{}",
            )
        )


def test_an_unreadable_entry_is_named_by_its_method_alias(
    repository: SQLiteWatchlistRepository, database: SQLiteDatabase
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Old"))
    _store_raw_entry(database, watchlist.watchlist_id, method_id="graham_number")

    with pytest.raises(StoredSelectionError, match=r"entry 1 \(KO, graham-number\)"):
        repository.get("Old")


def test_an_unreadable_entry_with_an_unmapped_method_id_is_named_as_stored(
    repository: SQLiteWatchlistRepository, database: SQLiteDatabase
) -> None:
    """A method retired by an earlier version has no alias; the error still names the entry."""
    watchlist = repository.create(WatchlistSpec(display_name="Old"))
    _store_raw_entry(database, watchlist.watchlist_id, method_id="retired_method")

    with pytest.raises(StoredSelectionError, match=r"entry 1 \(KO, retired_method\)"):
        repository.get("Old")


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


def _momentum_executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
    assert isinstance(selection, MomentumSelection)
    native = run_momentum(
        selection, ticker, _FixtureClient(), start_date="2026-01-01", executed_at=NOW, instrument_profile=None
    )
    return ExecutionCapture(native_evidence=native, profile=None, outcome=RunOutcome.COMPLETED)


def _retire_entry(database: SQLiteDatabase, *, position: int) -> None:
    """Rewrite one Momentum entry into the retired version-1 stored shape, as an earlier version saved it."""
    with database.transaction() as connection:
        selection_json = connection.execute(
            select(watchlist_entries.c.selection_json).where(watchlist_entries.c.position == position)
        ).scalar_one()
        selection = json.loads(selection_json)
        selection.pop("as_of")
        selection.pop("use_cache")
        selection["config_schema_version"] = 1
        connection.execute(
            text(
                "UPDATE watchlist_entries SET selection_json = :selection_json, config_schema_version = 1 "
                "WHERE position = :position"
            ),
            {"selection_json": json.dumps(selection), "position": position},
        )


def _seed_momentum(repository: SQLiteWatchlistRepository, name: str, tickers: list[str]) -> Watchlist:
    watchlist = repository.create(WatchlistSpec(display_name=name))
    momentum = MomentumSelection(short_window=2, long_window=3)
    return repository.add_entries(watchlist.display_name, [(ticker, momentum) for ticker in tickers])


def _row_counts(database: SQLiteDatabase) -> tuple[int, int, int]:
    with database.read() as connection:
        return (
            len(connection.execute(select(watchlists)).all()),
            len(connection.execute(select(watchlist_entries)).all()),
            len(connection.execute(select(analysis_runs)).all()),
        )


def test_delete_returns_the_pre_delete_aggregate_and_removes_everything(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="Doomed"))
    watchlist = repository.add_entries(
        watchlist.display_name, [("KO", GrahamNumberSelection()), ("PFE", GrahamNumberSelection())]
    )
    repository.create(WatchlistSpec(display_name="Survivor"))

    deleted = repository.delete("  DOOMED ")

    assert deleted.watchlist_id == watchlist.watchlist_id
    assert deleted.display_name == "Doomed"
    assert deleted.entry_count == 2
    assert deleted.watchlist == watchlist
    assert deleted.unreadable is None
    assert repository.get("Doomed") is None
    assert [summary.display_name for summary in repository.list()] == ["Survivor"]
    assert _row_counts(database)[1] == 0


def test_delete_leaves_other_watchlists_and_their_entries_untouched(repository: SQLiteWatchlistRepository) -> None:
    first = repository.create(WatchlistSpec(display_name="A"))
    repository.add_entries(first.display_name, [("KO", GrahamNumberSelection())])
    second = repository.create(WatchlistSpec(display_name="B"))
    repository.add_entries(second.display_name, [("PFE", GrahamNumberSelection())])

    repository.delete("A")

    remaining = repository.get("B")
    assert remaining is not None
    assert [entry.ticker for entry in remaining.entries] == ["PFE"]


def test_delete_of_an_unknown_name_raises_and_changes_nothing(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    repository.create(WatchlistSpec(display_name="Keep"))
    before = _row_counts(database)

    with pytest.raises(WatchlistNotFoundError):
        repository.delete("Nonexistent")

    assert _row_counts(database) == before


def test_delete_keeps_saved_runs_loadable_and_the_name_is_reusable(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = _seed_momentum(repository, "Doomed", ["AAPL"])
    runs = SQLiteAnalysisRunRepository(database)
    summary = refresh_watchlist(
        "Doomed",
        watchlists=repository,
        repository=runs,
        executor=_momentum_executor,
        run_specs=RUN_SPECS_BY_KEY,
        classify=failure_code,
    )
    saved = summary.results[0].run
    assert saved is not None
    assert _row_counts(database)[2] == 1

    repository.delete("Doomed")

    assert _row_counts(database)[2] == 1
    stored = runs.get(saved.analysis_run_id)
    assert stored is not None
    assert stored.watchlist_id == watchlist.watchlist_id
    assert stored.watchlist_name == "Doomed"
    recreated = repository.create(WatchlistSpec(display_name="Doomed"))
    assert recreated.watchlist_id != watchlist.watchlist_id


def test_the_cascade_alone_leaves_no_orphan_entries(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    """Delete removes entries explicitly; this proves the schema's ON DELETE CASCADE also covers it."""
    watchlist = _seed_momentum(repository, "Cascade", ["AAPL", "MSFT"])
    assert _row_counts(database)[1] == 2

    with database.transaction() as connection:
        connection.execute(watchlists.delete().where(watchlists.c.watchlist_id == str(watchlist.watchlist_id)))

    assert _row_counts(database)[:2] == (0, 0)


def test_delete_commits_when_entries_were_stored_by_an_earlier_version(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    """D6: delete counts stored entries and removes them without decoding any for its mutation."""
    watchlist = _seed_momentum(repository, "Old", ["AAPL", "MSFT", "KO"])
    _retire_entry(database, position=1)
    _retire_entry(database, position=2)

    deleted = repository.delete("Old")

    assert deleted.watchlist_id == watchlist.watchlist_id
    assert deleted.entry_count == 3
    assert deleted.watchlist is None
    assert isinstance(deleted.unreadable, StoredSelectionError)
    assert "entry 2 (MSFT, momentum)" in str(deleted.unreadable)
    assert repository.get("Old") is None
    assert _row_counts(database)[:2] == (0, 0)


def test_summary_counts_stored_entries_without_decoding_them(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = _seed_momentum(repository, "Old", ["AAPL", "MSFT"])
    _retire_entry(database, position=0)

    summary = repository.summary("old")

    assert summary.watchlist_id == watchlist.watchlist_id
    assert summary.display_name == "Old"
    assert summary.entry_count == 2
    with pytest.raises(WatchlistNotFoundError):
        repository.summary("Nonexistent")


def test_deleted_watchlist_holds_exactly_one_of_the_aggregate_or_the_error() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        DeletedWatchlist(watchlist_id=FIRST_ID, display_name="X", entry_count=0, watchlist=None, unreadable=None)


def test_rename_changes_the_name_keeps_the_id_and_entries_and_bumps_updated_at(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = _seed_momentum(repository, "Old Name", ["AAPL", "MSFT"])
    clocked = SQLiteWatchlistRepository(database, clock=lambda: LATER, alias_for=alias_for)

    clocked.rename("  old name ", "  New Name ")

    assert repository.get("Old Name") is None
    renamed = repository.get("new name")
    assert renamed is not None
    assert renamed.display_name == "New Name"
    assert renamed.normalized_name == "new name"
    assert renamed.watchlist_id == watchlist.watchlist_id
    assert renamed.entries == watchlist.entries
    assert renamed.created_at == watchlist.created_at
    assert renamed.updated_at == LATER


def test_rename_to_a_different_casing_of_its_own_name_changes_only_the_display_name(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    watchlist = repository.create(WatchlistSpec(display_name="core holdings"))
    clocked = SQLiteWatchlistRepository(database, clock=lambda: LATER, alias_for=alias_for)

    clocked.rename("core holdings", "Core Holdings")

    renamed = repository.get("core holdings")
    assert renamed is not None
    assert renamed.display_name == "Core Holdings"
    assert renamed.watchlist_id == watchlist.watchlist_id
    assert renamed.updated_at == LATER


def test_rename_to_the_identical_display_name_is_a_no_op_that_does_not_bump_updated_at(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    repository.create(WatchlistSpec(display_name="Same"))
    clocked = SQLiteWatchlistRepository(database, clock=lambda: LATER, alias_for=alias_for)

    clocked.rename("same", " Same ")

    unchanged = repository.get("Same")
    assert unchanged is not None
    assert unchanged.display_name == "Same"
    assert unchanged.updated_at is None


def test_rename_to_another_watchlists_name_is_a_conflict_and_changes_nothing(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    repository.create(WatchlistSpec(display_name="First"))
    repository.create(WatchlistSpec(display_name="Second"))
    before = _row_counts(database)

    with pytest.raises(WatchlistConflictError):
        repository.rename("First", "  SECOND ")

    assert _row_counts(database) == before
    unchanged = repository.get("First")
    assert unchanged is not None
    assert unchanged.display_name == "First"
    assert unchanged.updated_at is None


def test_rename_rejects_a_blank_new_name(repository: SQLiteWatchlistRepository) -> None:
    repository.create(WatchlistSpec(display_name="Keep"))

    with pytest.raises(ValueError, match="blank"):
        repository.rename("Keep", "   ")

    assert repository.get("Keep") is not None


def test_rename_of_an_unknown_name_raises(repository: SQLiteWatchlistRepository) -> None:
    with pytest.raises(WatchlistNotFoundError):
        repository.rename("Nonexistent", "Anything")


def test_rename_keeps_a_saved_runs_snapshot_name(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    _seed_momentum(repository, "Before", ["AAPL"])
    runs = SQLiteAnalysisRunRepository(database)
    summary = refresh_watchlist(
        "Before",
        watchlists=repository,
        repository=runs,
        executor=_momentum_executor,
        run_specs=RUN_SPECS_BY_KEY,
        classify=failure_code,
    )
    saved = summary.results[0].run
    assert saved is not None

    repository.rename("Before", "After")

    stored = runs.get(saved.analysis_run_id)
    assert stored is not None
    assert stored.watchlist_name == "Before"


def test_rename_commits_when_entries_were_stored_by_an_earlier_version(
    database: SQLiteDatabase, repository: SQLiteWatchlistRepository
) -> None:
    """D6: rename touches only the watchlist row, so a retired stored entry cannot prevent it."""
    watchlist = _seed_momentum(repository, "Old", ["AAPL", "MSFT"])
    _retire_entry(database, position=1)

    repository.rename("Old", "Renamed")

    with database.read() as connection:
        row = connection.execute(select(watchlists)).mappings().one()
    assert row["display_name"] == "Renamed"
    assert row["watchlist_id"] == str(watchlist.watchlist_id)
    assert _row_counts(database)[1] == 2
    with pytest.raises(StoredSelectionError, match=r"entry 2 \(MSFT, momentum\)"):
        repository.get("Renamed")
