"""A date given as an ``as_of`` is served as that date; a timestamp keeps its instant and offset."""

from datetime import UTC, date, datetime, timedelta, timezone

from pydantic import BaseModel

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.reporting.documents.timestamp import (
    DocumentAsOf,
    as_of_text,
    document_json_value,
    is_end_of_day_utc,
)
from investment_analysis_engine.reporting.presentation import format_as_of
from investment_analysis_engine.strategy_wiring import PIOTROSKI

_END_OF_DAY = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
_TORONTO = timezone(timedelta(hours=-5))
CONTEXT = ApplicationContext(settings=ProjectSettings())


class _Document(BaseModel):
    requested_as_of: DocumentAsOf | None


def test_the_end_of_a_utc_day_is_served_as_its_date() -> None:
    assert as_of_text(_END_OF_DAY) == "2025-12-31"


def test_a_timestamp_keeps_its_instant_and_its_offset() -> None:
    assert as_of_text(datetime(2025, 12, 31, 12, tzinfo=UTC)) == "2025-12-31T12:00:00+00:00"
    assert as_of_text(datetime(2025, 12, 31, 18, 59, 59, 999999, tzinfo=_TORONTO)) == "2025-12-31T18:59:59.999999-05:00"
    assert as_of_text(datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=_TORONTO)) == "2025-12-31T23:59:59.999999-05:00"


def test_a_document_as_of_is_a_date_or_an_instant_in_json_and_null_for_now() -> None:
    assert _Document(requested_as_of=_END_OF_DAY).model_dump(mode="json") == {"requested_as_of": "2025-12-31"}
    assert _Document(requested_as_of=None).model_dump(mode="json") == {"requested_as_of": None}


def test_a_stored_selection_serves_its_date_and_stores_the_end_of_day_unchanged() -> None:
    selection = build_selection(CONTEXT, PIOTROSKI.method_id, {"as_of": date(2025, 12, 31)})
    assert selection.as_of == _END_OF_DAY
    assert document_json_value(selection)["as_of"] == "2025-12-31"


def test_a_stored_selection_with_a_timestamp_serves_the_timestamp() -> None:
    moment = datetime(2025, 12, 31, 12, tzinfo=_TORONTO)
    selection = build_selection(CONTEXT, PIOTROSKI.method_id, {"as_of": moment})
    assert document_json_value(selection)["as_of"] == "2025-12-31T12:00:00-05:00"


def test_the_end_of_day_predicate_holds_only_for_the_last_microsecond_of_a_utc_day() -> None:
    assert is_end_of_day_utc(_END_OF_DAY)
    assert is_end_of_day_utc(_END_OF_DAY.astimezone(timezone(timedelta(0))))
    assert not is_end_of_day_utc(_END_OF_DAY - timedelta(microseconds=1))
    assert not is_end_of_day_utc(datetime(2025, 12, 31, tzinfo=UTC))
    assert not is_end_of_day_utc(datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=_TORONTO))
    assert not is_end_of_day_utc(_END_OF_DAY.astimezone(_TORONTO))


def test_text_output_prints_the_date_exactly_where_documents_serve_it_and_null_is_current() -> None:
    assert format_as_of(_END_OF_DAY) == as_of_text(_END_OF_DAY) == "2025-12-31"
    local = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=_TORONTO)
    assert format_as_of(local) != "2025-12-31"
    assert as_of_text(local) == local.isoformat()
    assert format_as_of(None) == "current"
