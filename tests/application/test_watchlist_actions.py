"""The watchlist actions: create, rename, delete, add, remove and summary, called as the CLI and the API call them."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.watchlists import (
    add_watchlist_entries,
    create_watchlist,
    delete_watchlist,
    get_watchlist_by_id,
    get_watchlist_by_name,
    get_watchlist_summary,
    list_watchlists,
    remove_watchlist_entry,
    remove_watchlist_method,
    remove_watchlist_tickers,
    rename_watchlist,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.repositories.watchlists import (
    RemovedEntries,
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from investment_analysis_engine.workspace.watchlists import (
    StoredSelectionError,
    WatchlistId,
    WatchlistName,
    WatchlistNotFoundError,
    WatchlistRef,
)
from tests.application._unready_database import unready_database_url

_MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_GRAHAM = GrahamNumberSelection()


def _context(settings: ProjectSettings) -> ApplicationContext:
    return ApplicationContext(settings=settings)


def _unready(directory: Path) -> ApplicationContext:
    return ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(directory)))


def _seed_core(settings: ProjectSettings) -> None:
    """Create ``Core`` holding AAPL and MSFT (momentum) and KO (graham-number), in that order."""
    context = _context(settings)
    create_watchlist(context, "Core")
    add_watchlist_entries(context, WatchlistName("Core"), [("AAPL", _MOMENTUM), ("MSFT", _MOMENTUM), ("KO", _GRAHAM)])


def _retire_entry(settings: ProjectSettings, ticker: str) -> None:
    """Rewrite one stored entry into a shape this version cannot read."""
    path = settings.database_url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    try:
        connection.execute("update watchlist_entries set selection_json = ? where ticker = ?", ('{"x":1}', ticker))
        connection.commit()
    finally:
        connection.close()


def _entry_tickers(settings: ProjectSettings) -> list[str]:
    path = settings.database_url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("select ticker from watchlist_entries order by position").fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


def _by_name_and_id(settings: ProjectSettings) -> list[WatchlistRef]:
    summary = get_watchlist_summary(_context(settings), WatchlistName("Core"))
    return [WatchlistName("Core"), WatchlistId(summary.watchlist_id)]


# create


def test_create_returns_an_empty_watchlist_with_the_trimmed_name(isolated_cli_settings: ProjectSettings) -> None:
    watchlist = create_watchlist(_context(isolated_cli_settings), "  Core ")

    assert (watchlist.display_name, watchlist.entries, watchlist.updated_at) == ("Core", (), None)
    assert get_watchlist_by_id(_context(isolated_cli_settings), watchlist.watchlist_id) == watchlist


def test_create_of_an_existing_name_is_a_conflict(isolated_cli_settings: ProjectSettings) -> None:
    create_watchlist(_context(isolated_cli_settings), "Core")

    with pytest.raises(WatchlistConflictError):
        create_watchlist(_context(isolated_cli_settings), " core ")
    assert [item.display_name for item in list_watchlists(_context(isolated_cli_settings))] == ["Core"]


def test_create_of_a_blank_name_names_the_name_parameter_and_writes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with pytest.raises(ActionParameterError) as caught:
        create_watchlist(_context(isolated_cli_settings), "   ")

    assert (str(caught.value), caught.value.parameters) == ("name must not be blank.", ("name",))
    assert list_watchlists(_context(isolated_cli_settings)) == ()


# rename


def test_rename_by_name_or_id_returns_the_renamed_watchlist(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)
    by_name, by_id = _by_name_and_id(isolated_cli_settings)

    first = rename_watchlist(_context(isolated_cli_settings), by_name, " Renamed ")
    second = rename_watchlist(_context(isolated_cli_settings), by_id, "Again")

    assert first.unreadable is None
    assert first.watchlist is not None
    assert (first.watchlist.display_name, [entry.ticker for entry in first.watchlist.entries]) == (
        "Renamed",
        ["AAPL", "MSFT", "KO"],
    )
    assert second.watchlist is not None
    assert second.watchlist.display_name == "Again"
    assert second.watchlist.watchlist_id == first.watchlist.watchlist_id


def test_rename_commits_and_returns_the_error_when_an_entry_is_unreadable(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)
    _retire_entry(isolated_cli_settings, "MSFT")

    renamed = rename_watchlist(_context(isolated_cli_settings), WatchlistName("Core"), "Renamed")

    assert renamed.watchlist is None
    assert renamed.unreadable is not None
    assert (renamed.unreadable.watchlist_name, renamed.unreadable.entry_number) == ("Renamed", 2)
    assert [item.display_name for item in list_watchlists(_context(isolated_cli_settings))] == ["Renamed"]


def test_rename_to_a_name_that_belongs_to_another_watchlist_is_a_conflict(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)
    create_watchlist(_context(isolated_cli_settings), "Other")

    with pytest.raises(WatchlistConflictError):
        rename_watchlist(_context(isolated_cli_settings), WatchlistName("Core"), "other")


def test_rename_to_a_blank_name_names_the_new_name_parameter(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        rename_watchlist(_context(isolated_cli_settings), WatchlistName("Core"), " ")

    assert (str(caught.value), caught.value.parameters) == ("new_name must not be blank.", ("new_name",))


# delete and summary


def test_delete_by_name_or_id_removes_the_watchlist_and_returns_what_it_held(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)
    by_name, by_id = _by_name_and_id(isolated_cli_settings)

    deleted = delete_watchlist(_context(isolated_cli_settings), by_id)

    assert (deleted.display_name, deleted.entry_count) == ("Core", 3)
    assert deleted.watchlist is not None
    assert list_watchlists(_context(isolated_cli_settings)) == ()
    with pytest.raises(WatchlistNotFoundError):
        delete_watchlist(_context(isolated_cli_settings), by_name)


def test_delete_of_a_watchlist_with_an_unreadable_entry_still_deletes_it(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)
    _retire_entry(isolated_cli_settings, "KO")

    deleted = delete_watchlist(_context(isolated_cli_settings), WatchlistName("Core"))

    assert deleted.watchlist is None
    assert deleted.unreadable is not None
    assert list_watchlists(_context(isolated_cli_settings)) == ()


def test_summary_counts_entries_by_name_or_id_without_decoding_them(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)
    _retire_entry(isolated_cli_settings, "KO")

    summaries = [
        get_watchlist_summary(_context(isolated_cli_settings), ref) for ref in _by_name_and_id(isolated_cli_settings)
    ]

    assert [(item.display_name, item.entry_count) for item in summaries] == [("Core", 3), ("Core", 3)]
    assert summaries[0] == summaries[1]


def test_a_rename_between_the_summary_and_the_delete_cannot_delete_another_watchlist(
    isolated_cli_settings: ProjectSettings,
) -> None:
    """The command asks from the summary and deletes by its ID: the name may mean another watchlist by then."""
    _seed_core(isolated_cli_settings)
    context = _context(isolated_cli_settings)
    asked_about = get_watchlist_summary(context, WatchlistName("Core"))
    rename_watchlist(context, WatchlistName("Core"), "Renamed")
    replacement = create_watchlist(context, "Core")

    deleted = delete_watchlist(context, WatchlistId(asked_about.watchlist_id))

    assert deleted.watchlist_id == asked_about.watchlist_id
    assert [(item.watchlist_id, item.display_name) for item in list_watchlists(context)] == [
        (replacement.watchlist_id, "Core")
    ]


@pytest.mark.parametrize(
    "operation",
    [
        lambda context, ref: rename_watchlist(context, ref, "New"),
        delete_watchlist,
        get_watchlist_summary,
        lambda context, ref: add_watchlist_entries(context, ref, [("KO", _GRAHAM)]),
        lambda context, ref: remove_watchlist_entry(context, ref, 1),
        lambda context, ref: remove_watchlist_tickers(context, ref, ["KO"]),
        lambda context, ref: remove_watchlist_method(context, ref, "graham_number"),
    ],
    ids=["rename", "delete", "summary", "add", "remove-entry", "remove-ticker", "remove-method"],
)
def test_a_missing_watchlist_is_not_found_by_name_and_by_id_with_each_message(
    operation: Callable[[ApplicationContext, WatchlistRef], object], isolated_cli_settings: ProjectSettings
) -> None:
    _seed_core(isolated_cli_settings)
    missing = uuid4()

    with pytest.raises(WatchlistNotFoundError) as by_name:
        operation(_context(isolated_cli_settings), WatchlistName("Nowhere"))
    with pytest.raises(WatchlistNotFoundError) as by_id:
        operation(_context(isolated_cli_settings), WatchlistId(missing))

    assert str(by_name.value) == "No watchlist named 'Nowhere' exists."
    assert str(by_id.value) == f"No watchlist with ID {missing} exists."


# add


def test_add_appends_entries_by_name_or_id_and_returns_the_watchlist(isolated_cli_settings: ProjectSettings) -> None:
    create_watchlist(_context(isolated_cli_settings), "Core")
    by_name = WatchlistName("Core")
    by_id = WatchlistId(get_watchlist_by_name(_context(isolated_cli_settings), "Core").watchlist_id)

    first = add_watchlist_entries(_context(isolated_cli_settings), by_name, [(" aapl ", _MOMENTUM)])
    second = add_watchlist_entries(_context(isolated_cli_settings), by_id, [("KO", _GRAHAM)])

    assert [entry.ticker for entry in first.entries] == ["AAPL"]
    assert [entry.ticker for entry in second.entries] == ["AAPL", "KO"]
    assert second.updated_at is not None


def test_add_with_a_blank_ticker_names_the_tickers_parameter_and_writes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        add_watchlist_entries(
            _context(isolated_cli_settings), WatchlistName("Core"), [("MSFT", _GRAHAM), (" ", _GRAHAM)]
        )

    assert (str(caught.value), caught.value.parameters) == ("tickers must not be empty.", ("tickers",))
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


def test_add_to_a_watchlist_with_an_unreadable_entry_is_refused_and_writes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)
    _retire_entry(isolated_cli_settings, "MSFT")
    before = get_watchlist_summary(_context(isolated_cli_settings), WatchlistName("Core"))

    with pytest.raises(StoredSelectionError) as caught:
        add_watchlist_entries(_context(isolated_cli_settings), WatchlistName("Core"), [("NVDA", _GRAHAM)])

    assert (caught.value.watchlist_name, caught.value.entry_number, caught.value.ticker) == ("Core", 2, "MSFT")
    assert get_watchlist_summary(_context(isolated_cli_settings), WatchlistName("Core")) == before
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


# remove


def test_remove_entry_removes_the_one_with_that_1_based_number(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)
    by_name, by_id = _by_name_and_id(isolated_cli_settings)

    first = remove_watchlist_entry(_context(isolated_cli_settings), by_name, 2)
    second = remove_watchlist_entry(_context(isolated_cli_settings), by_id, 1)

    assert first.removed == 1
    assert first.watchlist is not None
    assert [entry.ticker for entry in first.watchlist.entries] == ["AAPL", "KO"]
    assert second.watchlist is not None
    assert [entry.ticker for entry in second.watchlist.entries] == ["KO"]


def test_remove_entry_below_1_names_the_entry_number_parameter(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        remove_watchlist_entry(_context(isolated_cli_settings), WatchlistName("Core"), 0)

    assert (str(caught.value), caught.value.parameters) == (
        "entry_number must be 1 or greater.",
        ("entry_number",),
    )
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


def test_remove_entry_past_the_last_entry_is_not_found_and_removes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)

    for ref in _by_name_and_id(isolated_cli_settings):
        with pytest.raises(WatchlistEntryNotFoundError) as caught:
            remove_watchlist_entry(_context(isolated_cli_settings), ref, 4)
        assert str(caught.value) == "Watchlist 'Core' has no entry 4."
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


def test_remove_tickers_removes_every_entry_for_them_and_is_idempotent(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)
    by_name, by_id = _by_name_and_id(isolated_cli_settings)

    removed = remove_watchlist_tickers(_context(isolated_cli_settings), by_name, ["ko", "NOTHERE"])
    again = remove_watchlist_tickers(_context(isolated_cli_settings), by_id, ["KO"])

    assert removed.removed == 1
    assert removed.watchlist is not None
    assert [entry.ticker for entry in removed.watchlist.entries] == ["AAPL", "MSFT"]
    assert again.removed == 0
    assert again.watchlist == removed.watchlist


def test_remove_tickers_with_a_blank_ticker_names_the_tickers_parameter_and_removes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        remove_watchlist_tickers(_context(isolated_cli_settings), WatchlistName("Core"), ["KO", " "])

    assert (str(caught.value), caught.value.parameters) == ("tickers must not be empty.", ("tickers",))
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


def test_remove_method_removes_every_entry_for_it_and_is_idempotent(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core(isolated_cli_settings)
    by_name, by_id = _by_name_and_id(isolated_cli_settings)

    removed = remove_watchlist_method(_context(isolated_cli_settings), by_name, _MOMENTUM.method_id)
    again = remove_watchlist_method(_context(isolated_cli_settings), by_id, _MOMENTUM.method_id)

    assert removed.removed == 2
    assert removed.watchlist is not None
    assert [entry.ticker for entry in removed.watchlist.entries] == ["KO"]
    assert (again.removed, again.watchlist) == (0, removed.watchlist)


@pytest.mark.parametrize(
    "operation",
    [
        lambda context: remove_watchlist_entry(context, WatchlistName("Core"), 1),
        lambda context: remove_watchlist_tickers(context, WatchlistName("Core"), ["AAPL"]),
        lambda context: remove_watchlist_method(context, WatchlistName("Core"), _GRAHAM.method_id),
    ],
    ids=["remove-entry", "remove-ticker", "remove-method"],
)
def test_a_removal_commits_and_returns_the_error_when_another_entry_is_unreadable(
    operation: Callable[[ApplicationContext], RemovedEntries], isolated_cli_settings: ProjectSettings
) -> None:
    _seed_core(isolated_cli_settings)
    _retire_entry(isolated_cli_settings, "MSFT")
    before = _entry_tickers(isolated_cli_settings)

    removed = operation(_context(isolated_cli_settings))

    assert removed.watchlist is None
    unreadable = removed.unreadable
    assert isinstance(unreadable, StoredSelectionError)
    assert (unreadable.ticker, unreadable.method) == ("MSFT", "momentum")
    after = _entry_tickers(isolated_cli_settings)
    assert len(after) == len(before) - 1
    assert "MSFT" in after
    assert unreadable.entry_number == after.index("MSFT") + 1


# arguments are checked before the database opens


@pytest.mark.parametrize(
    ("operation", "parameters"),
    [
        (lambda context: create_watchlist(context, " "), ("name",)),
        (lambda context: rename_watchlist(context, WatchlistName("Core"), " "), ("new_name",)),
        (lambda context: add_watchlist_entries(context, WatchlistName("Core"), [(" ", _GRAHAM)]), ("tickers",)),
        (lambda context: remove_watchlist_entry(context, WatchlistName("Core"), 0), ("entry_number",)),
        (lambda context: remove_watchlist_tickers(context, WatchlistName("Core"), [" "]), ("tickers",)),
        (
            lambda context: remove_watchlist_method(context, WatchlistName("Core"), "retired_method"),
            ("method_id",),
        ),
    ],
    ids=["create", "rename", "add", "remove-entry", "remove-ticker", "remove-method"],
)
def test_a_bad_argument_is_reported_even_when_the_database_is_not_ready(
    operation: Callable[[ApplicationContext], object], parameters: tuple[str, ...], tmp_path: Path
) -> None:
    with pytest.raises(ActionParameterError) as caught:
        operation(_unready(tmp_path))

    assert caught.value.parameters == parameters


@pytest.mark.parametrize(
    "operation",
    [
        lambda context: create_watchlist(context, "Core"),
        lambda context: rename_watchlist(context, WatchlistName("Core"), "New"),
        lambda context: delete_watchlist(context, WatchlistName("Core")),
        lambda context: get_watchlist_summary(context, WatchlistName("Core")),
        lambda context: add_watchlist_entries(context, WatchlistName("Core"), [("KO", _GRAHAM)]),
        lambda context: remove_watchlist_entry(context, WatchlistName("Core"), 1),
        lambda context: remove_watchlist_tickers(context, WatchlistName("Core"), ["KO"]),
        lambda context: remove_watchlist_method(context, WatchlistName("Core"), "graham_number"),
    ],
    ids=["create", "rename", "delete", "summary", "add", "remove-entry", "remove-ticker", "remove-method"],
)
def test_a_valid_call_on_a_database_that_is_not_ready_is_a_readiness_error(
    operation: Callable[[ApplicationContext], object], tmp_path: Path
) -> None:
    with pytest.raises(DatabaseReadinessError):
        operation(_unready(tmp_path))


def test_remove_method_rejects_an_undeclared_method_before_the_database_is_opened(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        remove_watchlist_method(_context(isolated_cli_settings), WatchlistName("Core"), "retired_method")

    assert (str(caught.value), caught.value.parameters) == ("method_id is not a declared method.", ("method_id",))
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]


def test_remove_tickers_rejects_an_empty_list_and_add_rejects_an_empty_entry_list(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as removal:
        remove_watchlist_tickers(_context(isolated_cli_settings), WatchlistName("Core"), [])
    with pytest.raises(ActionParameterError) as addition:
        add_watchlist_entries(_context(isolated_cli_settings), WatchlistName("Core"), [])

    assert (str(removal.value), removal.value.parameters) == ("tickers must name at least one ticker.", ("tickers",))
    assert (str(addition.value), addition.value.parameters) == (
        "entries must hold at least one entry.",
        ("entries",),
    )
    assert _entry_tickers(isolated_cli_settings) == ["AAPL", "MSFT", "KO"]
