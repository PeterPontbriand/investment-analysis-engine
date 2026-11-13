"""The typed workspace documents: shape, timestamp spelling, versioning statement and builder behavior."""

import json
import types
import typing
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any, get_args, get_origin
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.types import AwareDatetime, FutureDatetime, NaiveDatetime, PastDatetime

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.provider_check import ProviderCheckFindings
from investment_analysis_engine.application.refresh import build_refresh_document
from investment_analysis_engine.cli_support import document_json, watchlist_json
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.refresh import RefreshJobResult, RefreshSummary
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistEntry
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection, SelectionMember
from investment_analysis_engine.workspace.watchlists import StoredSelectionError
from investment_analysis_engine.workspace_documents.refresh import RefreshResultDocument, RefreshSummaryDocument
from investment_analysis_engine.workspace_documents.runs import RunsListDocument, RunSummaryDocument
from investment_analysis_engine.workspace_documents.watchlist import (
    UnreadableEntryDocument,
    WatchlistDeleteDocument,
    WatchlistDocument,
    WatchlistRemovalDocument,
    WatchlistRenameDocument,
    build_unreadable_entry_document,
)
from scripts.generate_schemas import DOCUMENTS, expected_schemas

_DATETIME_LEAVES: tuple[Any, ...] = (datetime, AwareDatetime, NaiveDatetime, PastDatetime, FutureDatetime)
_TIMESTAMP_METADATA: tuple[Any, ...] = get_args(DocumentTimestamp)[1:]
_SELECTION_MEMBERS: tuple[Any, ...] = get_args(SelectionMember)
_VERSIONED_WATCHLIST_FILES = (
    "watchlist-delete.schema.json",
    "watchlist-removal.schema.json",
    "watchlist-rename.schema.json",
    "watchlist.schema.json",
)


def _untyped_datetime_fields(model: type[BaseModel], seen: set[type[BaseModel]]) -> list[str]:
    """Return ``Model.field`` for every datetime field below ``model`` that does not use ``DocumentTimestamp``.

    A selection member is a stored selection owned by its strategy, not a document model, so the walk stops there; the
    document's selection field spells their instants itself, and the emitted-output tests below check that.
    """
    if model in seen or model in _SELECTION_MEMBERS:
        return []
    seen.add(model)
    problems: list[str] = []
    for name, field in model.model_fields.items():
        stack: list[tuple[Any, tuple[Any, ...]]] = [(field.annotation, tuple(field.metadata))]
        while stack:
            node, metadata = stack.pop()
            if get_origin(node) is Annotated:
                inner, *extra = get_args(node)
                stack.append((inner, metadata + tuple(extra)))
            elif isinstance(node, type) and issubclass(node, BaseModel):
                problems.extend(_untyped_datetime_fields(node, seen))
            elif node in _DATETIME_LEAVES:
                if not all(item in metadata for item in _TIMESTAMP_METADATA):
                    problems.append(f"{model.__name__}.{name}")
            elif get_origin(node) in (typing.Union, types.UnionType) or get_args(node):
                stack.extend((argument, metadata) for argument in get_args(node))
    return problems


@pytest.mark.parametrize(("file_name", "model"), list(DOCUMENTS), ids=[name for name, _model in DOCUMENTS])
def test_every_document_model_declares_its_datetime_fields_as_document_timestamps(
    file_name: str, model: type[BaseModel]
) -> None:
    """A plain datetime field would emit pydantic's ``Z`` spelling; a failure names the model and field."""
    assert _untyped_datetime_fields(model, set()) == [], file_name


def test_the_timestamp_check_names_a_model_and_field_that_use_a_plain_datetime() -> None:
    """Negative control: the check fails for a datetime field declared without the shared type."""

    class Leaky(BaseModel):
        seen_at: AwareDatetime
        stamped_at: DocumentTimestamp
        maybe_at: DocumentTimestamp | None = None
        loose_at: datetime | None = None

    assert sorted(_untyped_datetime_fields(Leaky, set())) == ["Leaky.loose_at", "Leaky.seen_at"]


