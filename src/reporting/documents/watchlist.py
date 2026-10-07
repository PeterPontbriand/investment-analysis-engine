"""The watchlist documents: ``watchlist show``, ``watchlist rename`` and ``watchlist delete`` with ``--json``.

Neither document carries a ``schema_version``: they are unversioned. A change to a key, a type or a
timestamp spelling is a listed output change in the slice that makes it, and the generated schema shows it.
"""

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, field_serializer, model_validator

from src.reporting.documents.timestamp import DocumentTimestamp, document_json_value
from src.workspace.strategy_types import AnalysisSelection, SelectionMember


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


__all__ = ["WatchlistDeleteDocument", "WatchlistDocument", "WatchlistEntryDocument"]
