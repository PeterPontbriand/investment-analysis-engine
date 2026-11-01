"""The Piotroski analyzer: Apple's worked example and Monster's partial score checked independently, and every outcome.

Expected values are written here from the raw integers of the captured Company Facts, as exact fractions; the
calculation and the analyzer never produce them.
"""

import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from fractions import Fraction

import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, ConfigFreeAnalyzer
from investment_analysis_engine.analysis.shared.applicability import (
    Applicability,
    IndustryClass,
    applicability_of,
)
from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable, Operand
from investment_analysis_engine.analysis.shared.metric_inputs import YearEnds
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import (
    GOLDEN_ETF_TICKER,
    fixture_known_etf_profile,
)
from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import HeaderFetcher, StatementsFetcher
from investment_analysis_engine.strategies.piotroski import analyzer as analyzer_module
from investment_analysis_engine.strategies.piotroski.analyzer import (
    PIOTROSKI_SECTOR_GATE,
    PiotroskiAnalyzer,
    PiotroskiResult,
    _shared_taxonomy,
)
from investment_analysis_engine.strategies.piotroski.codec import encode_piotroski
from investment_analysis_engine.strategies.piotroski.vocabulary import CheckOutcome, Completeness
from tests.analysis.piotroski._statements_rig import CLOCK, adapter_of, analyzer_of, run, without_facts

AAPL_AS_OF = datetime(2025, 1, 15, tzinfo=UTC)
PASS, FAIL, UNAVAILABLE = CheckOutcome.PASS, CheckOutcome.FAIL, CheckOutcome.UNAVAILABLE

# The raw integers of Apple's captured Company Facts: fiscal years 2024-09-28 (t), 2023-09-30 (t-1), 2022-09-24 (t-2).
APPLE: dict[str, int] = {
    "assets_t": 364_980_000_000,
    "assets_t1": 352_583_000_000,
    "assets_t2": 352_755_000_000,
    "net_income_t": 93_736_000_000,
    "net_income_t1": 96_995_000_000,
    "cfo_t": 118_254_000_000,
    "sales_t": 391_035_000_000,
    "sales_t1": 383_285_000_000,
    "gross_profit_t": 180_683_000_000,
    "gross_profit_t1": 169_148_000_000,
    "debt_t": 96_662_000_000,
    "debt_t1": 105_103_000_000,
    "current_assets_t": 152_987_000_000,
    "current_assets_t1": 143_566_000_000,
    "current_liabilities_t": 176_392_000_000,
    "current_liabilities_t1": 145_308_000_000,
    "shares_t": 15_116_786_000,
    "shares_t1": 15_550_061_000,
}
# Monster's, fiscal years 2025-12-31 (t), 2024-12-31 (t-1), 2023-12-31 (t-2). It tags no net income, and it tags no debt
# at 2025-12-31 and reports no interest expense, so its long-term debt there is zero.
MONSTER: dict[str, int] = {
    "assets_t": 9_988_945_000,
    "assets_t1": 7_719_089_000,
    "assets_t2": 9_686_522_000,
    "cfo_t": 2_098_177_000,
    "sales_t": 8_294_343_000,
    "sales_t1": 7_492_709_000,
    "gross_profit_t": 4_632_195_000,
    "gross_profit_t1": 4_048_878_000,
    "debt_t": 0,
    "debt_t1": 373_951_000,
    "current_assets_t": 5_361_084_000,
    "current_assets_t1": 3_641_504_000,
    "current_liabilities_t": 1_447_780_000,
    "current_liabilities_t1": 1_097_519_000,
    "shares_t": 978_113_000,
    "shares_t1": 973_079_000,
}


def ratios(result: PiotroskiResult, number: int) -> dict[str, float]:
    """Return the ratios test ``number`` compared, by name."""
    assert result.f_score is not None
    return {item.name: item.result.value for item in result.f_score.tests[number - 1].ratios if item.result.value}


def outcomes(result: PiotroskiResult) -> tuple[CheckOutcome, ...]:
    """Return the nine outcomes in order."""
    assert result.f_score is not None
    return tuple(test.outcome for test in result.f_score.tests)


def near(value: float, exact: Fraction) -> bool:
    """Return whether ``value`` is the float nearest ``exact``."""
    return value == float(exact)


