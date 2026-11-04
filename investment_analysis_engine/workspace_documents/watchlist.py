"""The watchlist documents: ``watchlist list``, ``show``, ``rename`` and ``delete`` with ``--json``.

Only the watchlist list document carries a ``schema_version``; the others are unversioned. A change to a key, a type
or a timestamp spelling is a listed output change in the slice that makes it, and the generated schema shows it.
"""

from collections.abc import Sequence
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_validator,
)

from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp, document_json_value
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistSummary
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection, SelectionMember


class WatchlistEntryDocument(BaseModel):
    """One entry of a watchlist: its 1-based position, its ticker and the selection stored for it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(description="The 1-based position a user sees and passes to 'remove-entry'.")
    ticker: str
    selection: AnalysisSelection = Field(
        description="The stored selection; its method_id says which strategy. Its instants (as_of) carry a UTC offset."
    )

    @field_serializer("selection", mode="wrap", when_used="json")
    def _serialize_selection(self, value: SelectionMember, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]  # noqa: ANN202
        """Write the selection's instants as every other document does, leaving the selection model unchanged.

        The return type is left unannotated so the generated schema keeps the selection union; the value is the
        selection's JSON data, a dictionary.
        """
        del handler
        return document_json_value(value)


class WatchlistDocument(BaseModel):
    """The complete watchlist, as ``watchlist show`` and ``watchlist rename`` write it with ``--json``.

    This document is unversioned: it has no ``schema_version``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    watchlist_id: UUID
    display_name: str
    created_at: DocumentTimestamp
    updated_at: DocumentTimestamp | None = Field(description="Null until the watchlist is first changed.")
    entries: tuple[WatchlistEntryDocument, ...]


class WatchlistDeleteDocument(BaseModel):
    """The outcome of ``watchlist delete --json``, with the watchlist it removed when there was one.

    ``deleted`` is false, and ``watchlist`` null, only for ``--missing-ok`` on a name that does not exist.
    This document is unversioned: it has no ``schema_version``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_name: str
    deleted: bool
    watchlist: WatchlistDocument | None = Field(description="The deleted watchlist; null when nothing was deleted.")

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require ``watchlist`` to be set if and only if something was deleted."""
        if self.deleted != (self.watchlist is not None):
            raise ValueError("watchlist is set if and only if deleted is true.")
        return self


class WatchlistSummaryDocument(BaseModel):
    """One watchlist, summarized: its identity, name, entry count and timestamps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    watchlist_id: UUID
    display_name: str
    entry_count: int
    created_at: DocumentTimestamp
    updated_at: DocumentTimestamp | None = Field(description="Null until the watchlist is first changed.")


class WatchlistListDocument(BaseModel):
    """The whole ``watchlist list --json`` output: every watchlist's summary, in the order listed. It is not paged."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    items: tuple[WatchlistSummaryDocument, ...]


def build_watchlist_document(watchlist: Watchlist) -> WatchlistDocument:
    """Build the watchlist document: the flat, ordered entry list, each carrying the 1-based index a user sees."""
    return WatchlistDocument(
        watchlist_id=watchlist.watchlist_id,
        display_name=watchlist.display_name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        entries=tuple(
            WatchlistEntryDocument(index=index, ticker=entry.ticker, selection=entry.selection)
            for index, entry in enumerate(watchlist.entries, start=1)
        ),
    )


def build_watchlist_list_document(summaries: Sequence[WatchlistSummary]) -> WatchlistListDocument:
    """Build the watchlist-list document from watchlist summaries, keeping their order."""
    return WatchlistListDocument(
        items=tuple(
            WatchlistSummaryDocument(
                watchlist_id=item.watchlist_id,
                display_name=item.display_name,
                entry_count=item.entry_count,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in summaries
        )
    )


__all__ = [
    "WatchlistDeleteDocument",
    "WatchlistDocument",
    "WatchlistEntryDocument",
    "WatchlistListDocument",
    "WatchlistSummaryDocument",
    "build_watchlist_document",
    "build_watchlist_list_document",
]
