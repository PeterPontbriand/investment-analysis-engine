"""What the Graham documents and text views say about the anchor filing and the years left out (A.19, M8 to M11)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from investment_analysis_engine.analysis.shared.anchor_filing import stale_anchor_message
from investment_analysis_engine.data.financial.resolver import EARLIER_BASIS_MESSAGE
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.graham_growth.codec import decode_graham_growth, encode_graham_growth
from investment_analysis_engine.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    build_graham_growth_document,
    render_graham_growth,
)
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.strategies.graham_number.codec import decode_graham_number, encode_graham_number
from investment_analysis_engine.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    build_graham_number_document,
    render_graham_number,
)
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from tests.analysis.graham_value._anchored import (
    LATE,
    POLICY,
    ScriptedProvider,
    etf_profile,
    run_growth,
    run_number,
)

STRATEGIES = pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
QUOTE = 40.0


def _analysis(
    growth: bool, provider: ScriptedProvider, **kwargs: object
) -> GrahamNumberAnalysis | GrahamGrowthAnalysis:
    kwargs.setdefault("quote_override", QUOTE)
    return run_growth(provider, **kwargs) if growth else run_number(provider, **kwargs)  # type: ignore[arg-type]


def _document(analysis: GrahamNumberAnalysis | GrahamGrowthAnalysis):  # type: ignore[no-untyped-def]
    if isinstance(analysis, GrahamGrowthAnalysis):
        return build_graham_growth_document(_growth_presentation(analysis))
    return build_graham_number_document(_number_presentation(analysis))


def _number_presentation(analysis: GrahamNumberAnalysis) -> GrahamNumberPresentation:
    return GrahamNumberPresentation(
        ticker=analysis.ticker,
        assembly=analysis.assembly,
        result=analysis.result,
        effective_as_of=analysis.effective_as_of,
        as_of=analysis.as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        instrument_profile=analysis.instrument_profile,
    )


def _growth_presentation(analysis: GrahamGrowthAnalysis) -> GrahamGrowthPresentation:
    return GrahamGrowthPresentation(
        ticker=analysis.ticker,
        assembly=analysis.assembly,
        result=analysis.result,
        effective_as_of=analysis.effective_as_of,
        as_of=analysis.as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        instrument_profile=analysis.instrument_profile,
        base_pe=POLICY.base_pe,
        growth_multiplier=POLICY.growth_multiplier,
        baseline_aaa_yield=POLICY.baseline_aaa_yield,
    )


def _text(analysis: GrahamNumberAnalysis | GrahamGrowthAnalysis, mode: PresentationMode) -> list[str]:
    if isinstance(analysis, GrahamGrowthAnalysis):
        return render_graham_growth(_growth_presentation(analysis), mode).splitlines()
    return render_graham_number(_number_presentation(analysis), mode).splitlines()


@STRATEGIES
def test_m8_a_fresh_anchor_is_reported_with_no_warning(growth: bool) -> None:
    document = _document(_analysis(growth, ScriptedProvider()))
    assert document.anchor_filing is not None
    assert (document.anchor_filing.year_end, document.anchor_filing.form, document.anchor_filing.stale) == (
        date(2024, 6, 30),
        "10-K",
        False,
    )
    assert document.anchor_filing.filing_date == date(2024, 9, 13)
    assert not any("annual report filed by" in warning for warning in document.warnings)


@STRATEGIES
def test_m8_a_stale_anchor_message_is_the_first_warning_of_the_document(growth: bool) -> None:
    analysis = _analysis(growth, ScriptedProvider(), effective_as_of=LATE)
    document = _document(analysis)
    assert document.anchor_filing is not None
    assert document.anchor_filing.stale
    assert analysis.assembly.anchor_filing is not None
    expected = stale_anchor_message(analysis.assembly.anchor_filing, LATE)
    assert document.warnings[0] == expected
    assert len(document.warnings) > 1, "the user-supplied quote warning follows it"
    assert expected == (
        "The newest annual report filed by 2025-12-01 is for the fiscal year ended 2024-06-30 (10-K, filed "
        "2024-09-13). The next one was due by 2025-10-20 at the latest, and none had been filed."
    )


@STRATEGIES
@pytest.mark.parametrize("mode", [PresentationMode.CONCISE, PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS])
def test_m9_the_text_gains_the_warning_and_no_other_line_and_it_comes_first_among_the_warnings(
    growth: bool, mode: PresentationMode
) -> None:
    fresh = _text(_analysis(growth, ScriptedProvider()), mode)
    stale_analysis = _analysis(growth, ScriptedProvider(), effective_as_of=LATE)
    stale = _text(stale_analysis, mode)
    assert stale_analysis.assembly.anchor_filing is not None
    message = f"Warning: {stale_anchor_message(stale_analysis.assembly.anchor_filing, LATE)}"
    assert [line for line in stale if line not in fresh] == [message]
    assert [line for line in fresh if line not in stale] == []
    warnings = [line for line in stale if line.startswith("Warning: ")]
    assert warnings[0] == message
    assert len(warnings) > 1


@STRATEGIES
def test_m8_the_stale_warning_is_shown_on_an_unavailable_result_too(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.bvps_years_back = 1
    provider.eps_years_back = 1
    analysis = _analysis(growth, provider, effective_as_of=LATE)
    document = _document(analysis)
    assert document.status.value in {"input_unavailable", "provider_error"}
    assert document.anchor_filing is not None
    assert document.warnings[0].startswith("The newest annual report filed by 2025-12-01")
    assert any(
        line.startswith("Warning: The newest annual report filed by")
        for line in _text(analysis, PresentationMode.CONCISE)
    )


@STRATEGIES
def test_m8_the_element_is_null_for_an_etf(growth: bool) -> None:
    document = _document(_analysis(growth, ScriptedProvider(), profile=etf_profile()))
    assert document.status.value == "not_applicable"
    assert document.anchor_filing is None
    assert json.loads(_json(document))["anchor_filing"] is None


@STRATEGIES
def test_m7_the_element_is_null_when_every_filing_input_is_overridden(growth: bool) -> None:
    overrides = {"eps_override": 3.0} if growth else {"eps_override": 3.0, "bvps_override": 10.0}
    document = _document(_analysis(growth, ScriptedProvider(), quote_override=None, **overrides))
    assert document.status.value == "ok"
    assert document.anchor_filing is None


@STRATEGIES
def test_m10_the_document_lists_the_years_left_out_and_the_key_is_always_present(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.earlier_basis_year_ending = date(2022, 6, 30)
    document = _document(_analysis(growth, provider))
    assert [item.model_dump(mode="json") for item in document.left_out_years] == [
        {
            "field": "eps",
            "fiscal_year": 2022,
            "period_end": "2022-06-30",
            "reason_code": "earlier_basis",
            "reason": EARLIER_BASIS_MESSAGE,
        }
    ]
    assert document.reason is not None
    assert "FY2022 (ended 2022-06-30)" in document.reason, "the investor sees the reason that names the year"

    clean = json.loads(_json(_document(_analysis(growth, ScriptedProvider()))))
    assert clean["left_out_years"] == []


@STRATEGIES
def test_m4_the_investor_sees_the_year_message_not_the_general_text_of_its_status(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.eps_years_back = 1
    analysis = _analysis(growth, provider)
    document = _document(analysis)
    assert document.reason is not None
    assert document.reason.startswith("eps: The newest fiscal year of diluted EPS ends 2023-06-30, not")
    text = "\n".join(_text(analysis, PresentationMode.CONCISE))
    assert "never calculated from an older year" in text


@STRATEGIES
def test_replay_keeps_the_stale_element_and_a_null_one(growth: bool) -> None:
    encode, decode = (
        (encode_graham_growth, decode_graham_growth) if growth else (encode_graham_number, decode_graham_number)
    )
    stale = _analysis(growth, ScriptedProvider(), effective_as_of=LATE)
    restored = decode(encode(stale))  # type: ignore[arg-type]
    assert _document(restored).model_dump(mode="json") == _document(stale).model_dump(mode="json")
    assert _document(restored).anchor_filing is not None

    overrides = {"eps_override": 3.0} if growth else {"eps_override": 3.0, "bvps_override": 10.0}
    nothing = _analysis(growth, ScriptedProvider(), quote_override=None, **overrides)
    assert _document(decode(encode(nothing))).anchor_filing is None  # type: ignore[arg-type]


def _json(document: object) -> str:
    return strategy_document_json(document)  # type: ignore[arg-type]