def test_apple_scores_seven_of_nine_and_every_ratio_is_the_independent_one() -> None:
    """The worked example: the outcomes and the ratios of each test, from the raw integers."""
    a = APPLE
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.execution_status is CalculationStatus.OK
    assert result.f_score is not None
    assert result.f_score.score.value == 7.0
    assert result.f_score.completeness is Completeness.COMPLETE
    assert result.f_score.available_count == 9
    assert outcomes(result) == (PASS, PASS, FAIL, PASS, PASS, FAIL, PASS, PASS, PASS)
    assert near(ratios(result, 1)["roa_t"], Fraction(a["net_income_t"], a["assets_t1"]))
    assert near(ratios(result, 2)["cfo_over_assets_t"], Fraction(a["cfo_t"], a["assets_t1"]))
    assert near(ratios(result, 3)["roa_t1"], Fraction(a["net_income_t1"], a["assets_t2"]))
    assert near(
        ratios(result, 5)["leverage_t"], Fraction(a["debt_t"]) / ((Fraction(a["assets_t"]) + a["assets_t1"]) / 2)
    )
    assert near(
        ratios(result, 5)["leverage_t1"], Fraction(a["debt_t1"]) / ((Fraction(a["assets_t1"]) + a["assets_t2"]) / 2)
    )
    assert near(ratios(result, 6)["current_ratio_t"], Fraction(a["current_assets_t"], a["current_liabilities_t"]))
    assert near(ratios(result, 6)["current_ratio_t1"], Fraction(a["current_assets_t1"], a["current_liabilities_t1"]))
    assert near(ratios(result, 8)["gross_margin_t"], Fraction(a["gross_profit_t"], a["sales_t"]))
    assert near(ratios(result, 8)["gross_margin_t1"], Fraction(a["gross_profit_t1"], a["sales_t1"]))
    assert near(ratios(result, 9)["turnover_t"], Fraction(a["sales_t"], a["assets_t1"]))
    assert near(ratios(result, 9)["turnover_t1"], Fraction(a["sales_t1"], a["assets_t2"]))
    operands = {item.name: item.input.value for item in result.f_score.tests[6].operands}
    assert operands == {"shares_t": a["shares_t"], "shares_t1": a["shares_t1"]}


def test_apple_names_its_anchor_filing_class_taxonomy_and_source_filings() -> None:
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.anchor is not None
    assert (result.anchor.year_end, result.anchor.accession, result.anchor.form) == (
        date(2024, 9, 28),
        "0000320193-24-000123",
        "10-K",
    )
    assert result.anchor.filing_date == date(2024, 11, 1)
    assert result.industry_class is IndustryClass.MANUFACTURER
    assert result.industry_class_unknown is None
    assert result.taxonomy == "us-gaap"
    assert result.warnings == ()
    assert {item.accession for item in result.source_filings} == {"0000320193-23-000106", "0000320193-24-000123"}
    assert (result.schema_version, result.method_version) == (1, 1)


def test_monster_is_a_partial_score_of_five_of_six_with_net_income_tests_unavailable() -> None:
    m = MONSTER
    result = run("mnst", as_of=datetime(2026, 3, 31, tzinfo=UTC))
    assert result.execution_status is CalculationStatus.OK
    assert result.f_score is not None
    assert result.f_score.score.value == 5.0
    assert result.f_score.completeness is Completeness.PARTIAL
    assert (result.f_score.available_count, result.f_score.unavailable_tests) == (6, (1, 3, 4))
    assert outcomes(result) == (UNAVAILABLE, PASS, UNAVAILABLE, UNAVAILABLE, PASS, PASS, FAIL, PASS, PASS)
    for number in (1, 3, 4):
        test = result.f_score.tests[number - 1]
        assert test.reason_code is ReasonCode.MISSING_FACT
        assert "net income" in (test.reason or "").lower()
    assert near(ratios(result, 2)["cfo_over_assets_t"], Fraction(m["cfo_t"], m["assets_t1"]))
    assert ratios(result, 5).get("leverage_t", 0.0) == 0.0
    assert near(
        ratios(result, 5)["leverage_t1"], Fraction(m["debt_t1"]) / ((Fraction(m["assets_t1"]) + m["assets_t2"]) / 2)
    )
    assert near(ratios(result, 6)["current_ratio_t"], Fraction(m["current_assets_t"], m["current_liabilities_t"]))
    assert near(ratios(result, 8)["gross_margin_t1"], Fraction(m["gross_profit_t1"], m["sales_t1"]))
    assert near(ratios(result, 9)["turnover_t1"], Fraction(m["sales_t1"], m["assets_t2"]))
    assert (result.anchor.accession if result.anchor else None) == "0001104659-26-020831"


