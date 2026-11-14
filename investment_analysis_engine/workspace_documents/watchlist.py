"""The watchlist documents: the ``watchlist`` commands that write ``--json``, and the API's action endpoints.

Every document carries a ``schema_version``, except the entry and summary documents nested inside them. A change to a
key, a type or a timestamp spelling is a listed output change in the slice that makes it, and the generated schema
shows it. The rename, removal and delete result documents hold exactly one of ``watchlist`` and ``unreadable``: an
action that committed its change reports an entry this version cannot read in ``unreadable`` instead of the watchlist.
"""

from collections.abc import Sequence
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp, document_json_value
from investment_analysis_engine.workspace.repositories.watchlists import (
    DeletedWatchlist,
    RemovedEntries,
    RenamedWatchlist,
)
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistSummary
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection, SelectionMember
from investment_analysis_engine.workspace.watchlists import StoredSelectionError


class WatchlistEntryDocument(BaseModel):
    """One entry of a watchlist: its 1-based position, its ticker and the selection stored for it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(description="The 1-based position a user sees and passes to 'remove-entry'.")
    ticker: str
    selection: AnalysisSelection = Field(
        description=(
            "The stored selection; its method_id says which strategy. Its as_of is a date when a date was given, "
            "else an instant with its UTC offset."
        )
    )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Describe each selection's ``as_of`` as the date or the instant the document serves.

        The selection models are stored shapes and keep their own schema; the document spells ``as_of`` with
        :func:`~investment_analysis_engine.reporting.documents.timestamp.as_of_text`, so its schema says so.
        """
        schema = handler(core_schema)
        selection = handler.resolve_ref_schema(schema)["properties"]["selection"]
        for option in selection["oneOf"]:
            as_of = handler.resolve_ref_schema(option)["properties"]["as_of"]
            as_of["anyOf"] = [
                {"anyOf": [{"type": "string", "format": "date"}, {"type": "string", "format": "date-time"}]}
                if item.get("format") == "date-time"
                else item
                for item in as_of["anyOf"]
            ]
        return schema

    @field_serializer("selection", mode="wrap", when_used="json")
    def _serialize_selection(self, value: SelectionMember, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]  # noqa: ANN202
        """Write the selection's instants as every other document does, leaving the selection model unchanged.

        The return type is left unannotated so the generated schema keeps the selection union; the value is the
        selection's JSON data, a dictionary.
        """
        del handler
        return document_json_value(value)


class WatchlistDocument(BaseModel):
    """The complete watchlist, as every command that writes one with ``--json`` prints it.

    These are ``watchlist show``, ``create`` and ``add-selection``; the API serves it for a watchlist, for a created
    watchlist and for an added entry, and the result documents below nest it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    watchlist_id: UUID
    display_name: str
    created_at: DocumentTimestamp
    updated_at: DocumentTimestamp | None = Field(description="Null until the watchlist is first changed.")
    entries: tuple[WatchlistEntryDocument, ...]


class UnreadableEntryDocument(BaseModel):
    """The first entry of a watchlist that this version cannot read, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_number: int = Field(description="The 1-based position of the entry.")
    ticker: str
    method_id: str = Field(description="The method identifier as stored; this version may no longer declare it.")
    reason: str = Field(description="The state of the entry, in words for a person. It names no command.")


def _exactly_one(watchlist: object | None, unreadable: object | None) -> None:
    """Require exactly one of a result document's ``watchlist`` and ``unreadable``."""
    if (watchlist is None) == (unreadable is None):
        raise ValueError("exactly one of watchlist and unreadable is set.")


class WatchlistRenameDocument(BaseModel):
    """The outcome of ``watchlist rename --json``: the renamed watchlist, or the entry that could not be read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    watchlist: WatchlistDocument | None = Field(description="The renamed watchlist; null when an entry is unreadable.")
    unreadable: UnreadableEntryDocument | None = Field(
        description="The first entry this version cannot read; the rename is committed either way."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require exactly one of ``watchlist`` and ``unreadable``."""
        _exactly_one(self.watchlist, self.unreadable)
        return self