def test_a_timestamp_keeps_the_offset_it_carries() -> None:
    class Holder(BaseModel):
        at: DocumentTimestamp

    utc = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    east = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert Holder(at=utc).model_dump(mode="json")["at"] == "2026-01-02T03:04:05.123456+00:00"
    assert Holder(at=east).model_dump(mode="json")["at"] == "2026-01-02T03:04:05+05:30"
    assert Holder(at=utc).model_dump()["at"] == utc
    with pytest.raises(ValidationError):
        Holder(at=datetime(2026, 1, 2))  # noqa: DTZ001 - a naive instant is exactly what must be rejected


@pytest.mark.parametrize("file_name", _VERSIONED_WATCHLIST_FILES)
def test_each_watchlist_schema_is_version_one(file_name: str) -> None:
    schema = json.loads(expected_schemas()[file_name])
    assert "unversioned" not in schema["description"]
    assert schema["properties"]["schema_version"]["const"] == 1
    assert "schema_version" not in schema.get("required", [])


def test_the_runs_list_schema_is_version_two_with_a_paging_flag_and_items() -> None:
    schema = json.loads(expected_schemas()["runs-list.schema.json"])
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == 2
    assert list(RunsListDocument.model_fields) == ["schema_version", "has_more", "items"]
    assert schema["required"] == ["has_more", "items"]
    assert "unversioned" not in schema["description"]


def test_the_refresh_summary_schema_is_version_three_and_its_watchlist_is_nullable() -> None:
    schema = json.loads(expected_schemas()["refresh-summary.schema.json"])
    assert schema["properties"]["schema_version"]["const"] == 3
    assert {"type": "null"} in schema["properties"]["watchlist_id"]["anyOf"]
    assert {"type": "null"} in schema["properties"]["watchlist_name"]["anyOf"]
    assert "unversioned" not in schema["description"]


def test_the_refresh_summary_reuses_the_failure_envelopes_reason_codes() -> None:
    schema = json.loads(expected_schemas()["refresh-summary.schema.json"])
    assert schema["$defs"]["FailureReasonCode"]["enum"] == [item.value for item in FailureReasonCode]
    assert RefreshResultDocument.model_fields["reason_code"].annotation == FailureReasonCode | None


def test_the_watchlist_selection_is_the_analysis_selection_union() -> None:
    schema = json.loads(expected_schemas()["watchlist.schema.json"])
    selection = schema["$defs"]["WatchlistEntryDocument"]["properties"]["selection"]
    assert "oneOf" in selection, (
        "the entry selection lost its oneOf over the selection models: the selection serializer in "
        "investment_analysis_engine/workspace_documents/watchlist.py must stay unannotated, "
        "because any return annotation "
        "makes pydantic drop the union from the generated schema"
    )
    members = {reference["$ref"].rsplit("/", 1)[1] for reference in selection["oneOf"]}
    assert members == {member.__name__ for member in _SELECTION_MEMBERS}
    assert selection["discriminator"]["propertyName"] == "method_id"


def _watchlist(*, updated_at: datetime | None) -> Watchlist:
    selections: tuple[SelectionMember, ...] = (
        MomentumSelection(short_window=2, long_window=3, rsi_period=3),
        GrahamNumberSelection(),
        GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5),
        FCFGrowthSelection(as_of=datetime(2026, 1, 2, tzinfo=UTC)),
    )
    return Watchlist(
        watchlist_id=uuid4(),
        display_name="Core",
        normalized_name="core",
        created_at=datetime(2026, 3, 4, 5, 6, 7, 8, tzinfo=UTC),
        updated_at=updated_at,
        entries=tuple(WatchlistEntry(ticker=f"T{index}", selection=item) for index, item in enumerate(selections)),
    )


def _selection_datetime_fields() -> set[str]:
    """Return ``Model.field`` for every datetime field of a selection member, nested models included."""
    found: set[str] = set()
    seen: set[type[BaseModel]] = set()

    def visit(model: type[BaseModel]) -> None:
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            stack: list[Any] = [field.annotation]
            while stack:
                node = stack.pop()
                if get_origin(node) is Annotated:
                    stack.append(get_args(node)[0])
                elif isinstance(node, type) and issubclass(node, BaseModel):
                    visit(node)
                elif node in _DATETIME_LEAVES:
                    found.add(f"{model.__name__}.{name}")
                else:
                    stack.extend(get_args(node))

    for member in _SELECTION_MEMBERS:
        visit(member)
    return found


