"""Real annual resolution and presentation preserve the selected financial basis."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from src.analysis.strategy.fcf_earnings_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.analysis.strategy.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.strategy.fcf_earnings_growth.models import FCFClassificationBasis, FCFEarningsGrowthPolicy
from src.data.financial.facts import FinancialField
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.presentation import PresentationMode


@pytest.mark.parametrize("basis", list(FCFClassificationBasis))
@pytest.mark.parametrize("mode", list(PresentationMode))
def test_dilution_changes_the_selected_explanation(basis: FCFClassificationBasis, mode: PresentationMode) -> None:
    """Total FCF grows while dilution causes per-share FCF to fall."""
    facts = tuple(
        replace(
            fact,
            provider_id=SEC_PROVIDER_ID,
            value=(
                100.0 * (fact.fiscal_year - 2019)
                if fact.field_name is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES and fact.fiscal_year
                else fact.value
            ),
        )
        for fact in annual_series(range(2020, 2026))
    )
    now = datetime(2026, 9, 11, tzinfo=UTC)
    result = FCFEarningsGrowthAnalyzer(
        ProductionAnnualGrowthSeriesResolver(
            FixtureAnnualFinancialFactsProvider(facts),
            clock=lambda: now,
        )
    ).run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(classification_basis=basis),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=now,
        use_cache=False,
    )
    assert result.fcf_cagr.value == pytest.approx(((130 / 80) ** 0.2 - 1) * 100)
    assert result.fcf_per_share_cagr.value == pytest.approx((((130 / 600) / (80 / 100)) ** 0.2 - 1) * 100)
    text = render_fcf_earnings_growth(result, mode)
    if basis is FCFClassificationBasis.FCF_PER_SHARE:
        assert result.classification.value == "fail"
        assert "per diluted share" in text
        assert "Diluted EPS increased, but free cash flow did not." not in text
    else:
        assert result.classification.value == "pass"


def test_fcf_effective_boundary_controls_resolution_not_only_result_label() -> None:
    """A caller's fixed execution time must constrain the facts actually used."""
    facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    boundary = datetime(2024, 1, 15, tzinfo=UTC)
    result = FCFEarningsGrowthAnalyzer(
        ProductionAnnualGrowthSeriesResolver(
            FixtureAnnualFinancialFactsProvider(facts),
            clock=lambda: datetime(2026, 9, 11, tzinfo=UTC),
        )
    ).run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=boundary,
        use_cache=False,
    )
    assert result.annual_observations[-1].fiscal_year == 2023
