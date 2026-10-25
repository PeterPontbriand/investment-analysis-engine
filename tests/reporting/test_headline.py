"""The headline types, and each existing strategy's headline over the stored run of every outcome it can have."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.reporting.headline import (
    UNIT_PERCENT,
    CellKind,
    Headline,
    HeadlineCell,
    per_share_unit,
)
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategy_wiring import (
    EVIDENCE_BY_KEY,
    GRAHAM_NUMBER,
    HEADLINES_BY_KEY,
    MOMENTUM,
    STRATEGIES,
)
from investment_analysis_engine.workspace.codecs import decode_evidence
from tests._direct_command_output import _COMMANDS
from tests._strategy_document_output import CASES, Case, run_saved

STAMP = datetime(2026, 1, 1, tzinfo=UTC)
NO_CURRENCY = "currency unspecified per share"


def _number(**changes: object) -> HeadlineCell:
    base = HeadlineCell("k", "K", CellKind.NUMBER, 1.0, UNIT_PERCENT, MetricStatus.OK)
    return replace(base, **changes)  # type: ignore[arg-type]


def test_a_valid_number_and_text_cell_construct() -> None:
    assert _number().value == 1.0
    assert HeadlineCell("t", "T", CellKind.TEXT, "Bullish", None, None).value == "Bullish"
    assert HeadlineCell("t", "T", CellKind.TEXT, None, None, None).value is None
    absent = _number(value=None, status=CalculationStatus.INPUT_UNAVAILABLE, reason_code=ReasonCode.MISSING_FACT)
    assert absent.value is None


@pytest.mark.parametrize(
    "changes",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": True},
        {"value": "1.0"},
        {"unit": None},
        {"unit": " "},
        {"status": None},
        {"value": None},
        {"status": MetricStatus.UNAVAILABLE},
        {"reason_code": ReasonCode.MISSING_FACT},
        {"key": " "},
        {"label": ""},
    ],
)
def test_an_invalid_number_cell_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"."):
        _number(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"value": 1.0},
        {"value": " "},
        {"unit": "percent"},
        {"status": MetricStatus.OK},
        {"reason_code": ReasonCode.MISSING_FACT},
    ],
)
def test_an_invalid_text_cell_is_rejected(changes: dict[str, object]) -> None:
    base = HeadlineCell("t", "T", CellKind.TEXT, "PASS", None, None)
    with pytest.raises(ValueError, match=r"."):
        replace(base, **changes)  # type: ignore[arg-type]


def test_a_headline_needs_cells_with_unique_keys_and_an_aware_period_end() -> None:
    cell = _number()
    assert Headline(cells=(cell,), period_end=STAMP, period_end_label="span end").taxonomy is None
    for bad in (
        {"cells": ()},
        {"cells": (cell, cell)},
        {"cells": (cell,), "period_end": datetime(2026, 1, 1), "period_end_label": "span end"},
        {"cells": (cell,), "taxonomy": " "},
        {"cells": (cell,), "period_end": STAMP},
        {"cells": (cell,), "period_end_label": " "},
    ):
        with pytest.raises(ValueError, match=r"."):
            Headline(**bad)


def test_the_per_share_unit_names_the_currency_or_says_none_was_recorded() -> None:
    assert per_share_unit("USD") == "USD per share"
    assert per_share_unit(None) == NO_CURRENCY
    assert per_share_unit("") == NO_CURRENCY


def _headline_of(case: Case) -> tuple[str, Headline]:
    _direct, _replayed, run = run_saved(case)
    evidence = decode_evidence(run, EVIDENCE_BY_KEY)
    assert evidence is not None
    return run.status.value, HEADLINES_BY_KEY[(run.analysis_id, run.method_id)](evidence)


def _cells(case_name: str) -> dict[str, HeadlineCell]:
    case = next(item for item in CASES if item.name == case_name)
    return {cell.key: cell for cell in _headline_of(case)[1].cells}


def test_momentum_cells_for_a_known_trend() -> None:
    cells = _cells("momentum-success")
    assert list(cells) == ["trend", "rsi"]
    assert (cells["trend"].label, cells["trend"].value, cells["trend"].status) == ("Trend", "Bullish", None)
    assert (cells["rsi"].label, cells["rsi"].unit, cells["rsi"].status, cells["rsi"].value) == (
        "RSI",
        "points",
        MetricStatus.OK,
        100.0,
    )


def test_a_bearish_trend_is_the_word_bearish() -> None:
    from investment_analysis_engine.core.constants import TrendStatus  # noqa: PLC0415
    from investment_analysis_engine.strategies.momentum.presenter import trend_word  # noqa: PLC0415

    assert trend_word(TrendStatus.BEARISH) == "Bearish"
    assert trend_word(TrendStatus.UNKNOWN) is None


@pytest.mark.parametrize(
    ("case_name", "rsi_status", "rsi_code"),
    [
        ("momentum-insufficient-data", MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY),
        ("momentum-provider-error", CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR),
        ("momentum-no-observation", CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.NOT_AVAILABLE_AS_OF),
    ],
)
def test_momentum_cells_without_a_known_trend(
    case_name: str, rsi_status: MetricStatus | CalculationStatus, rsi_code: ReasonCode
) -> None:
    cells = _cells(case_name)
    assert cells["trend"].value is None, "An UNKNOWN trend and an absent calculation are both no value."
    assert cells["rsi"].value is None
    assert (cells["rsi"].status, cells["rsi"].reason_code) == (rsi_status, rsi_code)


def test_an_unknown_trend_keeps_the_rsi_that_was_computed() -> None:
    """A history shorter than the long average but longer than the RSI period still has an RSI."""
    from tests.analysis.momentum.test_momentum_exception_table import _data, _provider, _run  # noqa: PLC0415

    run = _run(_provider(_data([1.0, 2.0, 3.0, 4.0])))
    headline = HEADLINES_BY_KEY[(MOMENTUM.analysis_id, MOMENTUM.method_id)](run)
    cells = {cell.key: cell for cell in headline.cells}
    assert cells["trend"].value is None
    assert (cells["rsi"].value, cells["rsi"].status) == (100.0, MetricStatus.OK)


@pytest.mark.parametrize(
    ("case_name", "price_status", "price", "unit", "period"),
    [
        ("graham-number-success", CalculationStatus.OK, 36.686169055926236, "USD per share", True),
        ("graham-number-nonpositive-eps", CalculationStatus.NOT_APPLICABLE, None, "USD per share", False),
        ("graham-number-etf", CalculationStatus.NOT_APPLICABLE, None, NO_CURRENCY, False),
        (
            "graham-number-missing-input",
            CalculationStatus.INPUT_UNAVAILABLE,
            None,
            NO_CURRENCY,
            False,
        ),
        (
            "graham-number-provider-error",
            CalculationStatus.PROVIDER_ERROR,
            None,
            NO_CURRENCY,
            False,
        ),
    ],
)
def test_graham_number_price_cell(
    case_name: str, price_status: CalculationStatus, price: float | None, unit: str, period: bool
) -> None:
    case = next(item for item in CASES if item.name == case_name)
    _status, headline = _headline_of(case)
    cell = headline.cells[0]
    assert (cell.key, cell.label, cell.kind) == ("maximum_indicated_price", "Max price", CellKind.NUMBER)
    assert (cell.value, cell.status, cell.unit, cell.reason_code) == (price, price_status, unit, None)
    assert (headline.period_end is not None) is period
    assert headline.taxonomy is None
    assert headline.period_end_label == "earnings input period end"
    assert [item.key for item in headline.cells] == ["maximum_indicated_price", "margin_of_safety"]
    assert headline.cells[1].label == "Margin"


@pytest.mark.parametrize(
    ("case_name", "status", "value"),
    [
        ("graham-growth-success", CalculationStatus.OK, 58.4874074074074),
        ("graham-growth-negative-growth", CalculationStatus.OK, 14.226666666666667),
        ("graham-growth-etf", CalculationStatus.NOT_APPLICABLE, None),
        ("graham-growth-missing-input", CalculationStatus.INPUT_UNAVAILABLE, None),
        ("graham-growth-provider-error", CalculationStatus.PROVIDER_ERROR, None),
    ],
)
def test_graham_growth_value_cell(case_name: str, status: CalculationStatus, value: float | None) -> None:
    case = next(item for item in CASES if item.name == case_name)
    _outcome, headline = _headline_of(case)
    cell = headline.cells[0]
    assert (cell.key, cell.label, cell.value, cell.status, cell.reason_code) == (
        "intrinsic_value",
        "Value",
        value,
        status,
        None,
    )
    assert headline.cells[1].key == "margin_of_safety"


def test_a_graham_margin_is_ok_with_its_percent_when_the_comparison_is_available() -> None:
    _status, headline = _headline_of(next(item for item in CASES if item.name == "graham-number-success"))
    run = run_saved(next(item for item in CASES if item.name == "graham-number-success"))[2]
    analysis = decode_evidence(run, EVIDENCE_BY_KEY)
    assert isinstance(analysis, GrahamNumberAnalysis)
    from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison  # noqa: PLC0415

    available = replace(
        analysis, price_comparison=PriceComparison("available", "ok", percent=18.4), margin_of_safety_percent=18.4
    )
    cell = GRAHAM_NUMBER.behavior.headline_for(available).cells[1]
    assert (cell.value, cell.status, cell.unit, cell.reason_code) == (18.4, MetricStatus.OK, "percent", None)
    assert headline.cells[1].status is MetricStatus.UNAVAILABLE


def test_a_graham_margin_without_a_comparison_takes_the_runs_status() -> None:
    run = run_saved(next(item for item in CASES if item.name == "graham-number-missing-input"))[2]
    analysis = decode_evidence(run, EVIDENCE_BY_KEY)
    assert isinstance(analysis, GrahamNumberAnalysis)
    bare = replace(analysis, price_comparison=None)
    cell = GRAHAM_NUMBER.behavior.headline_for(bare).cells[1]
    assert cell.status is CalculationStatus.INPUT_UNAVAILABLE
    ok_without_comparison = GRAHAM_NUMBER.behavior.headline_for(
        replace(
            decode_evidence(
                run_saved(next(item for item in CASES if item.name == "graham-number-success"))[2], EVIDENCE_BY_KEY
            ),
            price_comparison=None,
        )  # type: ignore[type-var]
    ).cells[1]
    assert ok_without_comparison.status is MetricStatus.UNAVAILABLE


_OVERRIDE_CASES = (
    Case(
        "graham-number-both-overrides",
        "graham-number",
        (*_COMMANDS["graham-number"], "--eps", "5", "--bvps", "10"),
        0,
    ),
    Case(
        "graham-growth-eps-override",
        "graham-growth",
        (*_COMMANDS["graham-growth"], "--eps", "5"),
        0,
    ),
)


@pytest.mark.parametrize("case", _OVERRIDE_CASES, ids=lambda case: case.name)
def test_an_overridden_earnings_input_gives_a_per_share_cell_with_no_currency_and_no_period(case: Case) -> None:
    status, headline = _headline_of(case)
    cell = headline.cells[0]
    assert status == "completed"
    assert cell.status is CalculationStatus.OK
    assert cell.value is not None
    assert cell.unit == NO_CURRENCY
    assert headline.period_end is None, "An override carries no fiscal period."


@pytest.mark.parametrize(
    ("case_name", "label", "status", "code"),
    [
        ("fcf-growth-success", "FCF CAGR", MetricStatus.OK, None),
        ("fcf-growth-confirmation-per-share", "FCF/share CAGR", MetricStatus.OK, None),
        ("fcf-growth-nonmeaningful", "FCF CAGR", MetricStatus.UNAVAILABLE, ReasonCode.SIGN_CHANGE),
        ("fcf-growth-missing-input", "FCF CAGR", MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT),
        ("fcf-growth-provider-error", "FCF CAGR", MetricStatus.UNAVAILABLE, ReasonCode.PROVIDER_ERROR),
        ("fcf-growth-etf", "FCF CAGR", MetricStatus.NOT_APPLICABLE, ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE),
    ],
)
def test_fcf_growth_cagr_cell_names_its_basis_and_takes_the_metrics_own_status_and_code(
    case_name: str, label: str, status: MetricStatus, code: ReasonCode | None
) -> None:
    cells = _cells(case_name)
    assert list(cells) == ["fcf_cagr", "eps_cagr", "classification"]
    cagr = cells["fcf_cagr"]
    assert (cagr.label, cagr.unit, cagr.status, cagr.reason_code) == (label, "percent", status, code)
    assert (cagr.value is not None) is (status is MetricStatus.OK)


@pytest.mark.parametrize(
    ("case_name", "word"),
    [
        ("fcf-growth-success", "PASS"),
        ("fcf-growth-declining", "FAIL"),
        ("fcf-growth-nonmeaningful", "INDETERMINATE"),
        ("fcf-growth-missing-input", "INDETERMINATE"),
    ],
)
def test_fcf_growth_classification_is_the_screen_word_with_no_status(case_name: str, word: str) -> None:
    cell = _cells(case_name)["classification"]
    assert (cell.label, cell.kind, cell.value, cell.status, cell.reason_code, cell.unit) == (
        "Class",
        CellKind.TEXT,
        word,
        None,
        None,
        None,
    )


def test_the_period_end_of_fcf_growth_is_the_recorded_end_of_the_span() -> None:
    case = next(item for item in CASES if item.name == "fcf-growth-success")
    _status, headline = _headline_of(case)
    run = run_saved(case)[2]
    evidence = decode_evidence(run, EVIDENCE_BY_KEY)
    assert headline.period_end == getattr(evidence, "period_end")  # noqa: B009
    assert headline.period_end is not None


def test_headline_for_rejects_another_strategys_result_and_a_subclass() -> None:
    momentum_run = run_saved(next(item for item in CASES if item.name == "momentum-success"))[2]
    momentum = decode_evidence(momentum_run, EVIDENCE_BY_KEY)
    assert momentum is not None
    with pytest.raises(UndeclaredStrategyError):
        GRAHAM_NUMBER.behavior.headline_for(momentum)
    with pytest.raises(UndeclaredStrategyError):
        MOMENTUM.behavior.headline_for(object())
    subclass = type("_SubclassedRun", (type(momentum),), {})
    with pytest.raises(UndeclaredStrategyError):
        MOMENTUM.behavior.headline_for(object.__new__(subclass))


def test_every_declared_strategy_has_a_headline_function() -> None:
    assert set(HEADLINES_BY_KEY) == {(item.analysis_id, item.method_id) for item in STRATEGIES}
