"""The ``runs compare`` document's cell formatting and models, without a stored refresh."""

import typing
from uuid import UUID

import pytest
from pydantic import ValidationError

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus
from investment_analysis_engine.reporting.headline import CellKind, CellUnit
from investment_analysis_engine.workspace_documents.runs_compare import (
    CellStatusValue,
    CompareCellDocument,
    CompareRunDocument,
    format_cell,
)

RUN_ID = UUID("00000000-0000-4000-8000-000000000001")


def _cell(
    value: float | str | None,
    unit: CellUnit | None,
    currency: str | None = None,
    kind: CellKind = CellKind.NUMBER,
) -> CompareCellDocument:
    return CompareCellDocument(
        key="k",
        label="K",
        term="term-k",
        kind=kind,
        value=value,
        unit=unit,
        currency=currency,
        status="ok" if kind is CellKind.NUMBER else None,
        reason_code=None,
    )


@pytest.mark.parametrize(
    ("value", "unit", "currency", "expected"),
    [
        (18.44, CellUnit.PERCENT, None, "18.4%"),
        (-7.3, CellUnit.PERCENT, None, "−7.3%"),
        (61.25, CellUnit.POINTS, None, "61.2"),
        (12.34, CellUnit.MULTIPLE, None, "12.3x"),
        (-0.04, CellUnit.MULTIPLE, None, "−0.0x"),
        (142.1, CellUnit.PER_SHARE, "USD", "142.10 USD"),
        (-3.5, CellUnit.PER_SHARE, "CAD", "−3.50 CAD"),
        (142.1, CellUnit.PER_SHARE, None, "142.10 (currency unspecified)"),
        (None, CellUnit.PERCENT, None, "—"),
    ],
)
def test_a_number_is_formatted_by_its_unit(
    value: float | None, unit: CellUnit, currency: str | None, expected: str
) -> None:
    assert format_cell(_cell(value, unit, currency)) == expected


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": CellKind.TEXT, "value": "Bullish", "unit": CellUnit.PERCENT, "status": None},
        {"kind": CellKind.TEXT, "value": "Bullish", "unit": None, "currency": "USD", "status": None},
        {"kind": CellKind.NUMBER, "unit": None},
        {"kind": CellKind.NUMBER, "unit": CellUnit.PERCENT, "currency": "USD"},
    ],
)
def test_a_cell_document_refuses_a_unit_or_currency_its_kind_cannot_carry(fields: dict[str, object]) -> None:
    base: dict[str, object] = {
        "key": "k",
        "label": "K",
        "term": "term-k",
        "kind": CellKind.NUMBER,
        "value": 1.0,
        "unit": CellUnit.PER_SHARE,
        "currency": None,
        "status": "ok",
        "reason_code": None,
    }
    with pytest.raises(ValidationError):
        CompareCellDocument(**{**base, **fields})  # type: ignore[arg-type]


def test_a_text_cell_is_its_text_and_an_absent_one_is_a_dash() -> None:
    assert format_cell(_cell("Bullish", None, kind=CellKind.TEXT)) == "Bullish"
    assert format_cell(_cell(None, None, kind=CellKind.TEXT)) == "—"


def test_a_run_has_a_headline_or_the_reason_it_has_none_and_not_both() -> None:
    with pytest.raises(ValidationError, match="headline or the reason"):
        CompareRunDocument(
            analysis_run_id=RUN_ID,
            outcome=RunOutcome.FAILED,
            requested_as_of=None,
            headline=None,
            headline_unavailable=None,
        )


def test_the_status_values_are_exactly_the_calculation_and_metric_statuses() -> None:
    assert set(typing.get_args(CellStatusValue.__value__)) == {item.value for item in CalculationStatus} | {
        item.value for item in MetricStatus
    }
