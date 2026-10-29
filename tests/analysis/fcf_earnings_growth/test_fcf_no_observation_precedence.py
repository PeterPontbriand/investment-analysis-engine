"""When no observation of a field remains, FCF-Growth's outcome follows a fixed precedence, not the answer's order."""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.financial.facts import FinancialField, ProviderFact
from investment_analysis_engine.data.financial.provenance import AccountingScope
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider
from investment_analysis_engine.strategies.fcf_growth.input_resolver import (
    AnnualGrowthSeriesAssembly,
    resolve_annual_growth_series,
)
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthPolicy
from tests._sec_labeled_annual import sec_annual_fact, sec_annual_series

NOW = datetime(2026, 3, 1, tzinfo=UTC)
BOUNDARY = datetime(2026, 1, 1, tzinfo=UTC)
OCF = FinancialField.OPERATING_CASH_FLOW
NOT_AVAILABLE = "The annual fact was not publicly available at the analysis boundary."
LATER = "The annual observation is later than the analysis boundary."
CURRENCY = "The annual fact has an incompatible or unknown currency."

# V: valid. L: filed after the boundary. Q: fails the quality check (its period ends after the boundary).
# B: available at the boundary but in another currency, which this strategy's own checks reject.
KINDS = "VLQB"


def _fact(kind: str) -> ProviderFact:
    if kind == "V":
        return sec_annual_fact(OCF, 2021, 120.0)
    if kind == "L":
        return sec_annual_fact(OCF, 2022, 130.0, available_at=datetime(2026, 1, 6, tzinfo=UTC))
    if kind == "Q":
        return sec_annual_fact(OCF, 2027, 150.0, available_at=datetime(2025, 6, 1, tzinfo=UTC))
    return replace(sec_annual_fact(OCF, 2023, 140.0), currency="CAD")


def _outcome(order: tuple[str, ...], as_of: datetime | None) -> tuple[CalculationStatus, ReasonCode | None, str | None]:
    others = tuple(fact for fact in sec_annual_series(range(2020, 2026)) if fact.field_name is not OCF)
    result: AnnualGrowthSeriesAssembly = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=as_of,
        effective_as_of=as_of or NOW,
        provider=FixtureAnnualFinancialFactsProvider(others + tuple(_fact(kind) for kind in order)),
        clock=lambda: NOW,
    )
    return result.status, result.reason_code, result.reason


def _combinations() -> list[str]:
    return ["".join(combo) for size in range(1, 5) for combo in itertools.combinations(KINDS, size)]


def _expected(combination: str) -> tuple[CalculationStatus, ReasonCode | None, str | None]:
    if "B" in combination:
        return CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.INCOMPATIBLE_CURRENCY, CURRENCY
    if "L" in combination:
        return CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.NOT_AVAILABLE_AS_OF, NOT_AVAILABLE
    return CalculationStatus.INPUT_UNAVAILABLE, ReasonCode.NOT_AVAILABLE_AS_OF, LATER


@pytest.mark.parametrize("combination", [item for item in _combinations() if "V" not in item])
def test_with_no_valid_observation_every_order_gives_the_precedence_outcome(combination: str) -> None:
    expected = _expected(combination)
    for order in itertools.permutations(combination):
        assert _outcome(order, BOUNDARY) == expected, "".join(order)


@pytest.mark.parametrize("combination", [item for item in _combinations() if "V" in item])
def test_a_valid_observation_keeps_the_outcome_of_the_valid_one_alone_in_every_order(combination: str) -> None:
    alone = _outcome(("V",), BOUNDARY)
    for order in itertools.permutations(combination):
        assert _outcome(order, BOUNDARY) == alone, "".join(order)


@pytest.mark.parametrize(
    ("combination", "expected"),
    [("Q", (ReasonCode.NOT_AVAILABLE_AS_OF, LATER)), ("QB", (ReasonCode.INCOMPATIBLE_CURRENCY, CURRENCY))],
)
def test_a_live_run_follows_the_same_precedence(combination: str, expected: tuple[ReasonCode, str]) -> None:
    for order in itertools.permutations(combination):
        assert _outcome(order, None) == (CalculationStatus.INPUT_UNAVAILABLE, *expected), "".join(order)


def test_among_several_own_rejections_the_earliest_period_then_fact_id_is_chosen() -> None:
    others = tuple(fact for fact in sec_annual_series(range(2020, 2026)) if fact.field_name is not OCF)
    cad = replace(sec_annual_fact(OCF, 2023, 140.0, provider_fact_id="b"), currency="CAD")
    gbp = replace(sec_annual_fact(OCF, 2022, 130.0, provider_fact_id="a"), currency="GBP")
    parent = replace(sec_annual_fact(OCF, 2021, 120.0, provider_fact_id="c"), accounting_scope=AccountingScope.PARENT)
    for order in itertools.permutations((cad, gbp, parent)):
        result = resolve_annual_growth_series(
            policy=FCFEarningsGrowthPolicy(),
            subject_id="ACME",
            currency="USD",
            as_of=None,
            effective_as_of=NOW,
            provider=FixtureAnnualFinancialFactsProvider(others + order),
            clock=lambda: NOW,
        )
        assert result.reason_code is ReasonCode.INCOMPATIBLE_SCOPE