class WatchlistRemovalDocument(BaseModel):
    """The outcome of ``remove-entry``, ``remove-ticker`` and ``remove-method`` with ``--json``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    removed: int = Field(description="The number of entries removed; 0 when nothing matched.")
    watchlist: WatchlistDocument | None = Field(
        description="The watchlist read back; null when an entry is unreadable."
    )
    unreadable: UnreadableEntryDocument | None = Field(
        description="The first remaining entry this version cannot read; the removal is committed either way."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require exactly one of ``watchlist`` and ``unreadable``."""
        _exactly_one(self.watchlist, self.unreadable)
        return self


class WatchlistDeleteDocument(BaseModel):
    """The outcome of ``watchlist delete --json``, with the watchlist it removed when there was one.

    ``deleted`` is false, and ``watchlist`` and ``unreadable`` both null, only for ``--missing-ok`` on a name that does
    not exist. Otherwise exactly one of ``watchlist`` and ``unreadable`` is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    deleted: bool
    watchlist: WatchlistDocument | None = Field(
        description="The deleted watchlist; null when an entry was unreadable or nothing was deleted."
    )
    unreadable: UnreadableEntryDocument | None = Field(
        description="The first entry this version could not read; null when nothing was deleted."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require both to be null when nothing was deleted, and exactly one to be set otherwise."""
        if self.deleted:
            _exactly_one(self.watchlist, self.unreadable)
        elif self.watchlist is not None or self.unreadable is not None:
            raise ValueError("watchlist and unreadable are null when nothing was deleted.")
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


def build_unreadable_entry_document(error: StoredSelectionError) -> UnreadableEntryDocument:
    """Build the document of an unreadable entry from the repository's error, which names the entry."""
    if error.entry_number is None or error.ticker is None or error.method_id is None:
        raise ValueError("An unreadable entry document needs an error that names its entry.")
    return UnreadableEntryDocument(
        entry_number=error.entry_number, ticker=error.ticker, method_id=error.method_id, reason=str(error)
    )


def _read_back(
    watchlist: Watchlist | None, unreadable: StoredSelectionError | None
) -> tuple[WatchlistDocument | None, UnreadableEntryDocument | None]:
    """Return the documents of a write's read-back: the watchlist, or the entry that could not be read."""
    return (
        None if watchlist is None else build_watchlist_document(watchlist),
        None if unreadable is None else build_unreadable_entry_document(unreadable),
    )


def build_rename_document(renamed: RenamedWatchlist) -> WatchlistRenameDocument:
    """Build the rename result document."""
    watchlist, unreadable = _read_back(renamed.watchlist, renamed.unreadable)
    return WatchlistRenameDocument(watchlist=watchlist, unreadable=unreadable)


def build_removal_document(removed: RemovedEntries) -> WatchlistRemovalDocument:
    """Build the removal result document."""
    watchlist, unreadable = _read_back(removed.watchlist, removed.unreadable)
    return WatchlistRemovalDocument(removed=removed.removed, watchlist=watchlist, unreadable=unreadable)


def build_delete_document(deleted: DeletedWatchlist | None) -> WatchlistDeleteDocument:
    """Build the delete result document; ``None`` is the missing watchlist of ``--missing-ok``."""
    if deleted is None:
        return WatchlistDeleteDocument(deleted=False, watchlist=None, unreadable=None)
    watchlist, unreadable = _read_back(deleted.watchlist, deleted.unreadable)
    return WatchlistDeleteDocument(deleted=True, watchlist=watchlist, unreadable=unreadable)


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
    "UnreadableEntryDocument",
    "WatchlistDeleteDocument",
    "WatchlistDocument",
    "WatchlistEntryDocument",
    "WatchlistListDocument",
    "WatchlistRemovalDocument",
    "WatchlistRenameDocument",
    "WatchlistSummaryDocument",
    "build_delete_document",
    "build_removal_document",
    "build_rename_document",
    "build_unreadable_entry_document",
    "build_watchlist_document",
    "build_watchlist_list_document",
]