def test_the_gate_is_applicable_with_a_warning_for_a_financial_issuer_and_refuses_no_class() -> None:
    assert PIOTROSKI_SECTOR_GATE.gated is False
    assert PIOTROSKI_SECTOR_GATE.not_applicable == frozenset()
    assert PIOTROSKI_SECTOR_GATE.warn == frozenset({IndustryClass.FINANCIAL})
    outcomes_by_class = {item: applicability_of(PIOTROSKI_SECTOR_GATE, item).outcome for item in IndustryClass}
    assert outcomes_by_class == {
        IndustryClass.FINANCIAL: Applicability.APPLIES_WITH_WARNING,
        IndustryClass.UTILITY: Applicability.APPLIES,
        IndustryClass.MANUFACTURER: Applicability.APPLIES,
        IndustryClass.OTHER: Applicability.APPLIES,
    }
    assert applicability_of(PIOTROSKI_SECTOR_GATE, None).outcome is Applicability.APPLIES


def test_a_financial_issuer_runs_and_carries_the_warning_while_other_classes_carry_none() -> None:
    jpm = run("jpm")
    assert jpm.industry_class is IndustryClass.FINANCIAL
    assert jpm.execution_status is CalculationStatus.OK
    assert len(jpm.warnings) == 1
    assert "non-financial firms" in jpm.warnings[0]
    assert jpm.f_score is not None
    assert jpm.f_score.tests[5].outcome is UNAVAILABLE  # current assets are not tagged by a bank
    assert jpm.f_score.tests[7].outcome is UNAVAILABLE  # nor is gross profit or the cost of revenue
    for stem, expected in (
        ("aapl", IndustryClass.MANUFACTURER),
        ("duk", IndustryClass.UTILITY),
        ("sap", IndustryClass.OTHER),
    ):
        other = run(stem)
        assert other.industry_class is expected
        assert other.warnings == ()


def test_an_unknown_industry_class_runs_and_says_why() -> None:
    result = run("aapl", adapter=adapter_of("aapl", header=HeaderFetcher("not a filing header")))
    assert result.industry_class is None
    assert result.industry_class_unknown is not None
    assert result.industry_class_unknown.reason_code is ReasonCode.INDUSTRY_CLASS_UNKNOWN
    assert result.execution_status is CalculationStatus.OK
    assert result.warnings == (result.industry_class_unknown.reason,)
    assert result.f_score is not None
    assert result.f_score.score.value == 7.0


def test_an_etf_is_not_applicable_and_reads_no_statement() -> None:
    class Refusing(StatementsFetcher):
        calls = 0

        def __call__(
            self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
        ) -> object:
            del url, headers, not_found, provider_id
            Refusing.calls += 1
            raise AssertionError("an ETF reads no statement")

    adapter = adapter_of("aapl", fetcher=Refusing("aapl"))
    context = AnalysisContext(
        as_of=None, executed_at=CLOCK, use_cache=True, instrument_profile=fixture_known_etf_profile()
    )
    result = analyzer_of(adapter).run_analysis(GOLDEN_ETF_TICKER, context)
    assert Refusing.calls == 0
    assert result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert result.reason_code is ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE
    assert result.f_score is None
    assert result.input_failure is None


def test_an_instrument_profile_of_another_ticker_is_refused() -> None:
    context = AnalysisContext(
        as_of=None, executed_at=CLOCK, use_cache=True, instrument_profile=fixture_known_etf_profile()
    )
    with pytest.raises(ValueError, match="does not match"):
        analyzer_of(adapter_of("aapl")).run_analysis("AAPL", context)


def test_a_boundary_before_the_first_filing_runs_the_calculation_on_the_anchors_reason() -> None:
    result = run("aapl", as_of=datetime(2022, 6, 1, tzinfo=UTC))
    assert result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert result.anchor is None
    assert result.f_score is not None
    assert len(result.f_score.tests) == 9
    assert set(outcomes(result)) == {UNAVAILABLE}
    assert {test.reason_code for test in result.f_score.tests} == {ReasonCode.NOT_AVAILABLE_AS_OF}
    assert result.f_score.score.status is MetricStatus.UNAVAILABLE
    assert result.f_score.completeness is None
    assert result.taxonomy is None


def test_a_boundary_between_filings_scores_the_year_it_admits_and_never_a_later_one() -> None:
    result = run("aapl", as_of=datetime(2023, 12, 1, tzinfo=UTC))
    assert result.anchor is not None
    assert (result.anchor.year_end, result.anchor.accession) == (date(2023, 9, 30), "0000320193-23-000106")
    assert result.f_score is not None
    latest = max(
        operand.input.observation_period_end
        for test in result.f_score.tests
        for operand in test.operands
        if operand.input.observation_period_end is not None
    )
    assert latest.date() == date(2023, 9, 30)
    assert all(item.accession != "0000320193-24-000123" for item in result.source_filings)