def test_as_of_is_the_only_instant_in_any_selection_model() -> None:
    """The document re-spells every instant of a selection; a new one must be reviewed with the document."""
    assert _selection_datetime_fields() == {f"{member.__name__}.as_of" for member in _SELECTION_MEMBERS}


def _document_selections(watchlist: Watchlist) -> list[dict[str, Any]]:
    document = json.loads(watchlist_json(watchlist))
    selections: list[dict[str, Any]] = [entry["selection"] for entry in document["entries"]]
    return selections


def test_the_watchlist_document_matches_what_the_hand_built_dictionary_wrote() -> None:
    """Apart from the spelling of ``as_of``, each selection is its own ``model_dump``; a non-UTC offset is kept."""
    watchlist = _watchlist(updated_at=datetime(2026, 3, 5, tzinfo=timezone(timedelta(hours=-4))))
    expected_selections = []
    for entry in watchlist.entries:
        dumped = entry.selection.model_dump(mode="json")
        assert dumped["as_of"] is None or dumped["as_of"].endswith("Z")  # the selection model itself is unchanged
        if dumped["as_of"] is not None:
            dumped["as_of"] = entry.selection.as_of.isoformat()  # type: ignore[union-attr]
        expected_selections.append(dumped)
    expected = {
        "schema_version": 1,
        "watchlist_id": str(watchlist.watchlist_id),
        "display_name": "Core",
        "created_at": watchlist.created_at.isoformat(),
        "updated_at": "2026-03-05T00:00:00-04:00",
        "entries": [
            {"index": index, "ticker": entry.ticker, "selection": selection}
            for index, (entry, selection) in enumerate(
                zip(watchlist.entries, expected_selections, strict=True), start=1
            )
        ],
    }
    assert watchlist_json(watchlist) == json.dumps(expected, ensure_ascii=False, allow_nan=False)


@pytest.mark.parametrize("offset", [UTC, timezone(timedelta(hours=5, minutes=30))])
def test_a_selection_instant_is_written_with_its_offset_and_parses_back_to_the_same_selection(offset: timezone) -> None:
    """The rule: every instant in a document, a selection's ``as_of`` included, is ``isoformat()`` text."""
    instant = datetime(2026, 8, 1, 23, 59, 59, 999999, tzinfo=offset)
    selections: tuple[SelectionMember, ...] = (
        MomentumSelection(short_window=2, long_window=3, rsi_period=3, as_of=instant),
        GrahamNumberSelection(as_of=instant),
        GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5, as_of=instant),
        FCFGrowthSelection(as_of=instant),
    )
    watchlist = Watchlist(
        watchlist_id=uuid4(),
        display_name="Core",
        normalized_name="core",
        created_at=datetime(2026, 3, 4, tzinfo=UTC),
        entries=tuple(WatchlistEntry(ticker="A", selection=item) for item in selections),
    )
    emitted = _document_selections(watchlist)
    assert [item["as_of"] for item in emitted] == [instant.isoformat()] * 4
    assert not any(str(item["as_of"]).endswith("Z") for item in emitted)
    adapter: TypeAdapter[SelectionMember] = TypeAdapter(AnalysisSelection)
    assert [adapter.validate_python(item) for item in emitted] == list(selections)


def test_an_absent_as_of_stays_null() -> None:
    emitted = {item["as_of"] for item in _document_selections(_watchlist(updated_at=None))}
    assert emitted == {None, "2026-01-02T00:00:00+00:00"}


def test_a_watchlist_never_changed_has_a_null_updated_at() -> None:
    assert json.loads(watchlist_json(_watchlist(updated_at=None)))["updated_at"] is None


def _unreadable() -> UnreadableEntryDocument:
    return UnreadableEntryDocument(entry_number=2, ticker="KO", method_id="old_method", reason="it cannot be read")


