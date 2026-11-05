"""The watchlist operations: reads, and the actions that create, rename, delete and edit a watchlist.

Each action checks its arguments before it opens the database (so a rejected argument is reported even when the
database is not ready), then does its write and, where it returns the watchlist, its read-back in one transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.core.strategy_errors import find
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID
from investment_analysis_engine.workspace.repositories.watchlists import (
    DeletedWatchlist,
    RemovedEntries,
    RenamedWatchlist,
    SQLiteWatchlistRepository,
)
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistSummary
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import (
    WatchlistNotFoundError,
    WatchlistRef,
    WatchlistSpec,
)


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


def get_watchlist_by_name(context: ApplicationContext, name: str) -> Watchlist:
    """Return the watchlist named ``name``.

    Raises:
        WatchlistNotFoundError: If no watchlist has that name.
    """
    with open_database(context) as database:
        watchlist = watchlist_repository(database).get(name)
    if watchlist is None:
        raise WatchlistNotFoundError(f"No watchlist named {name!r} exists.")
    return watchlist


def get_watchlist_by_id(context: ApplicationContext, watchlist_id: UUID) -> Watchlist:
    """Return the watchlist with ID ``watchlist_id``.

    Raises:
        WatchlistNotFoundError: If no watchlist has that ID.
    """
    with open_database(context) as database:
        watchlist = watchlist_repository(database).get_by_id(watchlist_id)
    if watchlist is None:
        raise WatchlistNotFoundError(f"No watchlist with ID {watchlist_id} exists.")
    return watchlist


def check_watchlist_name(name: str, *, parameter: str = "name") -> None:
    """Reject a blank watchlist name.

    Raises:
        ActionParameterError: If ``name`` is blank after trimming; ``parameter`` is the action's name for it.
    """
    if not name.strip():
        raise ActionParameterError(f"{{{parameter}}} must not be blank.", parameters=(parameter,))


def check_tickers(tickers: Sequence[str]) -> None:
    """Reject a blank ticker.

    Raises:
        ActionParameterError: If any ticker is blank after trimming; the parameter is ``tickers``.
    """
    if any(not ticker.strip() for ticker in tickers):
        raise ActionParameterError("{tickers} must not be empty.", parameters=("tickers",))


def create_watchlist(context: ApplicationContext, name: str) -> Watchlist:
    """Create a watchlist with no entries.

    Raises:
        ActionParameterError: If ``name`` is blank (parameter ``name``); nothing is opened or written.
        WatchlistConflictError: If a watchlist with the same normalized name exists.
    """
    check_watchlist_name(name)
    with open_database(context) as database:
        return watchlist_repository(database).create(WatchlistSpec(display_name=name))


def rename_watchlist(context: ApplicationContext, ref: WatchlistRef, new_name: str) -> RenamedWatchlist:
    """Rename a watchlist and read it back in the same transaction.

    The result holds exactly one of the renamed watchlist and the error that makes one of its entries
    unreadable; the rename is committed either way.

    Raises:
        ActionParameterError: If ``new_name`` is blank (parameter ``new_name``); nothing is opened or written.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        WatchlistConflictError: If the new name belongs to a different watchlist.
    """
    check_watchlist_name(new_name, parameter="new_name")
    with open_database(context) as database:
        return watchlist_repository(database).rename(ref, new_name)


def delete_watchlist(context: ApplicationContext, ref: WatchlistRef) -> DeletedWatchlist:
    """Delete a watchlist and its entries; saved Analysis Runs are kept.

    Raises:
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    with open_database(context) as database:
        return watchlist_repository(database).delete(ref)


def get_watchlist_summary(context: ApplicationContext, ref: WatchlistRef) -> WatchlistSummary:
    """Return a watchlist's identity and stored entry count without decoding any entry.

    Raises:
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    with open_database(context) as database:
        return watchlist_repository(database).summary(ref)


def add_watchlist_entries(
    context: ApplicationContext, ref: WatchlistRef, entries: Sequence[tuple[str, AnalysisSelection]]
) -> Watchlist:
    """Append one entry per (ticker, selection) pair and return the watchlist.

    Nothing is written when the watchlist holds an entry this version cannot read.

    Raises:
        ActionParameterError: If a ticker is blank (parameter ``tickers``); nothing is opened or written.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        StoredSelectionError: If an entry of the watchlist cannot be read.
    """
    check_tickers([ticker for ticker, _ in entries])
    with open_database(context) as database:
        return watchlist_repository(database).add_entries(ref, entries)


def remove_watchlist_entry(context: ApplicationContext, ref: WatchlistRef, entry_number: int) -> RemovedEntries:
    """Remove the entry with the 1-based ``entry_number`` and read the watchlist back in the same transaction.

    Raises:
        ActionParameterError: If ``entry_number`` is below 1 (parameter ``entry_number``).
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        WatchlistEntryNotFoundError: If the watchlist has no entry with that number.
    """
    if entry_number < 1:
        raise ActionParameterError("{entry_number} must be 1 or greater.", parameters=("entry_number",))
    with open_database(context) as database:
        return watchlist_repository(database).remove_entry(ref, entry_number - 1)


def remove_watchlist_tickers(context: ApplicationContext, ref: WatchlistRef, tickers: Sequence[str]) -> RemovedEntries:
    """Remove every entry for the given tickers (idempotent) and read the watchlist back in the same transaction.

    Raises:
        ActionParameterError: If a ticker is blank (parameter ``tickers``); nothing is opened or written.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    check_tickers(tickers)
    with open_database(context) as database:
        return watchlist_repository(database).remove_entries_for_ticker(ref, tickers)


def remove_watchlist_method(context: ApplicationContext, ref: WatchlistRef, method_id: str) -> RemovedEntries:
    """Remove every entry for ``method_id`` (idempotent) and read the watchlist back in the same transaction.

    Raises:
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    with open_database(context) as database:
        return watchlist_repository(database).remove_entries_for_method(ref, method_id)


__all__ = [
    "add_watchlist_entries",
    "check_tickers",
    "check_watchlist_name",
    "create_watchlist",
    "delete_watchlist",
    "get_watchlist_by_id",
    "get_watchlist_by_name",
    "get_watchlist_summary",
    "list_watchlists",
    "remove_watchlist_entry",
    "remove_watchlist_method",
    "remove_watchlist_tickers",
    "rename_watchlist",
    "watchlist_repository",
]
