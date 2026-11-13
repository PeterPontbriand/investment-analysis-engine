"""Every non-OK Graham status serves a reason code, and its message is written where the code is set (issue 250).

One parametrized test per strategy runs each non-OK path and checks the status, the code on the assembly and on the
result, the analysis's own ``reason_code`` and the message.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEndUnavailableReason
from investment_analysis_engine.evaluation.fixtures.graham import NOW, SECURITY_ID
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthInputResolver,
    GrowthValueInputAssembly,
)
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis, run_graham_growth_analysis
from investment_analysis_engine.strategies.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberResult,
)
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from tests.analysis.graham_value._anchored import (
    POLICY,
    ScriptedProvider,
    etf_profile,
    no_anchor,
    provider_failure,
    run_growth,
    run_number,
)

PROVIDER_ERROR_MESSAGE = (
    f"Unable to analyze {SECURITY_ID}: the configured provider could not retrieve required security data."
)
UNVERIFIED_MESSAGE = (
    f"Unable to analyze {SECURITY_ID}: no provider-backed security fact or quote was resolved. "
    "Fully override-driven security analysis is not accepted in v0.2."
)


@dataclass(frozen=True)
class Path:
    """One non-OK path: how to reach it and what it serves."""

    status: CalculationStatus
    code: ReasonCode
    message: str
    """The whole message, or its start when ``prefix`` is set."""
    prefix: bool = False


def _scripted(**attributes: object) -> ScriptedProvider:
    provider = ScriptedProvider()
    for name, value in attributes.items():
        setattr(provider, name, value)
    return provider


def _growth_with_negative_growth() -> GrahamGrowthAnalysis:
    """Run Graham Growth with an expected growth that makes the valuation P/E negative."""
    provider = ScriptedProvider()
    return run_graham_growth_analysis(
        resolver=GrahamGrowthInputResolver(provider, cache=None, clock=lambda: NOW),
        ticker=SECURITY_ID,
        eps_basis="three_year_average",
        eps_override=None,
        expected_growth=-50.0,
        aaa_yield_override=4.5,
        quote_override=None,
        as_of=None,
        effective_as_of=NOW,
        use_cache=False,
        policy=POLICY,
    )


NUMBER_PATHS: dict[str, tuple[Callable[[], GrahamNumberAnalysis], Path]] = {
    "etf": (
        lambda: run_number(ScriptedProvider(), profile=etf_profile()),
        Path(
            CalculationStatus.NOT_APPLICABLE,
            ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
            "Graham Number is a company-level valuation method and does not apply directly to an ETF. "
            "No constituent-level or aggregate ETF valuation was performed.",
        ),
    ),
    "anchor_provider_error": (
        lambda: run_number(_scripted(anchor_error=provider_failure())),
        Path(CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR, PROVIDER_ERROR_MESSAGE),
    ),
    "anchor_missing": (
        lambda: run_number(
            _scripted(anchor=no_anchor(AnchorYearEndUnavailableReason.NO_ANCHOR_FILING, "No annual filing was found."))
        ),
        Path(CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.MISSING_FACT, "No annual filing was found."),
    ),
    "input_provider_error": (
        lambda: run_number(_scripted(facts_error=provider_failure()), use_cache=False),
        Path(CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR, PROVIDER_ERROR_MESSAGE),
    ),
    "eps_not_for_the_anchor_year": (
        lambda: run_number(_scripted(eps_years_back=1), use_cache=False),
        Path(
            CalculationStatus.INPUT_UNAVAILABLE,
            ReasonCode.INCOMPATIBLE_PERIOD,
            "Earnings per share is unavailable: ",
            prefix=True,
        ),
    ),
    "bvps_not_for_the_anchor_year": (
        lambda: run_number(_scripted(bvps_years_back=1), use_cache=False),
        Path(
            CalculationStatus.INPUT_UNAVAILABLE,
            ReasonCode.INCOMPATIBLE_PERIOD,
            "Book value per share is unavailable: ",
            prefix=True,
        ),
    ),
    "negative_eps": (
        lambda: run_number(ScriptedProvider(), eps_override=-1.0),
        Path(
            CalculationStatus.NOT_APPLICABLE,
            ReasonCode.NONPOSITIVE_INPUT,
            "Earnings per share is negative (-1.00 (currency unspecified)), so the Graham Number does not apply.",
        ),
    ),
    "zero_bvps": (
        lambda: run_number(ScriptedProvider(), bvps_override=0.0),
        Path(
            CalculationStatus.NOT_APPLICABLE,
            ReasonCode.NONPOSITIVE_INPUT,
            "Book value per common share is zero (0.00 (currency unspecified)), so the Graham Number does not apply.",
        ),
    ),
    "only_overrides": (
        lambda: run_number(ScriptedProvider(), eps_override=4.0, bvps_override=12.0, quote_override=30.0),
        Path(CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.OVERRIDE_ONLY, UNVERIFIED_MESSAGE),
    ),
}

GROWTH_PATHS: dict[str, tuple[Callable[[], GrahamGrowthAnalysis], Path]] = {
    "etf": (
        lambda: run_growth(ScriptedProvider(), profile=etf_profile()),
        Path(
            CalculationStatus.NOT_APPLICABLE,
            ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
            "Graham growth-value method is a company-level valuation method and does not apply directly to an ETF. "
            "No constituent-level or aggregate ETF valuation was performed.",
        ),
    ),
    "anchor_provider_error": (
        lambda: run_growth(_scripted(anchor_error=provider_failure())),
        Path(CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR, PROVIDER_ERROR_MESSAGE),
    ),
    "anchor_missing": (
        lambda: run_growth(
            _scripted(anchor=no_anchor(AnchorYearEndUnavailableReason.NO_ANCHOR_FILING, "No annual filing was found."))
        ),
        Path(CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.MISSING_FACT, "No annual filing was found."),
    ),
    "input_provider_error": (
        lambda: run_growth(_scripted(facts_error=provider_failure()), use_cache=False),
        Path(CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR, PROVIDER_ERROR_MESSAGE),
    ),
    "eps_not_for_the_anchor_year": (
        lambda: run_growth(_scripted(eps_years_back=1), use_cache=False),
        Path(
            CalculationStatus.INPUT_UNAVAILABLE,
            ReasonCode.INCOMPATIBLE_PERIOD,
            "Earnings per share is unavailable: ",
            prefix=True,
        ),
    ),
    "valuation_pe_not_positive": (
        _growth_with_negative_growth,
        Path(
            CalculationStatus.INVALID_INPUT,
            ReasonCode.INVALID_REQUEST,
            "The computed valuation P/E is zero or negative (-91.5), so the value cannot be computed.",
        ),
    ),
    "only_overrides": (
        lambda: run_growth(ScriptedProvider(), eps_override=4.0, quote_override=30.0),
        Path(CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.OVERRIDE_ONLY, UNVERIFIED_MESSAGE),
    ),
}


def _check(analysis: GrahamNumberAnalysis | GrahamGrowthAnalysis, path: Path) -> None:
    """Check the status, the codes and the message of one path."""
    assert analysis.native_status is path.status
    assert analysis.reason_code is path.code
    assembly, result = analysis.assembly, analysis.result
    if assembly.status is CalculationStatus.OK:
        assert assembly.reason_code is None
    else:
        assert assembly.reason_code is path.code
    assert result.reason_code is path.code
    message = result.reason if assembly.status is CalculationStatus.OK else assembly.reason
    assert message is not None
    assert message.startswith(path.message) if path.prefix else message == path.message


@pytest.mark.parametrize("name", list(NUMBER_PATHS))
def test_graham_number_every_non_ok_path_serves_its_code_and_message(name: str) -> None:
    run, path = NUMBER_PATHS[name]
    _check(run(), path)


@pytest.mark.parametrize("name", list(GROWTH_PATHS))
def test_graham_growth_every_non_ok_path_serves_its_code_and_message(name: str) -> None:
    run, path = GROWTH_PATHS[name]
    _check(run(), path)


def test_graham_number_product_overflow_is_invalid_request() -> None:
    """A provider-backed book value and an EPS override too large to multiply is refused as an invalid request."""
    analysis = run_number(ScriptedProvider(), eps_override=sys.float_info.max)
    assert analysis.native_status is CalculationStatus.INVALID_INPUT
    assert analysis.reason_code is ReasonCode.INVALID_REQUEST
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.assembly.reason_code is None
    assert analysis.result.reason_code is ReasonCode.INVALID_REQUEST
    assert analysis.result.reason is not None
    assert "not a valid positive finite value" in analysis.result.reason


@pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
def test_a_successful_analysis_has_no_reason_code(growth: bool) -> None:
    analysis = run_growth(ScriptedProvider()) if growth else run_number(ScriptedProvider())
    assert analysis.native_status is CalculationStatus.OK
    assert analysis.reason_code is None
    assert analysis.assembly.reason_code is None
    assert analysis.result.reason_code is None


@pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
def test_an_unavailable_eps_is_led_by_its_plain_words_not_an_internal_prefix(growth: bool) -> None:
    provider = _scripted(drop_eps_year_ending=date(2022, 6, 30))
    analysis = run_growth(provider, use_cache=False) if growth else run_number(provider, use_cache=False)
    assert analysis.native_status is CalculationStatus.INPUT_UNAVAILABLE
    message = analysis.assembly.reason
    assert message is not None
    assert message.startswith("Earnings per share is unavailable: ")
    assert "eps:" not in message


class TestAssemblyInvariants:
    """A reason code is present exactly when the status is not OK."""

    def test_number_non_ok_without_a_code_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_code is present exactly when"):
            GrahamNumberInputAssembly(status=CalculationStatus.INPUT_UNAVAILABLE, reason="no code")

    def test_number_not_applicable_without_a_code_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_code is present exactly when"):
            GrahamNumberInputAssembly(status=CalculationStatus.NOT_APPLICABLE, reason="no code")

    def test_number_ok_with_a_code_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_code is present exactly when"):
            GrahamNumberInputAssembly(status=CalculationStatus.OK, reason_code=ReasonCode.MISSING_FACT)

    def test_growth_non_ok_without_a_code_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_code is present exactly when"):
            GrowthValueInputAssembly(status=CalculationStatus.PROVIDER_ERROR, reason="no code")

    def test_growth_ok_with_a_code_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_code is present exactly when"):
            GrowthValueInputAssembly(status=CalculationStatus.OK, reason_code=ReasonCode.MISSING_FACT)

    def test_a_result_for_a_failed_assembly_carries_the_assemblys_code(self) -> None:
        result = GrahamNumberResult(
            status=CalculationStatus.PROVIDER_ERROR, reason="x", reason_code=ReasonCode.PROVIDER_ERROR
        )
        assert result.reason_code is ReasonCode.PROVIDER_ERROR