def _years(prior: date | InputUnavailable, second: date | InputUnavailable) -> YearEnds:
    return YearEnds(date(2024, 9, 28), prior, second)


def test_an_unavailable_prior_year_keeps_nine_tests_and_each_operand_of_that_year_carries_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = InputUnavailable(ReasonCode.INCOMPATIBLE_PERIOD, "The year ending 2024-09-28 began 20 days earlier.")
    monkeypatch.setattr(analyzer_module, "resolve_year_ends", lambda *_a, **_k: _years(reason, reason))
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.f_score is not None
    assert len(result.f_score.tests) == 9
    # Tests 1, 2, 3, 5, 6, 7, 8 and 9 need a prior year; test 4 needs only the year t.
    assert result.f_score.unavailable_tests == (1, 2, 3, 5, 6, 7, 8, 9)
    assert outcomes(result)[3] is PASS
    for number in result.f_score.unavailable_tests:
        test = result.f_score.tests[number - 1]
        assert test.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
        assert "The year ending 2024-09-28 began 20 days earlier." in (test.reason or "")
    assert result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert any("Fiscal year-end t-1: unavailable" in note for note in result.diagnostics)


def test_an_unavailable_second_prior_year_leaves_exactly_the_tests_that_need_it_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = InputUnavailable(ReasonCode.MISSING_FACT, "None of net_income reports a completed annual period.")
    prior = date(2023, 9, 30)
    monkeypatch.setattr(analyzer_module, "resolve_year_ends", lambda *_a, **_k: _years(prior, reason))
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.f_score is not None
    assert result.f_score.unavailable_tests == (3, 5, 9)
    assert result.f_score.available_count == 6
    assert result.f_score.completeness is Completeness.PARTIAL
    assert result.execution_status is CalculationStatus.OK
    for number in (3, 5, 9):
        assert result.f_score.tests[number - 1].reason_code is ReasonCode.MISSING_FACT


def test_a_missing_critical_input_is_an_unavailable_test_never_a_fail_and_never_zero() -> None:
    fetcher = without_facts("aapl", concepts={"NetCashProvidedByUsedInOperatingActivities"})
    result = run("aapl", as_of=AAPL_AS_OF, adapter=adapter_of("aapl", fetcher=fetcher))
    assert result.f_score is not None
    assert result.f_score.unavailable_tests == (2, 4)
    assert all(result.f_score.tests[number - 1].reason_code is ReasonCode.MISSING_FACT for number in (2, 4))
    assert result.f_score.score.value == 5.0  # the seven passes less tests 2 and 4, which were two of them
    assert result.execution_status is CalculationStatus.OK


def test_fewer_than_six_available_tests_is_input_unavailable_without_a_score() -> None:
    fetcher = without_facts(
        "aapl",
        concepts={
            "NetCashProvidedByUsedInOperatingActivities",
            "GrossProfit",
            "CostOfGoodsAndServicesSold",
            "AssetsCurrent",
        },
    )
    result = run("aapl", as_of=AAPL_AS_OF, adapter=adapter_of("aapl", fetcher=fetcher))
    assert result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.INSUFFICIENT_TESTS
    assert result.f_score is not None
    assert result.f_score.score.status is MetricStatus.UNAVAILABLE
    assert result.f_score.completeness is None
    assert result.f_score.available_count == 5


class _Down(StatementsFetcher):
    """A fetcher whose Company Facts request fails with a classified provider failure."""

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        if "/companyfacts/" in url:
            raise FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
        return super().__call__(url, headers=headers, not_found=not_found, provider_id=provider_id)


def test_a_provider_failure_stops_the_assembly_and_the_result_holds_the_failure_and_no_tests() -> None:
    result = run("aapl", adapter=adapter_of("aapl", fetcher=_Down("aapl")))
    assert result.execution_status is CalculationStatus.PROVIDER_ERROR
    assert result.f_score is None
    assert result.input_failure is not None
    assert result.reason_code is ReasonCode.PROVIDER_ERROR
    assert result.provider_failure == ProviderFailureRecord(
        ProviderFailureKind.UNREACHABLE, "sec_edgar", "anchor_year_end"
    )
    assert result.anchor is None
    assert result.industry_class is None


