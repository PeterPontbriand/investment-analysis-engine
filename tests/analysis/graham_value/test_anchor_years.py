"""Graham Number and Graham Growth Value take their input years from the shared anchor filing (decision record A.19).

Each test names its decision (M1 to M11) and fails without that decision's change.
"""

from __future__ import annotations

from datetime import date

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import LeftOutYear
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache
from investment_analysis_engine.data.financial.facts import FinancialField
from investment_analysis_engine.data.financial.resolver import EARLIER_BASIS_MESSAGE
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEndUnavailableReason
from investment_analysis_engine.evaluation.fixtures.graham import NOW
from investment_analysis_engine.strategies.graham_growth.calculation import GrowthValueInputAssembly
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputAssembly
from tests.analysis.graham_value._anchored import (
    ANCHOR_YEAR_END,
    LATE,
    ScriptedProvider,
    anchor_for,
    equity_profile,
    etf_profile,
    no_anchor,
    provider_failure,
    requested_fields,
    run_growth,
    run_number,
)

type Assembly = GrahamNumberInputAssembly | GrowthValueInputAssembly

STRATEGIES = pytest.mark.parametrize("growth", [False, True], ids=["graham_number", "graham_growth"])
METHOD = {False: "Graham Number", True: "Graham Growth Value"}
FIXTURE_FILING_DATE = date(2024, 9, 13)


def _assembly(growth: bool, provider: ScriptedProvider, **kwargs: object) -> Assembly:
    """Run one strategy and return its assembly."""
    if growth:
        return run_growth(provider, **kwargs).assembly  # type: ignore[arg-type]
    return run_number(provider, **kwargs).assembly  # type: ignore[arg-type]


# --- M1 and the unchanged happy path ---------------------------------------------------------------------------


@STRATEGIES
def test_m1_a_run_at_the_fixtures_anchor_succeeds_and_reports_that_anchor(growth: bool) -> None:
    provider = ScriptedProvider()
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.OK
    assert assembly.anchor_filing is not None
    assert assembly.anchor_filing.year_end == ANCHOR_YEAR_END
    assert assembly.anchor_filing.filing_date == FIXTURE_FILING_DATE
    assert not assembly.anchor_filing.stale
    assert provider.anchor_requests == 1
    assert provider.scopes_opened == 1


@STRATEGIES
def test_m1_the_inputs_are_requested_after_the_anchor_and_through_the_strategys_own_resolvers(growth: bool) -> None:
    provider = ScriptedProvider()
    _assembly(growth, provider, use_cache=False)
    assert provider.anchor_requests == 1
    assert requested_fields(provider)[0] is FinancialField.EPS


# --- M2: the anchor ---------------------------------------------------------------------------------------------


@STRATEGIES
def test_m2_a_provider_failure_resolving_the_anchor_is_a_provider_error_recorded_against_anchor_year_end(
    growth: bool,
) -> None:
    provider = ScriptedProvider()
    provider.anchor_error = provider_failure()
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.PROVIDER_ERROR
    assert assembly.provider_failure is not None
    assert assembly.provider_failure.input == "anchor_year_end"
    assert assembly.reason == (
        "Unable to analyze SYNTH: the configured provider could not retrieve required security data."
    )
    assert assembly.reason_code is ReasonCode.PROVIDER_ERROR
    assert assembly.anchor_filing is None
    assert provider.fact_requests == []


@STRATEGIES
@pytest.mark.parametrize("reason", list(AnchorYearEndUnavailableReason))
def test_m2_with_no_anchor_for_any_reason_the_result_is_input_unavailable_with_the_anchors_message(
    growth: bool, reason: AnchorYearEndUnavailableReason
) -> None:
    provider = ScriptedProvider()
    provider.anchor = no_anchor(reason, f"The anchor filing is unavailable: {reason.value}.")
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason == f"The anchor filing is unavailable: {reason.value}."
    assert assembly.reason_code is (
        ReasonCode.NOT_AVAILABLE_AS_OF
        if reason is AnchorYearEndUnavailableReason.ACCEPTED_AFTER_BOUNDARY
        else ReasonCode.MISSING_FACT
    )
    assert assembly.anchor_filing is None
    assert assembly.eps is None
    assert provider.fact_requests == [], "the newest facts are never used in place of the anchor"