def test_the_delete_document_requires_exactly_one_result_unless_nothing_was_deleted() -> None:
    document = WatchlistDocument.model_validate(json.loads(watchlist_json(_watchlist(updated_at=None))))
    WatchlistDeleteDocument(deleted=True, watchlist=document, unreadable=None)
    WatchlistDeleteDocument(deleted=True, watchlist=None, unreadable=_unreadable())
    WatchlistDeleteDocument(deleted=False, watchlist=None, unreadable=None)
    with pytest.raises(ValidationError, match="exactly one of watchlist and unreadable"):
        WatchlistDeleteDocument(deleted=True, watchlist=None, unreadable=None)
    with pytest.raises(ValidationError, match="exactly one of watchlist and unreadable"):
        WatchlistDeleteDocument(deleted=True, watchlist=document, unreadable=_unreadable())
    with pytest.raises(ValidationError, match="null when nothing was deleted"):
        WatchlistDeleteDocument(deleted=False, watchlist=document, unreadable=None)
    with pytest.raises(ValidationError, match="null when nothing was deleted"):
        WatchlistDeleteDocument(deleted=False, watchlist=None, unreadable=_unreadable())


def test_the_rename_and_removal_documents_require_exactly_one_of_the_watchlist_and_the_unreadable_entry() -> None:
    document = WatchlistDocument.model_validate(json.loads(watchlist_json(_watchlist(updated_at=None))))
    WatchlistRenameDocument(watchlist=document, unreadable=None)
    WatchlistRenameDocument(watchlist=None, unreadable=_unreadable())
    WatchlistRemovalDocument(removed=0, watchlist=document, unreadable=None)
    WatchlistRemovalDocument(removed=3, watchlist=None, unreadable=_unreadable())
    for neither_or_both in ((None, None), (document, _unreadable())):
        with pytest.raises(ValidationError, match="exactly one of watchlist and unreadable"):
            WatchlistRenameDocument(watchlist=neither_or_both[0], unreadable=neither_or_both[1])
        with pytest.raises(ValidationError, match="exactly one of watchlist and unreadable"):
            WatchlistRemovalDocument(removed=1, watchlist=neither_or_both[0], unreadable=neither_or_both[1])


def test_every_watchlist_document_is_versioned() -> None:
    document = WatchlistDocument.model_validate(json.loads(watchlist_json(_watchlist(updated_at=None))))
    assert document.schema_version == 1
    assert json.loads(watchlist_json(_watchlist(updated_at=None)))["schema_version"] == 1
    assert WatchlistDeleteDocument(deleted=False, watchlist=None, unreadable=None).model_dump(mode="json") == {
        "schema_version": 1,
        "deleted": False,
        "watchlist": None,
        "unreadable": None,
    }


def test_an_unreadable_entry_document_needs_an_error_that_names_its_entry() -> None:
    named = StoredSelectionError(
        "its stored selection is not valid JSON",
        watchlist_name="Core",
        entry_number=2,
        ticker="KO",
        method="old",
        method_id="old_method",
    )
    assert build_unreadable_entry_document(named) == UnreadableEntryDocument(
        entry_number=2, ticker="KO", method_id="old_method", reason=str(named)
    )
    with pytest.raises(ValueError, match="names its entry"):
        build_unreadable_entry_document(StoredSelectionError("its stored selection is not valid JSON"))


def test_the_runs_list_is_a_versioned_object_and_an_empty_page_has_no_items() -> None:
    assert RunsListDocument(has_more=False, items=()).model_dump(mode="json") == {
        "schema_version": 2,
        "has_more": False,
        "items": [],
    }
    row = RunSummaryDocument(
        analysis_run_id=UUID(int=1),
        ticker="AAPL",
        method_id="sma_crossover",
        outcome=RunOutcome.COMPLETED,
        completed_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        refresh_id=None,
    )
    document = RunsListDocument(has_more=True, items=(row,)).model_dump(mode="json")
    assert list(document) == ["schema_version", "has_more", "items"]
    assert document["has_more"] is True
    assert document["items"] == [
        {
            "analysis_run_id": "00000000-0000-0000-0000-000000000001",
            "ticker": "AAPL",
            "method_id": "sma_crossover",
            "outcome": "completed",
            "completed_at": "2026-01-02T03:04:05+00:00",
            "refresh_id": None,
        }
    ]


