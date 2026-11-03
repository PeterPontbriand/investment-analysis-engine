"""The watchlist read operations."""

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.core.strategy_errors import find
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID
from investment_analysis_engine.workspace.repositories.watchlists import SQLiteWatchlistRepository
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistSummary
from investment_analysis_engine.workspace.watchlists import WatchlistNotFoundError


def _stored_method_alias(method_id: str) -> str | None:
    """Return the alias of a stored method identifier, or ``None`` if this version declares no such method."""
    descriptor = find(BY_METHOD_ID, method_id)
    return None if descriptor is None else descriptor.alias


def watchlist_repository(database: SQLiteDatabase) -> SQLiteWatchlistRepository:
    """Compose the watchlist repository with the declared strategies' alias vocabulary."""
    return SQLiteWatchlistRepository(database, alias_for=_stored_method_alias)


def list_watchlists(context: ApplicationContext) -> tuple[WatchlistSummary, ...]:
    """Return a summary of every watchlist."""
    with open_database(context) as database:
        return watchlist_repository(database).list()


def get_watchlist(context: ApplicationContext, name: str) -> Watchlist:
    """Return the watchlist named ``name``.

    Raises:
        WatchlistNotFoundError: If no watchlist has that name.
    """
    with open_database(context) as database:
        watchlist = watchlist_repository(database).get(name)
    if watchlist is None:
        raise WatchlistNotFoundError(f"No watchlist named {name!r} exists.")
    return watchlist


__all__ = ["get_watchlist", "list_watchlists", "watchlist_repository"]
