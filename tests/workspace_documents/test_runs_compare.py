"""The ``runs compare`` document's cell formatting and models, without a stored refresh."""

import typing
from uuid import UUID

import pytest
from pydantic import ValidationError

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus
from investment_analysis_engine.reporting.headline import CellKind
from investment_analysis_engine.workspace_documents.runs_compare import (
    CellStatusValue,
    CompareCellDocument,
    CompareRunDocument,
    format_cell,
)

RUN_ID = UUID("00000000-0000-4000-8000-000000000001")


def _cell(value: float | str | None, unit: str | None, kind: CellKind = CellKind.NUMBER) -> CompareCellDocument:
    return CompareCellDocument(
        key="k",
        label="K",
        kind=kind,
        value=value,
        unit=unit,
        status="ok" if kind is CellKind.NUMBER else None,
        reason_code=None,
    )


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (18.44, "percent", "18.4%"),
        (-7.3, "percent", "−7.3%"),
        (61.25, "points", "61.2"),
        (12.34, "multiple", "12.3x"),
        (-0.04, "multiple", "−0.0x"),
        (142.1, "USD per share", "142.10 USD"),
        (-3.5, "CAD per share", "−3.50 CAD"),
        (142.1, "currency unspecified per share", "142.10 (currency unspecified)"),
        (None, "percent", "—"),
        (3.0, "widgets", "3.00 widgets"),
    ],
)
def test_a_number_is_formatted_by_its_unit(value: float | None, unit: str, expected: str) -> None:
    assert format_cell(_cell(value, unit)) == expected


def test_a_text_cell_is_its_text_and_an_absent_one_is_a_dash() -> None:
    assert format_cell(_cell("Bullish", None, CellKind.TEXT)) == "Bullish"
    assert format_cell(_cell(None, None, CellKind.TEXT)) == "—"


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
    assert set(typing.get_args(CellStatusValue)) == {item.value for item in CalculationStatus} | {
        item.value for item in MetricStatus
    }
