"""Watchlist creation input and selection JSON codec for persistence.

This module owns only pure typed helpers used by the SQLite watchlist
repository: the minimal creation request, ticker normalization, and the
selection JSON encode/decode pair. It performs no SQL, no provider work, and
no analysis; the `Watchlist`/`WatchlistSummary` aggregate types themselves
live in :mod:`src.workspace.runs`.
"""

import json

from pydantic import BaseModel, ConfigDict, TypeAdapter

from src.workspace.requests import AnalysisSelection

_SELECTION_ADAPTER: TypeAdapter[AnalysisSelection] = TypeAdapter(AnalysisSelection)


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
        ValueError: If the JSON is malformed or its identity does not match
            the row's own method/version columns.
    """
    selection = _SELECTION_ADAPTER.validate_json(selection_json)
    if selection.method_id != method_id or selection.config_schema_version != config_schema_version:
        raise ValueError("Stored selection identity does not match its method/version columns.")
    return selection


__all__ = [
    "WatchlistSpec",
    "decode_selection",
    "encode_selection",
    "normalize_ticker",
]
