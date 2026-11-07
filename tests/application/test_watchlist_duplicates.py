"""An add refuses an entry that repeats another, the same ticker with an equal selection (``entries.duplicate``)."""

from pathlib import Path

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.watchlists import (
    REPEATED_IN_REQUEST,
    REPEATED_IN_WATCHLIST,
    add_watchlist_entries,
    create_watchlist,
    get_watchlist_by_name,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.watchlists import WatchlistName
from tests.application._unready_database import unready_database_url

_MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_OTHER = MomentumSelection(short_window=2, long_window=4, rsi_period=14)
_REF = WatchlistName("Core")


def _seeded(settings: ProjectSettings) -> ApplicationContext:
    context = ApplicationContext(settings=settings)
    create_watchlist(context, "Core")
    return context


def test_a_repeat_within_the_request_is_refused_before_the_database_opens(tmp_path: Path) -> None:
    unready = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))

    with pytest.raises(ActionParameterError) as caught:
        add_watchlist_entries(unready, _REF, [("AAPL", _MOMENTUM), ("MSFT", _MOMENTUM), (" aapl", _MOMENTUM)])

    error = caught.value
    assert error.rule == "entries.duplicate"
    assert error.template == (
        "{tickers} must not duplicate an entry: {ticker} is already listed for {method_id} with an equal selection "
        "{where}."
    )
    assert error.arguments == {"ticker": "AAPL", "method_id": _MOMENTUM.method_id, "where": REPEATED_IN_REQUEST}
    assert error.action_parameters == ("tickers",)
    assert str(error) == (
        "tickers must not duplicate an entry: AAPL is already listed for sma_crossover with an equal selection "
        "earlier in this request."
    )


def test_every_repeat_in_the_request_is_listed(isolated_cli_settings: ProjectSettings) -> None:
    context = _seeded(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        add_watchlist_entries(
            context, _REF, [("AAPL", _MOMENTUM), ("AAPL", _MOMENTUM), ("MSFT", _MOMENTUM), ("MSFT", _MOMENTUM)]
        )

    assert [item.arguments["ticker"] for item in caught.value.errors] == ["AAPL", "MSFT"]
    assert get_watchlist_by_name(context, "Core").entries == ()


def test_a_repeat_of_a_stored_entry_is_refused_and_nothing_is_written(isolated_cli_settings: ProjectSettings) -> None:
    context = _seeded(isolated_cli_settings)
    add_watchlist_entries(context, _REF, [("AAPL", _MOMENTUM)])

    with pytest.raises(ActionParameterError) as caught:
        add_watchlist_entries(context, _REF, [("KO", _MOMENTUM), ("aapl", _MOMENTUM)])

    assert caught.value.rule == "entries.duplicate"
    assert caught.value.arguments == {
        "ticker": "AAPL",
        "method_id": _MOMENTUM.method_id,
        "where": REPEATED_IN_WATCHLIST,
    }
    assert str(caught.value).endswith("with an equal selection in the watchlist.")
    assert [entry.ticker for entry in get_watchlist_by_name(context, "Core").entries] == ["AAPL"]


def test_the_same_ticker_under_another_selection_or_another_method_is_not_a_duplicate(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seeded(isolated_cli_settings)
    add_watchlist_entries(context, _REF, [("AAPL", _MOMENTUM)])

    watchlist = add_watchlist_entries(context, _REF, [("AAPL", _OTHER), ("AAPL", GrahamNumberSelection())])

    assert [(entry.ticker, entry.selection.method_id) for entry in watchlist.entries] == [
        ("AAPL", _MOMENTUM.method_id),
        ("AAPL", _OTHER.method_id),
        ("AAPL", GrahamNumberSelection().method_id),
    ]
