"""FCF Growth over a series whose older years were reported only on an earlier basis."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.financial.facts import (
    AnnualSeriesFacts,
    FinancialFactRequest,
    FinancialField,
    ProviderFact,
)
from investment_analysis_engine.data.financial.resolver import EARLIER_BASIS_MESSAGE, LeftOutObservation, LeftOutReason
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PRODUCTIVE_ASSETS_CAPITAL_EXPENDITURES_FIELD,
    SEC_PROVIDER_ID,
)
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.codec import decode_fcf_growth, encode_fcf_growth
from investment_analysis_engine.strategies.fcf_growth.input_resolver import (
    ProductionAnnualGrowthSeriesResolver,
    _no_selection_reason,
)
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)
from investment_analysis_engine.strategies.fcf_growth.presenter import (
    build_fcf_growth_document,
    render_fcf_earnings_growth,
)
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    Classification,
    FCFClassificationBasis,
    HistoricalHorizon,
)
from tests._fcf_market_data import CLOCK, fcf_market_data

_YEARS = range(2020, 2026)
_RESTATED = " restated other years (for example after a stock split)"
_OBSERVED = f"reported only before a later filing{_RESTATED}"


class _EarlierBasisProvider(FixtureAnnualFinancialFactsProvider):
    """The fixture series, with some EPS and diluted-share years reported as left out.

    A year before a field's cutoff is earlier-basis. A year in a field's conflict set is conflicting, and every year
    before the newest conflicting one is dropped with it.
    """

    def __init__(
        self,
        facts: tuple[ProviderFact, ...],
        cutoffs: dict[FinancialField, int],
        conflicts: dict[FinancialField, set[int]] | None = None,
    ) -> None:
        super().__init__(facts)
        self.cutoffs = cutoffs
        self.conflicts = conflicts or {}

    def fetch_annual_series(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> AnnualSeriesFacts:
        facts = self.fetch_facts(request, effective_as_of=effective_as_of)
        cutoff = self.cutoffs.get(request.field_name, 0)
        conflict = self.conflicts.get(request.field_name, set())
        newest_conflict = max(conflict, default=0)

        def year(fact: ProviderFact) -> int:
            return fact.fiscal_year or 0

        return AnnualSeriesFacts(
            tuple(fact for fact in facts if year(fact) >= cutoff and year(fact) > newest_conflict),
            tuple(fact for fact in facts if year(fact) < cutoff and year(fact) not in conflict),
            tuple(fact for fact in facts if year(fact) in conflict),
        )


def _run(
    cutoffs: dict[FinancialField, int],
    *,
    conflicts: dict[FinancialField, set[int]] | None = None,
    broader_capex: bool = False,
    horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE,
    basis: FCFClassificationBasis = FCFClassificationBasis.TOTAL_FCF,
) -> FCFEarningsGrowthResult:
    facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(_YEARS))
    if broader_capex:
        facts = tuple(
            replace(fact, provider_field=SEC_PRODUCTIVE_ASSETS_CAPITAL_EXPENDITURES_FIELD)
            if fact.field_name is FinancialField.CAPITAL_EXPENDITURES
            else fact
            for fact in facts
        )
    provider = _EarlierBasisProvider(facts, cutoffs, conflicts)
    annual = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: CLOCK)
    policy = FCFEarningsGrowthPolicy(historical_horizon=horizon, classification_basis=basis)
    return FCFEarningsGrowthAnalyzer(annual, fcf_market_data()).run_analysis(
        "acme",
        AnalysisContext(as_of=None, executed_at=CLOCK, use_cache=False),
        FCFEarningsGrowthConfig(policy=policy, currency="USD"),
    )


_BOTH = {FinancialField.EPS: 2022, FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES: 2022}
_BOTH_WARNING = (
    f"Diluted EPS and weighted-average diluted shares for FY2020–FY2021 were {_OBSERVED}; those years are left out."
)


def test_a_shortened_series_reaches_the_three_year_horizon_under_longest_available() -> None:
    result = _run(_BOTH)

    assert result.execution_status is CalculationStatus.OK
    assert result.used_horizon_fallback is True
    assert (result.selected_horizon_years, result.selected_observation_count) == (3, 4)
    assert [item.period_end.year for item in result.annual_observations] == [2022, 2023, 2024, 2025]
    assert result.classification in (Classification.PASS, Classification.FAIL)


def test_the_left_out_years_are_recorded_for_each_field_and_year() -> None:
    result = _run(_BOTH)

    assert [(item.field, item.fiscal_year, item.period_end, item.reason_code) for item in result.left_out_years] == [
        ("eps", 2020, date(2020, 1, 1), ReasonCode.EARLIER_BASIS),
        ("eps", 2021, date(2021, 1, 1), ReasonCode.EARLIER_BASIS),
        ("weighted_average_diluted_shares", 2020, date(2020, 1, 1), ReasonCode.EARLIER_BASIS),
        ("weighted_average_diluted_shares", 2021, date(2021, 1, 1), ReasonCode.EARLIER_BASIS),
    ]
    assert {item.reason for item in result.left_out_years} == {EARLIER_BASIS_MESSAGE}


def test_nothing_left_out_gives_an_empty_list_and_no_warning() -> None:
    result = _run({})

    assert result.left_out_years == ()
    assert not any("restated" in warning for warning in result.warnings)


def test_the_warning_comes_before_the_horizon_fallback_warning() -> None:
    result = _run(_BOTH)

    assert result.warnings[:2] == (
        _BOTH_WARNING,
        "Automatic horizon selection fell back because five elapsed years were unavailable.",
    )


def test_one_field_left_out_uses_the_singular_wording() -> None:
    result = _run({FinancialField.EPS: 2022})

    assert result.warnings[0] == f"Diluted EPS for FY2020–FY2021 was {_OBSERVED}; those years are left out."
    assert {item.field for item in result.left_out_years} == {"eps"}


def test_fields_with_different_ranges_give_one_clause_each_in_one_warning() -> None:
    result = _run({FinancialField.EPS: 2022, FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES: 2021})

    assert result.warnings[0] == (
        f"Weighted-average diluted shares for FY2020 was {_OBSERVED}; "
        f"diluted EPS for FY2020–FY2021 was {_OBSERVED}; those years are left out."
    )


def test_an_explicit_span_that_needs_the_left_out_years_is_indeterminate_with_earlier_basis() -> None:
    result = _run({FinancialField.EPS: 2022}, horizon=HistoricalHorizon.FIVE_YEARS)

    assert result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.classification is Classification.INDETERMINATE
    assert result.classification_reason_code is ReasonCode.EARLIER_BASIS
    assert result.classification_reason == (
        f"Diluted EPS for FY2020–FY2021 was {_OBSERVED}; 5 elapsed years need FY2020–FY2025."
    )
    assert result.warnings[0] == f"Diluted EPS for FY2020–FY2021 was {_OBSERVED}; those years are left out."


def test_an_explicit_span_names_the_diluted_shares_only_when_the_basis_needs_them() -> None:
    per_share = _run(_BOTH, horizon=HistoricalHorizon.FIVE_YEARS, basis=FCFClassificationBasis.FCF_PER_SHARE)
    total = _run(_BOTH, horizon=HistoricalHorizon.FIVE_YEARS)

    assert per_share.classification_reason is not None
    assert per_share.classification_reason.startswith("Diluted EPS and weighted-average diluted shares for ")
    assert total.classification_reason is not None
    assert total.classification_reason.startswith("Diluted EPS for ")


def test_an_explicit_span_that_the_left_out_years_do_not_decide_keeps_its_own_reason() -> None:
    result = _run({FinancialField.EPS: 2022}, horizon=HistoricalHorizon.THREE_YEARS)

    assert result.execution_status is CalculationStatus.OK
    assert result.classification_reason_code is not ReasonCode.EARLIER_BASIS
    assert [item.fiscal_year for item in result.left_out_years if item.field == "eps"] == [2020, 2021]


def test_the_diagnostics_count_the_earlier_basis_years_per_field() -> None:
    result = _run({FinancialField.EPS: 2022})

    messages = {
        event.field_name: event.message for event in result.diagnostics.events if event.outcome.value == "success"
    }
    assert messages["eps"] == "4 fiscal-year observation(s) resolved; 2 left out as reported only on an earlier basis."
    assert messages["operating_cash_flow"] == "6 fiscal-year observation(s) resolved; 0 left out as ineligible."


def test_the_stored_result_and_its_document_carry_the_left_out_years() -> None:
    result = _run(_BOTH)

    restored = decode_fcf_growth(encode_fcf_growth(result))
    document = build_fcf_growth_document(restored)

    assert restored.left_out_years == result.left_out_years
    assert [(item.field, item.fiscal_year, item.period_end, item.reason_code) for item in document.left_out_years] == [
        (item.field, item.fiscal_year, item.period_end, item.reason_code) for item in result.left_out_years
    ]
    assert build_fcf_growth_document(_run({})).left_out_years == ()


def _left_out(why: LeftOutReason) -> LeftOutObservation:
    return LeftOutObservation(datetime(2020, 1, 1), why, "x")


def test_every_year_on_an_earlier_basis_gives_earlier_basis_not_the_boundary_message() -> None:
    code, reason = _no_selection_reason(FinancialField.EPS, (), (_left_out(LeftOutReason.EARLIER_BASIS),) * 2)

    assert (code, reason) == (ReasonCode.EARLIER_BASIS, EARLIER_BASIS_MESSAGE)


def test_a_year_filed_after_the_boundary_keeps_its_precedence_over_an_earlier_basis_year() -> None:
    code, _ = _no_selection_reason(
        FinancialField.EPS,
        (),
        (_left_out(LeftOutReason.EARLIER_BASIS), _left_out(LeftOutReason.NOT_AVAILABLE_AT_BOUNDARY)),
    )

    assert code is ReasonCode.NOT_AVAILABLE_AS_OF


def test_a_quality_failure_alone_is_still_later_than_the_boundary() -> None:
    code, _ = _no_selection_reason(FinancialField.EPS, (), (_left_out(LeftOutReason.FAILED_QUALITY_CHECK),))

    assert code is ReasonCode.NOT_AVAILABLE_AS_OF


def test_the_year_must_be_the_year_of_its_period_end() -> None:
    result = _run(_BOTH)
    year = result.left_out_years[0]

    with pytest.raises(ValueError, match="year of its period end"):
        replace(year, fiscal_year=year.fiscal_year + 1)


_SHARES = FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
_CONFLICT_ONE = "Diluted EPS for FY2021 has different values in filings filed together; that year is left out."


def test_a_conflicting_year_is_recorded_with_ambiguous_fact_and_warned_about_alone() -> None:
    result = _run({}, conflicts={FinancialField.EPS: {2021}})

    conflicting = [item for item in result.left_out_years if item.reason_code is ReasonCode.AMBIGUOUS_FACT]
    assert [(item.field, item.fiscal_year, item.reason) for item in conflicting] == [
        ("eps", 2021, "Filings filed together give different values for this year; not used.")
    ]
    assert result.warnings[0] == _CONFLICT_ONE
    assert [item.period_end.year for item in result.annual_observations] == [2022, 2023, 2024, 2025]


def test_the_conflict_warning_follows_the_earlier_basis_warning() -> None:
    result = _run({FinancialField.EPS: 2022}, conflicts={FinancialField.EPS: {2021}})

    assert result.warnings[:2] == (
        f"Diluted EPS for FY2020 was {_OBSERVED}; that year is left out.",
        _CONFLICT_ONE,
    )


def test_conflicting_years_of_two_fields_share_one_clause_and_one_ending() -> None:
    result = _run({}, conflicts={FinancialField.EPS: {2021}, _SHARES: {2021}})

    assert result.warnings[0] == (
        "Diluted EPS and weighted-average diluted shares for FY2021 have different values in filings filed "
        "together; that year is left out."
    )


def test_the_per_share_basis_chooses_its_horizon_from_the_periods_that_have_a_per_share_value() -> None:
    result = _run({_SHARES: 2022}, basis=FCFClassificationBasis.FCF_PER_SHARE)

    assert result.execution_status is CalculationStatus.OK
    assert (result.selected_horizon_years, result.selected_observation_count) == (3, 4)
    assert [item.period_end.year for item in result.annual_observations] == [2022, 2023, 2024, 2025]
    assert all(item.free_cash_flow_per_diluted_share is not None for item in result.annual_observations)
    assert {item.field for item in result.left_out_years} == {"weighted_average_diluted_shares"}


def test_the_per_share_basis_fails_with_incompatible_scope_when_too_few_periods_have_a_per_share_value() -> None:
    result = _run({_SHARES: 2024}, basis=FCFClassificationBasis.FCF_PER_SHARE)

    assert result.classification_reason_code is ReasonCode.INCOMPATIBLE_SCOPE
    assert result.classification_reason == (
        "Compatible same-accession diluted-share evidence is unavailable for every annual period."
    )


def test_the_total_basis_ignores_the_missing_per_share_periods() -> None:
    result = _run({_SHARES: 2024})

    assert result.execution_status is CalculationStatus.OK
    assert result.selected_observation_count == 6


def test_the_intangible_assets_limitation_appears_only_when_the_broader_capex_concept_is_used() -> None:
    narrow, broad = _run({}), _run({}, broader_capex=True)
    line = (
        "Limitation: Capital expenditures include purchases of intangible assets, which the filer reports together "
        "with property and equipment, so free cash flow may be lower than with property and equipment alone."
    )

    for mode in (PresentationMode.CONCISE, PresentationMode.DETAILS):
        assert line not in render_fcf_earnings_growth(narrow, mode).splitlines()
        lines = render_fcf_earnings_growth(broad, mode).splitlines()
        assert line in lines
        assert lines[lines.index(line) - 1].startswith("Limitation: Historical financial strength")
    assert len(build_fcf_growth_document(narrow).limitations) == 1
    document = build_fcf_growth_document(broad)
    assert document.limitations[1] == line.removeprefix("Limitation: ")
    assert {item.normalized_capital_expenditures.provider_field for item in document.annual_observations} == {
        SEC_PRODUCTIVE_ASSETS_CAPITAL_EXPENDITURES_FIELD
    }