def test_the_result_refuses_fields_that_disagree_with_its_status() -> None:
    ok = run("aapl", as_of=AAPL_AS_OF)
    with pytest.raises(ValueError, match="reason code is set exactly when"):
        replace(ok, reason_code=ReasonCode.MISSING_FACT, reason="x")
    with pytest.raises(ValueError, match="tests are held exactly when"):
        replace(ok, f_score=None)
    with pytest.raises(ValueError, match="provider failure is held exactly when"):
        replace(
            ok,
            f_score=None,
            execution_status=CalculationStatus.PROVIDER_ERROR,
            reason_code=ReasonCode.PROVIDER_ERROR,
            reason="x",
        )


def test_the_analyzer_is_the_config_free_form_and_is_called_with_the_ticker_and_context_only() -> None:
    assert issubclass(PiotroskiAnalyzer, ConfigFreeAnalyzer)
    result = analyzer_of(adapter_of("aapl")).run_analysis(
        "  aapl ", AnalysisContext(as_of=AAPL_AS_OF, executed_at=CLOCK, use_cache=False)
    )
    assert result.ticker == "AAPL"
    assert result.requested_as_of == AAPL_AS_OF
    assert result.effective_as_of == AAPL_AS_OF


def test_an_effective_time_without_a_timezone_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        analyzer_of(adapter_of("aapl")).run_analysis(
            "AAPL", AnalysisContext(as_of=None, executed_at=datetime(2026, 1, 1), use_cache=True)
        )


def test_the_result_does_not_depend_on_the_order_the_fields_are_requested_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shuffled field order gives the identical result: operands arrive keyed by name and every test is emitted once."""
    forward = encode_piotroski(run("aapl", as_of=AAPL_AS_OF))
    monkeypatch.setattr(analyzer_module, "_BALANCE_FIELDS", tuple(reversed(analyzer_module._BALANCE_FIELDS)))
    monkeypatch.setattr(analyzer_module, "_ANNUAL_FIELDS", tuple(reversed(analyzer_module._ANNUAL_FIELDS)))
    assert encode_piotroski(run("aapl", as_of=AAPL_AS_OF)) == forward
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.f_score is not None
    assert [test.number for test in result.f_score.tests] == list(range(1, 10))


def test_an_ifrs_filer_has_long_term_debt_and_dilution_unavailable_and_records_its_taxonomy() -> None:
    result = run("sap")
    assert result.taxonomy == "ifrs-full"
    assert result.f_score is not None
    assert result.f_score.unavailable_tests == (5, 7)
    assert result.f_score.tests[4].reason_code is ReasonCode.UNSUPPORTED_MAPPING
    assert result.f_score.completeness is Completeness.PARTIAL


def test_the_taxonomy_is_recorded_only_when_every_operand_states_the_same_one() -> None:
    result = run("aapl", as_of=AAPL_AS_OF)
    assert result.f_score is not None
    assert _shared_taxonomy(result.f_score) == "us-gaap"
    first = result.f_score.tests[0]
    changed = replace(first.operands[0].input, provider_field="ifrs-full:ProfitLoss")
    tests = (
        replace(first, operands=(Operand(first.operands[0].name, changed), *first.operands[1:])),
        *result.f_score.tests[1:],
    )
    assert _shared_taxonomy(replace(result.f_score, tests=tests)) is None
    unstated = replace(first.operands[0].input, provider_field="not-a-concept")
    tests = (
        replace(first, operands=(Operand(first.operands[0].name, unstated), *first.operands[1:])),
        *result.f_score.tests[1:],
    )
    assert _shared_taxonomy(replace(result.f_score, tests=tests)) is None


@pytest.mark.parametrize("stem", ["aapl", "mnst", "jpm", "sap"])
def test_no_reason_message_names_an_internal_operand_or_an_underscore_joined_identifier(stem: str) -> None:
    result = run(stem, as_of=AAPL_AS_OF if stem == "aapl" else None)
    assert result.f_score is not None
    reasons = [test.reason for test in result.f_score.tests if test.reason is not None]
    reasons += [result.reason or "", *result.warnings, *result.diagnostics[:0]]
    keys = {operand.name for test in result.f_score.tests for operand in test.operands}
    for reason in reasons:
        assert not re.search(r"[A-Za-z0-9]+_[A-Za-z0-9_]+", reason), reason
        assert not any(key in reason for key in keys), reason


def test_a_reason_names_the_operand_in_plain_words_with_its_year_end() -> None:
    result = run("mnst", as_of=datetime(2026, 3, 31, tzinfo=UTC))
    assert result.f_score is not None
    assert result.f_score.tests[0].reason == (
        "Net income for 2025-12-31 is unavailable: The filings report none for that fiscal year."
    )
