"""The watchlist read operations: list, get and the repository composition."""

from collections.abc import Callable
from pathlib import Path

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.watchlists import get_watchlist, list_watchlists, watchlist_repository
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.watchlists import WatchlistNotFoundError, WatchlistSpec
from tests.application._unready_database import unready_database_url

_SELECTION = MomentumSelection(short_window=2, long_window=3, rsi_period=14)


def _seed(settings: ProjectSettings) -> None:
    with open_database(ApplicationContext(settings=settings)) as database:
        repository = watchlist_repository(database)
        repository.create(WatchlistSpec(display_name="Empty"))
        repository.create(WatchlistSpec(display_name="Core"))
        repository.add_entries("Core", [("AAPL", _SELECTION), ("msft", _SELECTION)])


def test_an_empty_store_lists_no_watchlists(isolated_cli_settings: ProjectSettings) -> None:
    assert list_watchlists(ApplicationContext(settings=isolated_cli_settings)) == ()


def test_the_list_summarizes_every_watchlist_with_its_entry_count(isolated_cli_settings: ProjectSettings) -> None:
    _seed(isolated_cli_settings)

    summaries = list_watchlists(ApplicationContext(settings=isolated_cli_settings))

    assert {item.display_name: item.entry_count for item in summaries} == {"Empty": 0, "Core": 2}
    by_name = {item.display_name: item for item in summaries}
    assert by_name["Empty"].updated_at is None
    assert by_name["Core"].updated_at is not None


def test_get_returns_the_watchlist_with_its_entries_in_order(isolated_cli_settings: ProjectSettings) -> None:
    _seed(isolated_cli_settings)

    watchlist = get_watchlist(ApplicationContext(settings=isolated_cli_settings), "Core")

    assert watchlist.display_name == "Core"
    assert [entry.ticker for entry in watchlist.entries] == ["AAPL", "MSFT"]


def test_get_of_an_unknown_name_raises_the_not_found_error_with_the_message_the_command_prints(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with pytest.raises(WatchlistNotFoundError) as caught:
        get_watchlist(ApplicationContext(settings=isolated_cli_settings), "Nowhere")
    assert str(caught.value) == "No watchlist named 'Nowhere' exists."


@pytest.mark.parametrize(
    "operation",
    [list_watchlists, lambda context: get_watchlist(context, "Core")],
    ids=["list", "get"],
)
def test_an_unready_database_is_a_readiness_error(
    operation: Callable[[ApplicationContext], object], tmp_path: Path
) -> None:
    context = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))
    with pytest.raises(DatabaseReadinessError):
        operation(context)
