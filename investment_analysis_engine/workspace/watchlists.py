"""Watchlist creation input and selection JSON codec for persistence.

This module owns only pure typed helpers used by the SQLite watchlist
repository: the minimal creation request, ticker normalization, and the
selection JSON encode/decode pair. It performs no SQL, no provider work, and
no analysis; the `Watchlist`/`WatchlistSummary` aggregate types themselves
live in :mod:`investment_analysis_engine.workspace.runs`.
"""

import json
from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection

_SELECTION_ADAPTER: TypeAdapter[AnalysisSelection] = TypeAdapter(AnalysisSelection)


class StoredSelectionError(ValueError):
    """A stored watchlist selection cannot be read by this version of the application.

    A decoder raises it with a self-contained clause describing the entry's state (for example
    "saved by an earlier version (selection version 1) and can no longer be read"), before it
    knows which entry it was decoding. The repository, which does know, raises it again naming the
    entry: the message is then ``Watchlist 'Core', entry 2 (MSFT, momentum): <clause>.`` and the
    watchlist name, the 1-based entry number, the ticker, the method name and the stored method identifier are fields.
    The message never names a command that removes the entry; a caller that offers one builds it from the fields.
    """

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.STORED_SELECTION_UNREADABLE

    def __init__(  # noqa: PLR0913
        self,
        clause: str,
        *,
        watchlist_name: str | None = None,
        entry_number: int | None = None,
        ticker: str | None = None,
        method: str | None = None,
        method_id: str | None = None,
    ) -> None:
        """Keep the clause, or name the entry when all five of its fields are given."""
        named = (watchlist_name, entry_number, ticker, method, method_id)
        if any(field is not None for field in named) and any(field is None for field in named):
            raise ValueError("StoredSelectionError names an entry by all of its five fields or by none.")
        if watchlist_name is None:
            message = clause
        else:
            message = f"Watchlist {watchlist_name!r}, entry {entry_number} ({ticker}, {method}): {clause}."
        super().__init__(message)
        self.watchlist_name = watchlist_name
        self.entry_number = entry_number
        self.ticker = ticker
        self.method = method
        self.method_id = method_id


class WatchlistNotFoundError(ValueError):
    """No watchlist exists with the requested name."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.WATCHLIST_NOT_FOUND


@dataclass(frozen=True)
class WatchlistName:
    """A watchlist addressed by its name, compared after trimming and case folding."""

    name: str


@dataclass(frozen=True)
class WatchlistId:
    """A watchlist addressed by its permanent ID."""

    watchlist_id: UUID


type WatchlistRef = WatchlistName | WatchlistId
"""How an operation addresses one watchlist: by name or by ID."""


def not_found_message(ref: WatchlistRef) -> str:
    """Return the message that reports no watchlist matches ``ref``."""
    if isinstance(ref, WatchlistName):
        return f"No watchlist named {ref.name!r} exists."
    return f"No watchlist with ID {ref.watchlist_id} exists."


class WatchlistSpec(BaseModel):
    """Creation input for a new watchlist: a display name, nothing else.

    Creation always starts with no entries (Amendment A1, §12): there is no
    default selection materialized for a new watchlist. Seeding a freshly
    created watchlist with entries is the caller's own, separate concern.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    display_name: str


def normalize_ticker(value: str) -> str:
    """Normalize a member ticker using the existing uppercase/trim convention.

    Args:
        value: A raw ticker, possibly carrying a venue suffix.

    Returns:
        The trimmed, uppercased ticker with any venue suffix preserved.

    Raises:
        ValueError: If the normalized ticker is empty.
    """
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty.")
    return normalized


def encode_selection(selection: AnalysisSelection) -> str:
    """Encode one selection as canonical, sorted, finite JSON text."""
    return json.dumps(
        selection.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def decode_selection(method_id: str, config_schema_version: int, selection_json: str) -> AnalysisSelection:
    """Decode stored selection JSON and confirm it matches its identity columns.

    Args:
        method_id: The stored row's method identifier column.
        config_schema_version: The stored row's configuration version column.
        selection_json: The stored canonical JSON text for the selection.

    Returns:
        The validated selection with canonical identifiers restored.

    Raises:
        StoredSelectionError: If the JSON is malformed, is not a selection this
            version supports (for example a retired configuration version), or
            its identity does not match the row's own method/version columns.
            The message is a single readable line.
    """
    try:
        selection = _SELECTION_ADAPTER.validate_json(selection_json)
    except ValidationError as exc:
        first = exc.errors()[0]
        if first["type"] == "json_invalid":
            raise StoredSelectionError("its stored selection is not valid JSON") from exc
        if first["loc"] and first["loc"][-1] == "config_schema_version":
            raise StoredSelectionError(
                f"saved by an earlier version (selection version {config_schema_version}) and can no longer be read"
            ) from exc
        raise StoredSelectionError("its stored selection is not in a shape this version can read") from exc
    if selection.method_id != method_id or selection.config_schema_version != config_schema_version:
        raise StoredSelectionError("its stored selection does not match its method/version columns")
    return selection


__all__ = [
    "StoredSelectionError",
    "WatchlistId",
    "WatchlistName",
    "WatchlistNotFoundError",
    "WatchlistRef",
    "WatchlistSpec",
    "decode_selection",
    "encode_selection",
    "normalize_ticker",
    "not_found_message",
]