def test_the_refresh_summary_reports_an_unsaved_outcome_and_a_failed_job() -> None:
    summary = RefreshSummary(
        refresh_id=UUID(int=2),
        watchlist_id=UUID(int=3),
        watchlist_name="Seeded",
        results=(
            RefreshJobResult(ticker="AAPL", method_id="sma_crossover", outcome=RunOutcome.COMPLETED),
            RefreshJobResult(ticker="BAD", method_id="sma_crossover", error="boom", reason_code="provider_error"),
        ),
    )
    document = json.loads(document_json(build_refresh_document(summary, ProviderCheckFindings())))
    assert list(document) == [
        "schema_version",
        "refresh_id",
        "watchlist_id",
        "watchlist_name",
        "results",
        "counts",
        "provider_check",
    ]
    assert document["schema_version"] == 3
    assert document["provider_check"] is None
    assert document["results"] == [
        {
            "ticker": "AAPL",
            "method_id": "sma_crossover",
            "analysis_run_id": None,
            "saved": False,
            "status": "completed",
            "error": None,
            "reason_code": None,
        },
        {
            "ticker": "BAD",
            "method_id": "sma_crossover",
            "analysis_run_id": None,
            "saved": False,
            "status": None,
            "error": "boom",
            "reason_code": "provider_error",
        },
    ]
    assert document["counts"] == {"completed": 1, "error": 1}


def test_a_refresh_job_with_an_unknown_reason_code_is_rejected() -> None:
    summary = RefreshSummary(
        refresh_id=UUID(int=2),
        watchlist_id=UUID(int=3),
        watchlist_name="Seeded",
        results=(RefreshJobResult(ticker="X", method_id="m", error="boom", reason_code="not_a_code"),),
    )
    with pytest.raises(ValueError, match="not_a_code"):
        document_json(build_refresh_document(summary, ProviderCheckFindings()))


def test_a_refresh_result_document_enforces_its_consistency_rules() -> None:
    base: dict[str, Any] = {
        "ticker": "A",
        "method_id": "m",
        "analysis_run_id": None,
        "saved": False,
        "status": RunOutcome.COMPLETED,
        "error": None,
        "reason_code": None,
    }
    RefreshResultDocument(**base)
    for change, message in (
        ({"saved": True}, "saved is true"),
        ({"reason_code": FailureReasonCode.PROVIDER_ERROR}, "reason_code is set"),
        ({"error": "boom", "reason_code": FailureReasonCode.PROVIDER_ERROR}, "status is set"),
        ({"status": None}, "status is set"),
    ):
        with pytest.raises(ValidationError, match=message):
            RefreshResultDocument(**{**base, **change})


def test_the_generator_publishes_the_watchlist_documents_and_the_other_workspace_documents() -> None:
    assert {
        name: model
        for name, model in DOCUMENTS
        if name in {*_VERSIONED_WATCHLIST_FILES, "refresh-summary.schema.json", "runs-list.schema.json"}
    } == {
        "watchlist.schema.json": WatchlistDocument,
        "watchlist-delete.schema.json": WatchlistDeleteDocument,
        "watchlist-removal.schema.json": WatchlistRemovalDocument,
        "watchlist-rename.schema.json": WatchlistRenameDocument,
        "runs-list.schema.json": RunsListDocument,
        "refresh-summary.schema.json": RefreshSummaryDocument,
    }


def test_a_refresh_of_entries_has_no_watchlist_and_the_id_and_name_go_together() -> None:
    summary = RefreshSummary(
        refresh_id=UUID(int=2),
        watchlist_id=None,
        watchlist_name=None,
        results=(RefreshJobResult(ticker="AAPL", method_id="sma_crossover", outcome=RunOutcome.COMPLETED),),
    )

    document = json.loads(document_json(build_refresh_document(summary, ProviderCheckFindings())))

    assert (document["watchlist_id"], document["watchlist_name"]) == (None, None)
    for watchlist_id, name in ((UUID(int=3), None), (None, "Seeded")):
        with pytest.raises(ValueError, match="both be set or both null"):
            RefreshSummaryDocument(
                refresh_id=UUID(int=2),
                watchlist_id=watchlist_id,
                watchlist_name=name,
                results=(),
                counts={},
                provider_check=None,
            )
