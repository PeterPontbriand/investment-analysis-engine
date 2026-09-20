"""SQLite-backed watchlist repository: create, entry edits, reopen.

No provider, network, or analysis work occurs here; only reads/writes against
a caller-owned, already-migrated :class:`SQLiteDatabase`. Conflicts and
missing lookups raise typed errors rather than leaking SQLAlchemy/SQLite
exceptions. Each public method is one short transaction; nothing is left
partially written on failure.

A watchlist holds one ordered list of entries (Amendment A1, §12), not a
separate membership list and selection list. Every mutation that removes one
or more entries renumbers the survivors to stay contiguous from zero, so the
stored ``position`` column always matches what a caller derives a 1-based,
human-facing index from (``index = position + 1``) — there is never a gap
left behind by a deletion.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from src.data.repositories.schema import watchlist_entries, watchlists
from src.data.repositories.sqlite import SQLiteDatabase
from src.workspace.requests import AnalysisSelection
from src.workspace.runs import Watchlist, WatchlistEntry, WatchlistSummary
from src.workspace.watchlists import WatchlistSpec, decode_selection, encode_selection, normalize_ticker


class WatchlistConflictError(ValueError):
    """A watchlist with the same normalized name already exists."""


class WatchlistNotFoundError(ValueError):
    """No watchlist exists with the requested name."""


class WatchlistEntryNotFoundError(ValueError):
    """No entry exists at the requested 0-based position."""


def _normalize_name(name: str) -> str:
    """Apply the watchlist name comparison convention: trim, then casefold."""
    return name.strip().casefold()


def _utc(value: datetime) -> str:
    """Encode a timezone-aware instant without guessing a missing timezone."""
    if value.utcoffset() is None:
        raise ValueError("Storage timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class SQLiteWatchlistRepository:
    """Persist watchlist aggregates in a borrowed migrated database."""

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        """Retain a caller-owned database and injected clock/ID generator."""
        self._database = database
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._id_factory = id_factory if id_factory is not None else uuid4

    def create(self, spec: WatchlistSpec) -> Watchlist:
        """Create a watchlist with no entries.

        Raises:
            ValueError: If ``spec.display_name`` is blank after trimming.
            WatchlistConflictError: If a watchlist with the same normalized
                name already exists.
        """
        watchlist = Watchlist(
            watchlist_id=self._id_factory(),
            display_name=spec.display_name.strip(),
            normalized_name=_normalize_name(spec.display_name),
            created_at=self._clock(),
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    watchlists.insert().values(
                        watchlist_id=str(watchlist.watchlist_id),
                        normalized_name=watchlist.normalized_name,
                        display_name=watchlist.display_name,
                        created_at=_utc(watchlist.created_at),
                        updated_at=None,
                    )
                )
        except IntegrityError as exc:
            raise WatchlistConflictError(f"A watchlist named {spec.display_name!r} already exists.") from exc
        return watchlist

    def get(self, name: str) -> Watchlist | None:
        """Return the watchlist matching ``name`` case-insensitively, or None."""
        normalized = _normalize_name(name)
        with self._database.read() as connection:
            watchlist_id = connection.execute(
                select(watchlists.c.watchlist_id).where(watchlists.c.normalized_name == normalized)
            ).scalar_one_or_none()
            if watchlist_id is None:
                return None
            return self._load(connection, watchlist_id)

    def list(self) -> tuple[WatchlistSummary, ...]:
        """Return every watchlist as a summary, ordered by creation then ID."""
        with self._database.read() as connection:
            rows = (
                connection.execute(select(watchlists).order_by(watchlists.c.created_at, watchlists.c.watchlist_id))
                .mappings()
                .all()
            )
            summaries = [
                WatchlistSummary(
                    watchlist_id=UUID(row["watchlist_id"]),
                    display_name=row["display_name"],
                    entry_count=connection.execute(
                        select(func.count())
                        .select_from(watchlist_entries)
                        .where(watchlist_entries.c.watchlist_id == row["watchlist_id"])
                    ).scalar_one(),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=None if row["updated_at"] is None else datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]
        return tuple(summaries)

    def add_entries(self, name: str, entries: Sequence[tuple[str, AnalysisSelection]]) -> Watchlist:
        """Append one entry per (ticker, selection) pair, after the current highest position.

        Tickers are normalized; the whole batch is validated before any row
        is written, and applied in one transaction. An empty ``entries`` is a
        no-op that still returns the current watchlist.

        Raises:
            ValueError: If any ticker normalizes to empty.
            WatchlistNotFoundError: If no watchlist matches ``name``.
        """
        normalized_entries = [(normalize_ticker(ticker), selection) for ticker, selection in entries]
        with self._database.transaction() as connection:
            watchlist_id = self._find_id(connection, name)
            if normalized_entries:
                next_position = self._next_position(connection, watchlist_id)
                rows: list[dict[str, Any]] = [
                    {
                        "watchlist_id": watchlist_id,
                        "position": next_position + offset,
                        "ticker": ticker,
                        "method_id": selection.method_id,
                        "config_schema_version": selection.config_schema_version,
                        "selection_json": encode_selection(selection),
                    }
                    for offset, (ticker, selection) in enumerate(normalized_entries)
                ]
                connection.execute(watchlist_entries.insert(), rows)
                self._touch(connection, watchlist_id)
            return self._load(connection, watchlist_id)

    def remove_entry(self, name: str, position: int) -> Watchlist:
        """Remove exactly one entry by its stored 0-based position, renumbering survivors.

        Raises:
            WatchlistNotFoundError: If no watchlist matches ``name``.
            WatchlistEntryNotFoundError: If no entry exists at ``position``.
        """
        with self._database.transaction() as connection:
            watchlist_id = self._find_id(connection, name)
            rows = self._entry_rows(connection, watchlist_id)
            survivors = [row for row in rows if row["position"] != position]
            if len(survivors) == len(rows):
                raise WatchlistEntryNotFoundError(f"No entry at position {position} in watchlist {name!r}.")
            self._replace_entries(connection, watchlist_id, survivors)
            self._touch(connection, watchlist_id)
            return self._load(connection, watchlist_id)

    def remove_entries_for_ticker(self, name: str, tickers: Sequence[str]) -> Watchlist:
        """Remove every entry for the given ticker(s); absent tickers are a no-op.

        Raises:
            ValueError: If any ticker normalizes to empty.
            WatchlistNotFoundError: If no watchlist matches ``name``.
        """
        normalized_tickers = {normalize_ticker(ticker) for ticker in tickers}
        with self._database.transaction() as connection:
            watchlist_id = self._find_id(connection, name)
            if normalized_tickers:
                rows = self._entry_rows(connection, watchlist_id)
                survivors = [row for row in rows if row["ticker"] not in normalized_tickers]
                if len(survivors) != len(rows):
                    self._replace_entries(connection, watchlist_id, survivors)
                    self._touch(connection, watchlist_id)
            return self._load(connection, watchlist_id)

    def remove_entries_for_method(self, name: str, method_id: str) -> Watchlist:
        """Remove every entry for ``method_id``; absent is a no-op.

        Raises:
            WatchlistNotFoundError: If no watchlist matches ``name``.
        """
        with self._database.transaction() as connection:
            watchlist_id = self._find_id(connection, name)
            rows = self._entry_rows(connection, watchlist_id)
            survivors = [row for row in rows if row["method_id"] != method_id]
            if len(survivors) != len(rows):
                self._replace_entries(connection, watchlist_id, survivors)
                self._touch(connection, watchlist_id)
            return self._load(connection, watchlist_id)

    def _touch(self, connection: Connection, watchlist_id: str) -> None:
        """Bump ``updated_at`` to the injected clock's current instant."""
        connection.execute(
            update(watchlists).where(watchlists.c.watchlist_id == watchlist_id).values(updated_at=_utc(self._clock()))
        )

    def _find_id(self, connection: Connection, name: str) -> str:
        """Resolve a name to its watchlist ID, or raise if none matches."""
        watchlist_id = connection.execute(
            select(watchlists.c.watchlist_id).where(watchlists.c.normalized_name == _normalize_name(name))
        ).scalar_one_or_none()
        if watchlist_id is None:
            raise WatchlistNotFoundError(f"No watchlist named {name!r} exists.")
        return cast(str, watchlist_id)

    @staticmethod
    def _next_position(connection: Connection, watchlist_id: str) -> int:
        """Return one past the current highest entry position, or zero if empty."""
        highest = connection.execute(
            select(func.max(watchlist_entries.c.position)).where(watchlist_entries.c.watchlist_id == watchlist_id)
        ).scalar_one()
        return 0 if highest is None else cast(int, highest) + 1

    @staticmethod
    def _entry_rows(connection: Connection, watchlist_id: str) -> Sequence[RowMapping]:
        """Return every entry row for this watchlist, in position order."""
        return (
            connection.execute(
                select(watchlist_entries)
                .where(watchlist_entries.c.watchlist_id == watchlist_id)
                .order_by(watchlist_entries.c.position)
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _replace_entries(connection: Connection, watchlist_id: str, survivors: Sequence[RowMapping]) -> None:
        """Rewrite a watchlist's entries from ``survivors``, renumbered contiguously from zero.

        Deleting everything and reinserting the survivors (rather than
        shifting positions in place) keeps this correct regardless of which
        positions were removed, with no risk of a transient primary-key
        collision mid-update.
        """
        connection.execute(delete(watchlist_entries).where(watchlist_entries.c.watchlist_id == watchlist_id))
        if survivors:
            connection.execute(
                watchlist_entries.insert(),
                [
                    {
                        "watchlist_id": watchlist_id,
                        "position": position,
                        "ticker": row["ticker"],
                        "method_id": row["method_id"],
                        "config_schema_version": row["config_schema_version"],
                        "selection_json": row["selection_json"],
                    }
                    for position, row in enumerate(survivors)
                ],
            )

    def _load(self, connection: Connection, watchlist_id: str) -> Watchlist:
        """Reconstruct one full watchlist from its two tables in position order."""
        row = connection.execute(select(watchlists).where(watchlists.c.watchlist_id == watchlist_id)).mappings().one()
        entry_rows = self._entry_rows(connection, watchlist_id)
        entries = tuple(
            WatchlistEntry(
                ticker=entry_row["ticker"],
                selection=decode_selection(
                    entry_row["method_id"], entry_row["config_schema_version"], entry_row["selection_json"]
                ),
            )
            for entry_row in entry_rows
        )
        return Watchlist(
            watchlist_id=UUID(row["watchlist_id"]),
            display_name=row["display_name"],
            normalized_name=row["normalized_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=None if row["updated_at"] is None else datetime.fromisoformat(row["updated_at"]),
            entries=entries,
        )


__all__ = [
    "SQLiteWatchlistRepository",
    "WatchlistConflictError",
    "WatchlistEntryNotFoundError",
    "WatchlistNotFoundError",
]
