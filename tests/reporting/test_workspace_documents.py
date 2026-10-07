"""The typed workspace documents: shape, timestamp spelling, versioning statement and builder behavior."""

import json
import types
import typing
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any, get_args, get_origin
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.types import AwareDatetime, FutureDatetime, NaiveDatetime, PastDatetime

from scripts.generate_schemas import DOCUMENTS, expected_schemas
from src.cli_workspace import _refresh_json, _watchlist_json
from src.reporting.documents.failure import FailureReasonCode
from src.reporting.documents.refresh import RefreshResultDocument, RefreshSummaryDocument
from src.reporting.documents.runs import RunsListDocument, RunSummaryDocument
from src.reporting.documents.timestamp import DocumentTimestamp
from src.reporting.documents.watchlist import WatchlistDeleteDocument, WatchlistDocument
from src.strategies.fcf_growth.selection import FCFGrowthSelection
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.models import RunOutcome
from src.workspace.refresh import RefreshJobResult, RefreshSummary
from src.workspace.runs import Watchlist, WatchlistEntry
from src.workspace.strategy_types import SelectionMember

_DATETIME_LEAVES: tuple[Any, ...] = (datetime, AwareDatetime, NaiveDatetime, PastDatetime, FutureDatetime)
_TIMESTAMP_METADATA: tuple[Any, ...] = get_args(DocumentTimestamp)[1:]
_SELECTION_MEMBERS: tuple[Any, ...] = get_args(SelectionMember)
_WORKSPACE_FILES = (
    "refresh-summary.schema.json",
    "runs-list.schema.json",
    "watchlist-delete.schema.json",
    "watchlist.schema.json",
)


def _untyped_datetime_fields(model: type[BaseModel], seen: set[type[BaseModel]]) -> list[str]:
    """Return ``Model.field`` for every datetime field below ``model`` that does not use ``DocumentTimestamp``.

    A selection member is a stored selection owned by its strategy, not a document model, so the walk stops there.
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


@pytest.mark.parametrize("file_name", _WORKSPACE_FILES)
def test_each_workspace_schema_states_that_the_document_is_unversioned(file_name: str) -> None:
    schema = json.loads(expected_schemas()[file_name])
    assert "unversioned" in schema["description"]
    assert "schema_version" not in schema.get("properties", {})


def test_the_refresh_summary_reuses_the_failure_envelopes_reason_codes() -> None:
    schema = json.loads(expected_schemas()["refresh-summary.schema.json"])
    assert schema["$defs"]["FailureReasonCode"]["enum"] == [item.value for item in FailureReasonCode]
    assert RefreshResultDocument.model_fields["reason_code"].annotation == FailureReasonCode | None


def test_the_watchlist_selection_is_the_analysis_selection_union() -> None:
    schema = json.loads(expected_schemas()["watchlist.schema.json"])
    selection = schema["$defs"]["WatchlistEntryDocument"]["properties"]["selection"]
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


def test_the_watchlist_document_matches_what_the_hand_built_dictionary_wrote() -> None:
    """Each selection is its own ``model_dump``, byte for byte; a non-UTC offset is emitted as it is."""
    watchlist = _watchlist(updated_at=datetime(2026, 3, 5, tzinfo=timezone(timedelta(hours=-4))))
    expected = {
        "watchlist_id": str(watchlist.watchlist_id),
        "display_name": "Core",
        "created_at": watchlist.created_at.isoformat(),
        "updated_at": "2026-03-05T00:00:00-04:00",
        "entries": [
            {"index": index, "ticker": entry.ticker, "selection": entry.selection.model_dump(mode="json")}
            for index, entry in enumerate(watchlist.entries, start=1)
        ],
    }
    assert _watchlist_json(watchlist) == json.dumps(expected, ensure_ascii=False, allow_nan=False)
    assert _watchlist_json(watchlist).count('"as_of": "2026-01-02T00:00:00Z"') == 1


def test_a_watchlist_never_changed_has_a_null_updated_at() -> None:
    assert json.loads(_watchlist_json(_watchlist(updated_at=None)))["updated_at"] is None


def test_the_delete_document_requires_the_watchlist_if_and_only_if_it_was_deleted() -> None:
    document = WatchlistDocument.model_validate(json.loads(_watchlist_json(_watchlist(updated_at=None))))
    WatchlistDeleteDocument(requested_name="Core", deleted=True, watchlist=document)
    WatchlistDeleteDocument(requested_name="Nowhere", deleted=False, watchlist=None)
    with pytest.raises(ValidationError, match="if and only if deleted"):
        WatchlistDeleteDocument(requested_name="Core", deleted=True, watchlist=None)
    with pytest.raises(ValidationError, match="if and only if deleted"):
        WatchlistDeleteDocument(requested_name="Core", deleted=False, watchlist=document)


def test_the_runs_list_is_a_bare_array_and_an_empty_list_is_an_empty_array() -> None:
    assert RunsListDocument(()).model_dump(mode="json") == []
    row = RunSummaryDocument(
        analysis_run_id=UUID(int=1),
        ticker="AAPL",
        method_id="sma_crossover",
        status=RunOutcome.COMPLETED,
        completed_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        refresh_id=None,
    )
    assert RunsListDocument((row,)).model_dump(mode="json") == [
        {
            "analysis_run_id": "00000000-0000-0000-0000-000000000001",
            "ticker": "AAPL",
            "method_id": "sma_crossover",
            "status": "completed",
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
    document = json.loads(_refresh_json(summary))
    assert list(document) == ["refresh_id", "watchlist_id", "watchlist_name", "results", "counts"]
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
        _refresh_json(summary)


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


def test_the_generator_publishes_the_four_workspace_documents() -> None:
    assert {name: model for name, model in DOCUMENTS if name in _WORKSPACE_FILES} == {
        "watchlist.schema.json": WatchlistDocument,
        "watchlist-delete.schema.json": WatchlistDeleteDocument,
        "runs-list.schema.json": RunsListDocument,
        "refresh-summary.schema.json": RefreshSummaryDocument,
    }
