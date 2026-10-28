"""Resolving a completed-annual field as a series: the provider-response checks, the trace and what is not cached."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    FinancialSubjectKind,
    PeriodKind,
    SourceKind,
)
from investment_analysis_engine.data.financial.resolution_trace import ResolutionOutcome, ResolutionStage
from investment_analysis_engine.data.financial.resolver import AnnualSeriesResolution, InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from tests._sec_instants import ANNUAL_FIXTURES, NOW, FixtureFetcher, adapter_for

_FIELD = FinancialField.NET_INCOME


def _request(**changes: object) -> FinancialFactRequest:
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "SYN", _FIELD, SEC_PROVIDER_ID, basis="fiscal_year", as_of=None
    )
    return replace(request, **changes)  # type: ignore[arg-type]


def _fact(year: int = 2024, *, available_days: int = 50, **changes: object) -> ProviderFact:
    end = datetime(year, 12, 31, tzinfo=UTC)
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="SYN",
        field_name=_FIELD,
        value=100.0 + year,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field="us-gaap:NetIncomeLoss",
        retrieved_at=NOW,
        basis="fiscal_year",
        currency="USD",
        observation_period_start=datetime(year, 1, 1, tzinfo=UTC),
        observation_period_end=end,
        available_at=end + timedelta(days=available_days),
        fiscal_year=year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        provider_fact_id=f"a:{year}:{available_days}",
    )
    return replace(fact, **changes)  # type: ignore[arg-type]


class _Provider:
    def __init__(self, answer: tuple[ProviderFact, ...] | Exception) -> None:
        self.answer = answer
        self.requests: list[tuple[FinancialFactRequest, datetime]] = []

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        self.requests.append((request, effective_as_of))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _resolver(provider: object, cache: InMemoryResolvedInputCache | None = None) -> InputResolver:
    return InputResolver(provider, cache, clock=lambda: NOW)  # type: ignore[arg-type]


def _closing(result: AnnualSeriesResolution) -> tuple[ResolutionStage, ResolutionOutcome]:
    event = result.resolution_trace.events[-1]
    return event.stage, event.outcome


def test_every_observation_that_passes_the_checks_is_a_resolved_input_oldest_period_first() -> None:
    provider = _Provider((_fact(2024), _fact(2022), _fact(2023), _fact(2023, available_days=200)))
    result = _resolver(provider).resolve_annual_series(_request())
    assert result.status is CalculationStatus.OK
    assert [item.provider_fact_id for item in result.inputs] == ["a:2022:50", "a:2023:50", "a:2023:200", "a:2024:50"]
    assert [item.fiscal_year for item in result.inputs] == [2022, 2023, 2023, 2024]
    first = result.inputs[0]
    assert (first.source_kind, first.field_name, first.basis, first.units, first.currency) == (
        SourceKind.PROVIDER,
        "net_income",
        "fiscal_year",
        "currency",
        "USD",
    )
    assert (first.period_kind, first.accounting_scope) == (PeriodKind.COMPLETED_ANNUAL, AccountingScope.CONSOLIDATED)
    assert (first.provider_id, first.provider_field, first.provider_fact_id) == (
        SEC_PROVIDER_ID,
        "us-gaap:NetIncomeLoss",
        "a:2022:50",
    )
    assert first.resolved_at == NOW
    assert first.as_of is None
    assert len(provider.requests) == 1


def test_the_trace_records_the_request_and_the_outcome() -> None:
    result = _resolver(_Provider((_fact(),))).resolve_annual_series(_request())
    events = result.resolution_trace.events
    assert [(event.stage, event.outcome) for event in events] == [
        (ResolutionStage.PROVIDER, ResolutionOutcome.ATTEMPTED),
        (ResolutionStage.PROVIDER, ResolutionOutcome.SUCCESS),
    ]
    assert events[0].field_name == "net_income"
    assert "1 fiscal-year observation(s) resolved" in events[1].message


def test_the_provider_gets_the_boundary_of_the_request_or_the_clock() -> None:
    boundary = datetime(2025, 6, 30, tzinfo=UTC)
    historical, current = _Provider((_fact(),)), _Provider((_fact(),))
    _resolver(historical).resolve_annual_series(_request(as_of=boundary))
    _resolver(current).resolve_annual_series(_request())
    assert historical.requests[0][1] == boundary
    assert current.requests[0][1] == NOW


def test_the_series_is_not_cached() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    provider = _Provider((_fact(),))
    resolver = _resolver(provider, cache)
    resolver.resolve_annual_series(_request())
    resolver.resolve_annual_series(_request())
    assert len(provider.requests) == 2


def test_the_basis_must_be_the_fiscal_year() -> None:
    provider = _Provider((_fact(),))
    for basis in (None, "fiscal_year_end"):
        result = _resolver(provider).resolve_annual_series(_request(basis=basis))
        assert result.status is CalculationStatus.INVALID_INPUT
        assert "requires basis='fiscal_year'" in (result.reason or "")
        assert _closing(result) == (ResolutionStage.VALIDATION, ResolutionOutcome.INVALID)
    assert provider.requests == []


def test_a_subject_that_is_not_available_as_of_the_boundary_is_flagged() -> None:
    result = _resolver(_Provider(FactsNotAvailableAsOf("first annual report came later"))).resolve_annual_series(
        _request()
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.not_available_as_of
    assert result.reason == "first annual report came later"
    assert _closing(result) == (ResolutionStage.PROVIDER, ResolutionOutcome.UNAVAILABLE)


def test_a_provider_that_reports_nothing_is_unavailable_but_not_flagged() -> None:
    result = _resolver(_Provider(())).resolve_annual_series(_request())
    assert (result.status, result.not_available_as_of) == (CalculationStatus.INPUT_UNAVAILABLE, False)
    assert result.reason == "Provider returned no data for the requested field."


def test_a_provider_failure_is_returned_with_its_record() -> None:
    failure = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID)
    result = _resolver(_Provider(failure)).resolve_annual_series(_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, SEC_PROVIDER_ID)
    assert result.reason == "Provider error: down"
    assert _closing(result) == (ResolutionStage.PROVIDER, ResolutionOutcome.ERROR)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"subject_id": "OTHER"}, "subject_id"),
        ({"field_name": FinancialField.SALES}, "field_name"),
        ({"provider_id": "yfinance"}, "provider_id"),
        ({"basis": "fiscal_year_end"}, "basis"),
        ({"period_kind": PeriodKind.QUARTERLY, "fiscal_year": None}, "quarterly period kind"),
        ({"period_kind": None, "fiscal_year": None}, "no period kind"),
        ({"observation_period_start": None}, "missing its observation period"),
        ({"observation_period_end": None}, "missing its observation period"),
    ],
)
def test_an_answer_that_does_not_answer_the_request_is_rejected_as_a_whole(
    changes: dict[str, Any], message: str
) -> None:
    result = _resolver(_Provider((_fact(2023), _fact(2024, **changes)))).resolve_annual_series(_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert message in (result.reason or "")
    assert result.provider_failure == ProviderFailureRecord(ProviderFailureKind.UNEXPECTED_RESPONSE, SEC_PROVIDER_ID)
    assert _closing(result) == (ResolutionStage.PROVIDER, ResolutionOutcome.REJECTED)


def test_an_observation_not_available_at_the_boundary_is_left_out_and_the_others_stand() -> None:
    boundary = datetime(2025, 3, 1, tzinfo=UTC)
    late = _fact(2024, available_days=100)  # available 2025-04-10
    result = _resolver(_Provider((_fact(2023), late))).resolve_annual_series(_request(as_of=boundary))
    assert result.status is CalculationStatus.OK
    assert [item.fiscal_year for item in result.inputs] == [2023]
    assert "1 left out as ineligible" in result.resolution_trace.events[-1].message


def test_a_historical_observation_with_no_availability_is_left_out() -> None:
    result = _resolver(_Provider((_fact(available_days=0, available_at=None),))).resolve_annual_series(
        _request(as_of=datetime(2025, 6, 30, tzinfo=UTC))
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert "No net_income observation is eligible at the boundary" in (result.reason or "")
    assert not result.not_available_as_of


def test_an_observation_that_fails_the_quality_checks_is_left_out() -> None:
    future = _fact(2030)
    result = _resolver(_Provider((future,))).resolve_annual_series(_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert "is eligible at the boundary" in (result.reason or "")


def test_the_invariants_of_the_result_are_enforced() -> None:
    with pytest.raises(ValueError, match="OK requires inputs"):
        AnnualSeriesResolution(CalculationStatus.OK)
    with pytest.raises(ValueError, match="requires a reason and no inputs"):
        AnnualSeriesResolution(CalculationStatus.INPUT_UNAVAILABLE)
    with pytest.raises(ValueError, match="provider_failure requires PROVIDER_ERROR"):
        AnnualSeriesResolution(
            CalculationStatus.INPUT_UNAVAILABLE,
            reason="x",
            provider_failure=ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, SEC_PROVIDER_ID),
        )
    with pytest.raises(ValueError, match="not_available_as_of requires INPUT_UNAVAILABLE"):
        AnnualSeriesResolution(CalculationStatus.PROVIDER_ERROR, reason="x", not_available_as_of=True)


def test_the_sec_adapter_series_passes_the_checks_on_a_captured_issuer() -> None:
    adapter = adapter_for("WMT", FixtureFetcher("WMT", folder=ANNUAL_FIXTURES))
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "WMT", FinancialField.NET_INCOME, SEC_PROVIDER_ID, basis="fiscal_year"
    )
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        result = _resolver(adapter).resolve_annual_series(request)
    assert result.status is CalculationStatus.OK
    assert all(item.period_kind is PeriodKind.COMPLETED_ANNUAL for item in result.inputs)
    ends = [item.observation_period_end for item in result.inputs if item.observation_period_end is not None]
    assert ends == sorted(ends)
    assert date(2026, 1, 31) in {end.date() for end in ends}
