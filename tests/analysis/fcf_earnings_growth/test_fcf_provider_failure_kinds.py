"""FCF Growth stores the kind and provider of a failed annual field.

A diluted-share lookup that fails while the classification is on total free cash flow is not a failure of the
analysis; its trace event stays in the result's diagnostics.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.core.analysis_status import CalculationStatus
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialProviderError, ProviderFact
from src.data.financial.resolution_trace import ResolutionOutcome
from src.evaluation.fixtures.fcf_earnings_growth import (
    PROVIDER_ID,
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from src.strategies.fcf_growth.input_resolver import (
    AnnualGrowthSeriesAssembly,
    FinancialFieldProvider,
    resolve_annual_growth_series,
)
from src.strategies.fcf_growth.models import FCFEarningsGrowthPolicy, ReasonCode
from src.strategies.fcf_growth.vocabulary import FCFClassificationBasis
from tests.analysis.fcf_earnings_growth.test_fcf_earnings_growth_input_resolver import NOW

_KINDS = list(ProviderFailureKind)


class _FailingField(FixtureAnnualFinancialFactsProvider):
    """The annual fixture, raising a chosen exception for one field."""

    def __init__(self, field: FinancialField, error: BaseException) -> None:
        super().__init__(annual_series(range(2020, 2026)))
        self._field = field
        self._error = error

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        if request.field_name is self._field:
            raise self._error
        return super().fetch_facts(request, effective_as_of=effective_as_of)


def _resolve(
    provider: FixtureAnnualFinancialFactsProvider, basis: FCFClassificationBasis
) -> AnnualGrowthSeriesAssembly:
    binding = FinancialFieldProvider(PROVIDER_ID, provider)
    return resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(classification_basis=basis),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        effective_as_of=NOW,
        providers=dict.fromkeys(
            (
                FinancialField.OPERATING_CASH_FLOW,
                FinancialField.CAPITAL_EXPENDITURES,
                FinancialField.EPS,
                FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
            ),
            binding,
        ),
        cache=None,
        clock=lambda: NOW,
    )


def _typed(kind: ProviderFailureKind) -> FinancialProviderError:
    return FinancialProviderError("synthetic failure", kind=kind, provider_id=PROVIDER_ID)


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "field",
    [FinancialField.OPERATING_CASH_FLOW, FinancialField.CAPITAL_EXPENDITURES, FinancialField.EPS],
)
def test_a_failed_required_field_stores_its_kind_and_provider(field: FinancialField, kind: ProviderFailureKind) -> None:
    result = _resolve(_FailingField(field, _typed(kind)), FCFClassificationBasis.TOTAL_FCF)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.reason_code is ReasonCode.PROVIDER_ERROR
    assert result.provider_failure == ProviderFailureRecord(kind=kind, provider_id=PROVIDER_ID, input=field.value)


def test_an_unclassified_failure_stores_no_kind() -> None:
    error = FinancialProviderError("bare")

    result = _resolve(_FailingField(FinancialField.EPS, error), FCFClassificationBasis.TOTAL_FCF)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure is None


@pytest.mark.parametrize("kind", _KINDS)
def test_a_failed_diluted_share_field_is_a_failure_only_under_the_per_share_basis(kind: ProviderFailureKind) -> None:
    provider = _FailingField(FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES, _typed(kind))

    per_share = _resolve(provider, FCFClassificationBasis.FCF_PER_SHARE)

    assert per_share.status is CalculationStatus.PROVIDER_ERROR
    assert per_share.provider_failure == ProviderFailureRecord(
        kind=kind, provider_id=PROVIDER_ID, input="weighted_average_diluted_shares"
    )


@pytest.mark.parametrize("kind", _KINDS)
def test_a_skipped_diluted_share_failure_leaves_a_trace_event_and_no_failure(kind: ProviderFailureKind) -> None:
    provider = _FailingField(FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES, _typed(kind))

    total = _resolve(provider, FCFClassificationBasis.TOTAL_FCF)

    assert total.status is CalculationStatus.OK
    assert total.provider_failure is None
    skipped = [
        event
        for event in total.resolution_trace.events
        if event.field_name == "weighted_average_diluted_shares" and event.outcome is ResolutionOutcome.ERROR
    ]
    assert len(skipped) == 1
    assert "synthetic failure" in skipped[0].message


@pytest.mark.parametrize("defect", [RuntimeError("defect"), ValueError("defect"), KeyError("defect")])
def test_an_exception_that_is_not_a_provider_failure_propagates(defect: BaseException) -> None:
    with pytest.raises(type(defect)):
        _resolve(_FailingField(FinancialField.OPERATING_CASH_FLOW, defect), FCFClassificationBasis.TOTAL_FCF)
