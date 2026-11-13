"""The Graham documents serve a reason code exactly when the status is not ok, and the price cell carries it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.strategies.graham_growth.envelope import GrahamGrowthDocument
from investment_analysis_engine.strategies.graham_growth.replay import headline_graham_growth
from investment_analysis_engine.strategies.graham_number.envelope import GrahamNumberDocument
from investment_analysis_engine.strategies.graham_number.replay import headline_graham_number
from tests.analysis.graham_value._anchored import ScriptedProvider, etf_profile, run_growth, run_number

EXPECTED = Path(__file__).parent / "expected_output"
STORED = sorted(
    [
        *(EXPECTED / "strategy_documents").glob("graham-*.json"),
        *(EXPECTED / "direct_commands").glob("graham-*.json"),
    ]
)


def test_the_stored_graham_documents_exist() -> None:
    assert STORED, "no stored Graham document was found"


@pytest.mark.parametrize("path", STORED, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_a_stored_graham_document_has_a_reason_code_exactly_when_its_status_is_not_ok(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    if "reason_code" not in document:
        pytest.skip("not a strategy document")

    keys = list(document)
    assert keys.index("reason_code") + 1 == keys.index("reason"), "reason_code sits immediately before reason"
    assert (document["reason_code"] is None) is (document["status"] == "ok")
    if document["reason_code"] is not None:
        assert ReasonCode(document["reason_code"])
        assert document["reason"]


MODELS: dict[str, type[GrahamNumberDocument] | type[GrahamGrowthDocument]] = {
    "graham_number": GrahamNumberDocument,
    "graham_growth_value": GrahamGrowthDocument,
}


@pytest.mark.parametrize("path", STORED, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_the_document_model_enforces_the_same_rule(path: Path) -> None:
    text = path.read_text(encoding="utf-8").replace("<wall-clock>", "2026-01-01T00:00:00+00:00")
    document = json.loads(text)
    if "reason_code" not in document:
        pytest.skip("not a strategy document")
    MODELS[document["analysis"]].model_validate(document)
    flipped = {**document, "reason_code": None if document["reason_code"] is not None else "invalid_request"}

    with pytest.raises(ValueError, match="reason_code is null exactly when status is ok"):
        MODELS[document["analysis"]].model_validate(flipped)


@pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
def test_the_price_cell_of_a_failed_run_carries_the_analysis_code(growth: bool) -> None:
    profile = etf_profile()
    if growth:
        analysis_growth = run_growth(ScriptedProvider(), profile=profile)
        cell = headline_graham_growth(analysis_growth).cells[0]
        expected = analysis_growth.reason_code
    else:
        analysis_number = run_number(ScriptedProvider(), profile=profile)
        cell = headline_graham_number(analysis_number).cells[0]
        expected = analysis_number.reason_code

    assert expected is ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE
    assert cell.reason_code is expected


@pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
def test_the_price_cell_of_a_successful_run_carries_no_code(growth: bool) -> None:
    headline = (
        headline_graham_growth(run_growth(ScriptedProvider()))
        if growth
        else headline_graham_number(run_number(ScriptedProvider()))
    )

    assert headline.cells[0].reason_code is None
    assert headline.cells[0].value is not None
