"""The watchlist operations: reads, and the actions that create, rename, delete and edit a watchlist.

Each action checks its arguments before it opens the database (so a rejected argument is reported even when the
database is not ready), then does its write and, where it returns the watchlist, its read-back in one transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.core.strategy_errors import find, require
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID
from investment_analysis_engine.workspace.repositories.watchlists import (
    DeletedWatchlist,
    DuplicateEntryError,
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
    encode_selection,
)

REPEATED_IN_REQUEST = "earlier in this request"
"""Where a duplicate entry's twin is, when it is another entry of the same request."""

REPEATED_IN_WATCHLIST = "in the watchlist"
"""Where a duplicate entry's twin is, when it is an entry the watchlist already holds."""


def _stored_method_alias(method_id: str) -> str | None:
    """Return the alias of a stored method identifier, or ``None`` if this version declares no such method."""
    descriptor = find(BY_METHOD_ID, method_id)
    return None if descriptor is None else descriptor.alias


def alias_for_method_id(method_id: str) -> str:
    """Return the CLI alias of a declared method; an undeclared one is a programming error, not a fallback."""
    return require(BY_METHOD_ID, method_id, what="method id").alias


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


def _check_watchlist_name(name: str, *, parameter: str = "name") -> None:
    """Reject a blank watchlist name.

    Raises:
        ActionParameterError: If ``name`` is blank after trimming; ``parameter`` is the action's name for it.
    """
    if not name.strip():
        raise ActionParameterError(
            f"{{{parameter}}} must not be blank.", parameters=(parameter,), rule="watchlist.blank_name"
        )


def _check_tickers(tickers: Sequence[str]) -> None:
    """Reject a blank ticker.

    Raises:
        ActionParameterError: If any ticker is blank after trimming; the parameter is ``tickers``.
    """
    if any(not ticker.strip() for ticker in tickers):
        raise ActionParameterError(
            "{tickers} must not be empty.", parameters=("tickers",), rule="watchlist.blank_ticker"
        )


def duplicate_entry_error(parameter: str, ticker: str, method_id: str, where: str) -> ActionParameterError:
    """Return the error of an entry that repeats another: the same ticker with an equal selection.

    This is the one rule of a duplicate, ``entries.duplicate``, for a list of entries to refresh and for every add to a
    watchlist.

    Args:
        parameter: The action's name for the offending entry or entries.
        ticker: The normalized ticker.
        method_id: The strategy's method identifier.
        where: Where the other entry is: :data:`REPEATED_IN_REQUEST` or :data:`REPEATED_IN_WATCHLIST`.
    """
    return ActionParameterError(
        f"{{{parameter}}} must not duplicate an entry: {{ticker}} is already listed for {{method_id}} with an equal "
        "selection {where}.",
        parameters=(parameter,),
        rule="entries.duplicate",
        arguments={"ticker": ticker, "method_id": method_id, "where": where},
    )


def entry_key(ticker: str, selection: AnalysisSelection) -> tuple[str, str]:
    """Return what makes two entries equal: the normalized ticker and the canonical text of the selection."""
    return normalize_ticker(ticker), encode_selection(selection)


def create_watchlist(context: ApplicationContext, name: str) -> Watchlist:
    """Create a watchlist with no entries.

    Raises:
        ActionParameterError: If ``name`` is blank (parameter ``name``); nothing is opened or written.
        WatchlistConflictError: If a watchlist with the same normalized name exists.
    """
    _check_watchlist_name(name)
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
    _check_watchlist_name(new_name, parameter="new_name")
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
        ActionParameterError: If ``entries`` is empty (parameter ``entries``), a ticker is blank or an entry repeats
            another entry of the request or one the watchlist holds, the same ticker with an equal selection
            (parameter ``tickers``, rule ``entries.duplicate``); nothing is written, and a repeat within the request
            is found before anything is opened.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        StoredSelectionError: If an entry of the watchlist cannot be read.
    """
    if not entries:
        raise ActionParameterError(
            "{entries} must hold at least one entry.", parameters=("entries",), rule="watchlist.no_entries"
        )
    _check_tickers([ticker for ticker, _ in entries])
    seen: set[tuple[str, str]] = set()
    repeated: list[ActionParameterError] = []
    for ticker, selection in entries:
        key = entry_key(ticker, selection)
        if key in seen:
            repeated.append(duplicate_entry_error("tickers", key[0], selection.method_id, REPEATED_IN_REQUEST))
        seen.add(key)
    if repeated:
        raise ActionParameterError.several(repeated)
    with open_database(context) as database:
        try:
            return watchlist_repository(database).add_entries(ref, entries)
        except DuplicateEntryError as exc:
            raise ActionParameterError.several(
                [
                    duplicate_entry_error("tickers", ticker, method_id, REPEATED_IN_WATCHLIST)
                    for ticker, method_id in exc.duplicates
                ]
            ) from None


def remove_watchlist_entry(context: ApplicationContext, ref: WatchlistRef, entry_number: int) -> RemovedEntries:
    """Remove the entry with the 1-based ``entry_number`` and read the watchlist back in the same transaction.

    Raises:
        ActionParameterError: If ``entry_number`` is below 1 (parameter ``entry_number``).
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        WatchlistEntryNotFoundError: If the watchlist has no entry with that number.
    """
    if entry_number < 1:
        raise ActionParameterError(
            "{entry_number} must be 1 or greater.",
            parameters=("entry_number",),
            rule="watchlist.entry_number_below_one",
        )
    with open_database(context) as database:
        return watchlist_repository(database).remove_entry(ref, entry_number - 1)


def remove_watchlist_tickers(context: ApplicationContext, ref: WatchlistRef, tickers: Sequence[str]) -> RemovedEntries:
    """Remove every entry for the given tickers (idempotent) and read the watchlist back in the same transaction.

    Raises:
        ActionParameterError: If ``tickers`` is empty or holds a blank ticker (parameter ``tickers``); nothing is
            opened or written.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    if not tickers:
        raise ActionParameterError(
            "{tickers} must name at least one ticker.", parameters=("tickers",), rule="watchlist.no_tickers"
        )
    _check_tickers(tickers)
    with open_database(context) as database:
        return watchlist_repository(database).remove_entries_for_ticker(ref, tickers)


def remove_watchlist_method(context: ApplicationContext, ref: WatchlistRef, method_id: str) -> RemovedEntries:
    """Remove every entry for ``method_id`` (idempotent) and read the watchlist back in the same transaction.

    Raises:
        ActionParameterError: If ``method_id`` is not a declared method (parameter ``method_id``); nothing is opened.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
    """
    if find(BY_METHOD_ID, method_id) is None:
        raise ActionParameterError(
            "{method_id} is not a declared method.", parameters=("method_id",), rule="watchlist.undeclared_method"
        )
    with open_database(context) as database:
        return watchlist_repository(database).remove_entries_for_method(ref, method_id)


__all__ = [
    "REPEATED_IN_REQUEST",
    "REPEATED_IN_WATCHLIST",
    "alias_for_method_id",
    "add_watchlist_entries",
    "create_watchlist",
    "delete_watchlist",
    "duplicate_entry_error",
    "entry_key",
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
