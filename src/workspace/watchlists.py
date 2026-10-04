"""Watchlist creation input and selection JSON codec for persistence.

This module owns only pure typed helpers used by the SQLite watchlist
repository: the minimal creation request, ticker normalization, and the
selection JSON encode/decode pair. It performs no SQL, no provider work, and
no analysis; the `Watchlist`/`WatchlistSummary` aggregate types themselves
live in :mod:`src.workspace.runs`.
"""

import json

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from src.workspace.strategy_types import AnalysisSelection

_SELECTION_ADAPTER: TypeAdapter[AnalysisSelection] = TypeAdapter(AnalysisSelection)


class StoredSelectionError(ValueError):
    """A stored watchlist selection cannot be read by this version of the application.

    The message is a self-contained clause describing the entry's state (for example
    "saved by an earlier version (selection version 1) and can no longer be read"); a caller
    that knows which entry it was decoding adds the watchlist, position and remedy.
    """


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
    "WatchlistSpec",
    "decode_selection",
    "encode_selection",
    "normalize_ticker",
]