@STRATEGIES
def test_m2_an_etf_is_not_applicable_before_any_request_with_a_null_anchor(growth: bool) -> None:
    provider = ScriptedProvider()
    assembly = _assembly(growth, provider, profile=etf_profile())
    assert assembly.status is CalculationStatus.NOT_APPLICABLE
    assert assembly.anchor_filing is None
    assert provider.anchor_requests == 0
    assert provider.fact_requests == []
    assert provider.scopes_opened == 0


# --- M4: the year of each input ---------------------------------------------------------------------------------


@STRATEGIES
def test_m4_eps_that_does_not_end_on_the_anchors_year_end_is_unavailable_and_never_an_older_year(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.anchor = anchor_for(date(2025, 6, 30))
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason == (
        "Earnings per share is unavailable: The newest fiscal year of diluted EPS ends 2024-06-30, not the anchor "
        "filing's fiscal year-end "
        f"2025-06-30; the {METHOD[growth]} is never calculated from an older year."
    )
    assert assembly.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
    assert assembly.eps is None


def test_m4_book_value_that_does_not_end_on_the_anchors_year_end_is_unavailable() -> None:
    provider = ScriptedProvider()
    provider.bvps_years_back = 1
    assembly = run_number(provider).assembly
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason == (
        "Book value per share is unavailable: The newest book value per common share is for the fiscal year ended "
        "2023-06-30, not the anchor "
        "filing's fiscal year-end 2024-06-30; the Graham Number is never calculated from an older year."
    )
    assert assembly.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
    assert assembly.bvps is None
    assert assembly.eps is not None, "the aligned EPS stays resolved"


def test_m4_the_single_year_eps_basis_of_graham_growth_is_checked_too() -> None:
    provider = ScriptedProvider()
    provider.serve_single_year_eps = True
    provider.anchor = anchor_for(date(2025, 6, 30))
    assembly = run_growth(provider, eps_basis="fiscal_year").assembly
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason is not None
    assert assembly.reason.startswith(
        "Earnings per share is unavailable: The newest fiscal year of diluted EPS ends 2024-06-30, not"
    )


@STRATEGIES
def test_m4_a_year_that_ends_one_day_off_is_unavailable_because_there_is_no_tolerance(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.anchor = anchor_for(date(2024, 7, 1))
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason is not None
    assert "anchor filing's fiscal year-end 2024-07-01" in assembly.reason


# --- M5: consecutive years --------------------------------------------------------------------------------------


@STRATEGIES
def test_m5_three_eps_years_with_a_gap_are_unavailable_and_the_missing_year_is_named(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.oldest_eps_years_back = 1  # the years ended 2021, 2023 and 2024: none ends 2022-06-30
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason == (
        "Earnings per share is unavailable: The fiscal years of diluted EPS are not consecutive: none ends 2022-06-30, "
        "between the years ended "
        "2021-06-30 and 2023-06-30."
    )
    assert assembly.reason_code is ReasonCode.MISSING_FACT
    assert assembly.eps is None


# --- M7: overrides ----------------------------------------------------------------------------------------------


def test_m7_an_overridden_eps_is_exempt_but_the_book_value_still_resolves_the_anchor() -> None:
    provider = ScriptedProvider()
    provider.anchor = anchor_for(date(2025, 6, 30))
    analysis = run_number(provider, eps_override=3.0)
    assembly = analysis.assembly
    assert provider.anchor_requests == 1
    assert assembly.anchor_filing is not None
    assert assembly.anchor_filing.year_end == date(2025, 6, 30)
    # EPS is exempt from the year check; the book value of the older year is not.
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason is not None
    assert assembly.reason.startswith(
        "Book value per share is unavailable: The newest book value per common share is for the fiscal year ended"
    )


def test_m7_with_both_filing_inputs_overridden_no_anchor_is_requested_and_it_is_null() -> None:
    provider = ScriptedProvider()
    analysis = run_number(provider, eps_override=3.0, bvps_override=10.0)
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.assembly.anchor_filing is None
    assert provider.anchor_requests == 0
    assert provider.scopes_opened == 1, "the plain analysis scope stays open"
    assert FinancialField.EPS not in requested_fields(provider)
    assert FinancialField.BVPS not in requested_fields(provider)


def test_m7_graham_growth_with_eps_overridden_makes_no_anchor_request() -> None:
    provider = ScriptedProvider()
    analysis = run_growth(provider, eps_override=3.0)
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.assembly.anchor_filing is None
    assert provider.anchor_requests == 0
    assert provider.scopes_opened == 1


def test_m7_an_override_without_a_year_is_not_a_year_mismatch_for_graham_growth() -> None:
    provider = ScriptedProvider()
    provider.anchor = anchor_for(date(2030, 6, 30))
    analysis = run_growth(provider, eps_override=3.0)
    assert analysis.assembly.status is CalculationStatus.OK


# --- M8: the stale anchor ---------------------------------------------------------------------------------------


@STRATEGIES
def test_m8_a_stale_anchor_leaves_the_status_and_fills_the_element(growth: bool) -> None:
    fresh = _assembly(growth, ScriptedProvider(), effective_as_of=NOW)
    stale = _assembly(growth, ScriptedProvider(), effective_as_of=LATE)
    assert fresh.status is stale.status is CalculationStatus.OK
    assert fresh.anchor_filing is not None
    assert not fresh.anchor_filing.stale
    assert stale.anchor_filing is not None
    assert stale.anchor_filing.stale
    assert stale.anchor_filing.next_report_due == date(2025, 10, 20)


@STRATEGIES
def test_m8_the_element_is_reported_on_a_year_mismatch_result(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.anchor = anchor_for(date(2024, 7, 1))  # one day after the facts' year, and overdue at LATE
    assembly = _assembly(growth, provider, effective_as_of=LATE)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.anchor_filing is not None
    assert assembly.anchor_filing.stale


@STRATEGIES
def test_m8_the_element_is_reported_on_a_provider_error_result_after_the_anchor(growth: bool) -> None:
    failing = ScriptedProvider()
    failing.facts_error = provider_failure()
    assembly = _assembly(growth, failing, effective_as_of=LATE)
    assert assembly.status is CalculationStatus.PROVIDER_ERROR
    assert assembly.provider_failure is not None
    assert assembly.provider_failure.input == "eps"
    assert assembly.anchor_filing is not None
    assert assembly.anchor_filing.stale


# --- M10: left-out years ----------------------------------------------------------------------------------------


@STRATEGIES
def test_m10_an_eps_series_short_because_of_a_restatement_names_each_left_out_year(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.earlier_basis_year_ending = date(2022, 6, 30)
    assembly = _assembly(growth, provider)
    assert assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.reason is not None
    assert "found 2 distinct period(s), need 3" in assembly.reason
    assert f"FY2022 (ended 2022-06-30): {EARLIER_BASIS_MESSAGE}" in assembly.reason
    assert assembly.reason_code is ReasonCode.EARLIER_BASIS
    assert assembly.left_out_years == (
        LeftOutYear("eps", 2022, date(2022, 6, 30), ReasonCode.EARLIER_BASIS, EARLIER_BASIS_MESSAGE),
    )


@STRATEGIES
def test_m10_a_run_that_leaves_no_year_out_has_none_listed(growth: bool) -> None:
    assert _assembly(growth, ScriptedProvider()).left_out_years == ()


@STRATEGIES
def test_m10_graham_never_averages_fewer_than_three_years(growth: bool) -> None:
    provider = ScriptedProvider()
    provider.earlier_basis_year_ending = date(2022, 6, 30)
    assembly = _assembly(growth, provider)
    assert assembly.eps is None
    assert assembly.status is not CalculationStatus.OK


# --- the boundary the cache keys use ---------------------------------------------------------------------------


@STRATEGIES
def test_a_cached_run_at_the_same_anchor_still_hits_the_cache(growth: bool) -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    first = ScriptedProvider()
    _assembly(growth, first, cache=cache)
    second = ScriptedProvider()
    assembly = _assembly(growth, second, cache=cache)
    assert assembly.status is CalculationStatus.OK
    assert FinancialField.EPS not in requested_fields(second)


# --- a fully overridden run keeps share-unit verification ------------------------------------------------------------


def test_a_fully_overridden_graham_number_run_with_a_quote_verifies_the_share_unit_inside_a_snapshot() -> None:
    provider = ScriptedProvider()
    analysis = run_number(provider, eps_override=3.0, bvps_override=10.0, profile=equity_profile())
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.assembly.anchor_filing is None
    assert provider.anchor_requests == 0
    assert provider.unit_requests == [True], "the plain analysis scope is open when the share unit is verified"


def test_a_fully_overridden_graham_growth_run_with_a_quote_verifies_the_share_unit_inside_a_snapshot() -> None:
    provider = ScriptedProvider()
    analysis = run_growth(provider, eps_override=3.0, profile=equity_profile())
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.assembly.anchor_filing is None
    assert provider.anchor_requests == 0
    assert provider.unit_requests == [True], "the plain analysis scope is open when the share unit is verified"
