"""The balance-sheet and annual values at several named year-ends, through the shared assembly functions."""

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.metric_inputs import (
    MetricInputsFailure,
    resolve_annual_values,
    resolve_annual_values_at,
    resolve_balance_sheet_values,
    resolve_balance_sheet_values_at,
)
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind, ResolvedInput
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from tests._sec_instants import NOW
from tests.analysis.shared._metric_input_rig import LIVE_NOW, FactsStub, unreachable

F = FinancialField
_Table = Mapping[FinancialField, Mapping[date, "_Reported | InstantAbsence"]]
_T = date(2025, 12, 31)
_T1 = date(2024, 12, 31)
_T2 = date(2023, 12, 31)
_YEARS = (_T, _T1, _T2)
_FILED = {
    _T: datetime(2026, 2, 20, tzinfo=UTC),
    _T1: datetime(2025, 2, 20, tzinfo=UTC),
    _T2: datetime(2024, 2, 20, tzinfo=UTC),
}
_ANCHOR = AnchorYearEnd(_T, "0000000001-26-000001", "10-K", date(2026, 2, 20), {})


@dataclass(frozen=True)
class _Reported:
    """An instant value as one filing reports it."""

    value: float
    currency: str = "USD"
    provider_field: str = "us-gaap:Assets"
    accession: str = "0000000001-26-000001"


@dataclass(frozen=True)
class _Annual:
    """An annual observation as one filing reports it."""

    value: float
    day: date
    available: datetime
    currency: str = "USD"
    provider_field: str = "us-gaap:NetIncomeLoss"


class _Filings(FactsStub):
    """A provider whose instant and annual answers come from tables and which records every request."""

    def __init__(
        self,
        instants: _Table | None = None,
        annuals: Mapping[FinancialField, Sequence[_Annual]] | None = None,
        *,
        reverse: bool = False,
        failure: BaseException | None = None,
    ) -> None:
        super().__init__(error=failure)
        self.instants = dict(instants or {})
        self.annuals = dict(annuals or {})
        self.reverse = reverse

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:  # noqa: ARG002
        """Answer each requested date from the table, absent when the table has none."""
        self.series_requests.append(request)
        if self.error is not None:
            raise self.error
        facts: list[ProviderFact] = []
        absences: list[InstantAbsence] = []
        for day in request.period_ends:
            held = self.instants.get(request.field_name, {}).get(day)
            if isinstance(held, _Reported):
                facts.append(
                    ProviderFact(
                        FinancialSubjectKind.SECURITY,
                        request.subject_id,
                        request.field_name,
                        held.value,
                        FinancialUnit.CURRENCY,
                        request.provider_id,
                        held.provider_field,
                        NOW,
                        basis="fiscal_year_end",
                        currency=held.currency,
                        observation_period_end=datetime.combine(day, datetime.max.time(), tzinfo=UTC),
                        available_at=_FILED[day],
                        period_kind=PeriodKind.INSTANT,
                        provider_fact_id=f"{held.accession}:{request.field_name.value}:{day}",
                        notes=(f"accession={held.accession}",),
                    )
                )
            else:
                absences.append(held or InstantAbsence(day, InstantAbsenceReason.NOT_TAGGED, "not tagged"))
        if self.reverse:
            facts.reverse()
            absences.reverse()
        return InstantSeriesFacts(tuple(facts), tuple(absences))

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        """Answer an annual series request from the table."""
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.not_available_as_of is not None:
            raise FactsNotAvailableAsOf(self.not_available_as_of)
        facts = tuple(
            ProviderFact(
                FinancialSubjectKind.SECURITY,
                request.subject_id,
                request.field_name,
                item.value,
                FinancialUnit.CURRENCY,
                request.provider_id,
                item.provider_field,
                NOW,
                basis=request.basis,
                currency=item.currency,
                observation_period_start=datetime.combine(
                    item.day - timedelta(days=364), datetime.min.time(), tzinfo=UTC
                ),
                observation_period_end=datetime.combine(item.day, datetime.min.time(), tzinfo=UTC),
                available_at=item.available,
                fiscal_year=item.day.year,
                period_kind=PeriodKind.COMPLETED_ANNUAL,
                provider_fact_id=f"stub:{request.field_name.value}:{item.day}:{item.available:%Y%m%d}:{item.value}",
            )
            for item in self.annuals.get(request.field_name, ())
        )
        return tuple(reversed(facts)) if self.reverse else facts


def _resolver(stub: FactsStub) -> InputResolver:
    return InputResolver(stub, clock=lambda: LIVE_NOW)


def _balance(stub: _Filings, fields: Sequence[FinancialField], years: Sequence[date], **keywords: Any) -> Any:
    return resolve_balance_sheet_values_at(
        _resolver(stub), ticker="WMT", fields=fields, year_ends=years, as_of=keywords.get("as_of")
    )


def _annual(stub: _Filings, fields: Sequence[FinancialField], years: Sequence[date], **keywords: Any) -> Any:
    return resolve_annual_values_at(
        _resolver(stub), ticker="WMT", fields=fields, year_ends=years, as_of=keywords.get("as_of")
    )


def _held(value: object) -> ResolvedInput:
    assert isinstance(value, ResolvedInput)
    return value


def _unavailable(value: object) -> InputUnavailable:
    assert isinstance(value, InputUnavailable)
    return value


# --- balance-sheet values at several year-ends ---------------------------------------------------------------------


def test_total_assets_at_three_year_ends_is_one_value_per_year_and_one_request() -> None:
    stub = _Filings({F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: _Reported(200.0), _T2: _Reported(100.0)}})
    values = _balance(stub, [F.TOTAL_ASSETS], _YEARS)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    assert {day: _held(item).value for day, item in values[F.TOTAL_ASSETS].items()} == {
        _T: 300.0,
        _T1: 200.0,
        _T2: 100.0,
    }
    assert len(stub.series_requests) == 1
    assert stub.series_requests[0].period_ends == (_T2, _T1, _T)


def test_a_value_two_years_back_from_an_earlier_filing_is_returned_with_its_own_filing() -> None:
    older = "0000000001-24-000001"
    stub = _Filings(
        {F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: _Reported(200.0), _T2: _Reported(100.0, accession=older)}}
    )
    values = _balance(stub, [F.TOTAL_ASSETS], _YEARS)[F.TOTAL_ASSETS]
    assert f"accession={older}" in _held(values[_T2]).notes
    assert f"accession={_ANCHOR.accession}" in _held(values[_T]).notes
    assert _held(values[_T2]).available_at == _FILED[_T2]


def test_a_conflict_at_the_prior_year_end_is_that_years_absence_only() -> None:
    conflict = InstantAbsence(_T1, InstantAbsenceReason.CONFLICT, "two filings disagree")
    stub = _Filings({F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: conflict, _T2: _Reported(100.0)}})
    values = _balance(stub, [F.TOTAL_ASSETS], _YEARS)[F.TOTAL_ASSETS]
    assert values[_T1] == conflict
    assert _held(values[_T]).value == 300.0
    assert _held(values[_T2]).value == 100.0


def test_a_prior_year_end_filed_after_the_boundary_is_that_years_absence_and_the_others_stay() -> None:
    late = InstantAbsence(_T1, InstantAbsenceReason.AFTER_BOUNDARY, "filed after the boundary")
    stub = _Filings({F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: late, _T2: _Reported(100.0)}})
    values = _balance(stub, [F.TOTAL_ASSETS], _YEARS)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    assert values[F.TOTAL_ASSETS][_T1] == late
    assert _held(values[F.TOTAL_ASSETS][_T]).value == 300.0


def test_every_requested_year_end_after_the_boundary_is_returned_once_and_no_further_field_is_requested() -> None:
    late = {day: InstantAbsence(day, InstantAbsenceReason.AFTER_BOUNDARY, "after the boundary.") for day in _YEARS}
    stub = _Filings({F.TOTAL_ASSETS: late, F.CURRENT_ASSETS: late})
    outcome = _balance(stub, [F.TOTAL_ASSETS, F.CURRENT_ASSETS], _YEARS)
    unavailable = _unavailable(outcome)
    assert (unavailable.reason_code, unavailable.reason) == (ReasonCode.NOT_AVAILABLE_AS_OF, "after the boundary.")
    assert len(stub.series_requests) == 1


def test_fields_that_disagree_on_currency_or_taxonomy_reach_the_caller_unchanged() -> None:
    stub = _Filings(
        {
            F.TOTAL_ASSETS: {
                _T: _Reported(300.0),
                _T1: _Reported(200.0, currency="EUR", provider_field="ifrs-full:Assets"),
            },
            F.CURRENT_ASSETS: {_T: _Reported(30.0, provider_field="us-gaap:AssetsCurrent")},
        }
    )
    values = _balance(stub, [F.TOTAL_ASSETS, F.CURRENT_ASSETS], (_T1, _T))
    assets, current = values[F.TOTAL_ASSETS], values[F.CURRENT_ASSETS]
    assert (_held(assets[_T]).currency, _held(assets[_T]).provider_field) == ("USD", "us-gaap:Assets")
    assert (_held(assets[_T1]).currency, _held(assets[_T1]).provider_field) == ("EUR", "ifrs-full:Assets")
    assert (_held(current[_T]).currency, _held(current[_T]).provider_field) == ("USD", "us-gaap:AssetsCurrent")
    assert isinstance(current[_T1], InstantAbsence)


def test_an_unsupported_provider_is_an_unsupported_absence_at_every_requested_year_end() -> None:
    class FactsOnly:
        def fetch_facts(self, request: Any, *, effective_as_of: datetime) -> tuple[()]:  # noqa: ARG002
            return ()

    values = resolve_balance_sheet_values_at(
        InputResolver(FactsOnly(), clock=lambda: LIVE_NOW),
        ticker="WMT",
        fields=[F.TOTAL_ASSETS],
        year_ends=(_T1, _T),
        as_of=None,
    )
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    absences = values[F.TOTAL_ASSETS]
    assert set(absences) == {_T1, _T}
    assert all(
        isinstance(item, InstantAbsence) and item.reason is InstantAbsenceReason.UNSUPPORTED
        for item in absences.values()
    )


def test_balance_sheet_results_do_not_depend_on_the_order_of_fields_dates_or_the_providers_answer() -> None:
    table: _Table = {
        F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: _Reported(200.0), _T2: _Reported(100.0)},
        F.CURRENT_ASSETS: {_T: _Reported(30.0), _T1: InstantAbsence(_T1, InstantAbsenceReason.CONFLICT, "conflict")},
        F.CASH_AND_EQUIVALENTS: {_T: _Reported(3.0), _T2: _Reported(1.0)},
    }
    fields = [F.TOTAL_ASSETS, F.CURRENT_ASSETS, F.CASH_AND_EQUIVALENTS]
    expected = _balance(_Filings(table), fields, _YEARS)
    for ordered_fields, ordered_years, reverse in itertools.product(
        itertools.permutations(fields), itertools.permutations(_YEARS), (False, True)
    ):
        assert _balance(_Filings(table, reverse=reverse), ordered_fields, ordered_years) == expected
    assert _balance(_Filings(table), [*fields, *fields], [*_YEARS, _T, _T2]) == expected


def test_a_balance_sheet_provider_failure_is_returned_typed_for_the_field() -> None:
    outcome = _balance(_Filings(failure=unreachable()), [F.TOTAL_ASSETS, F.CURRENT_ASSETS], _YEARS)
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "total_assets"
    assert outcome.provider_failure is not None
    assert outcome.provider_failure.kind is ProviderFailureKind.UNREACHABLE


def test_the_one_year_end_function_is_the_slice_of_the_multi_year_function_at_the_anchor() -> None:
    table: _Table = {
        F.TOTAL_ASSETS: {_T: _Reported(300.0), _T1: _Reported(200.0)},
        F.CURRENT_ASSETS: {_T: InstantAbsence(_T, InstantAbsenceReason.UNSUPPORTED, "unsupported")},
    }
    single = resolve_balance_sheet_values(
        _resolver(_Filings(table)),
        anchor=_ANCHOR,
        ticker="WMT",
        fields=[F.CURRENT_ASSETS, F.TOTAL_ASSETS],
        as_of=None,
    )
    multi = _balance(_Filings(table), [F.CURRENT_ASSETS, F.TOTAL_ASSETS], (_T1, _T))
    assert not isinstance(single, (InputUnavailable, MetricInputsFailure))
    assert dict(single) == {name: multi[name][_T] for name in (F.CURRENT_ASSETS, F.TOTAL_ASSETS)}
    assert list(single) == [F.CURRENT_ASSETS, F.TOTAL_ASSETS]


def test_no_year_end_and_a_field_that_is_not_on_the_balance_sheet_are_caller_errors() -> None:
    with pytest.raises(ValueError, match="At least one year-end"):
        _balance(_Filings(), [F.TOTAL_ASSETS], [])
    with pytest.raises(ValueError, match="not a balance-sheet field"):
        _balance(_Filings(), [F.SALES], _YEARS)


# --- annual values at several year-ends ----------------------------------------------------------------------------


def _years(*values: float, provider_field: str = "us-gaap:NetIncomeLoss") -> list[_Annual]:
    return [
        _Annual(value, day, _FILED[day], provider_field=provider_field)
        for value, day in zip(values, _YEARS, strict=True)
    ]


def test_annual_values_are_selected_per_requested_year_end_from_one_series_per_field() -> None:
    stub = _Filings(annuals={F.NET_INCOME: _years(30.0, 20.0, 10.0), F.SALES: _years(3.0, 2.0, 1.0)})
    values = _annual(stub, [F.NET_INCOME, F.SALES], _YEARS)
    assert {day: _held(item).value for day, item in values[F.NET_INCOME].items()} == {_T: 30.0, _T1: 20.0, _T2: 10.0}
    assert {day: _held(item).value for day, item in values[F.SALES].items()} == {_T: 3.0, _T1: 2.0, _T2: 1.0}
    assert len(stub.requests) == 2


def test_a_year_the_filings_report_no_value_for_is_none_and_the_others_stay() -> None:
    stub = _Filings(annuals={F.NET_INCOME: [_Annual(30.0, _T, _FILED[_T]), _Annual(10.0, _T2, _FILED[_T2])]})
    values = _annual(stub, [F.NET_INCOME], _YEARS)[F.NET_INCOME]
    assert values[_T1] is None
    assert _held(values[_T]).value == 30.0
    assert _held(values[_T2]).value == 10.0


def test_a_value_two_years_back_from_an_earlier_filing_is_the_one_that_filing_reported() -> None:
    stub = _Filings(annuals={F.NET_INCOME: _years(30.0, 20.0, 10.0)})
    values = _annual(stub, [F.NET_INCOME], _YEARS)[F.NET_INCOME]
    assert _held(values[_T2]).available_at == _FILED[_T2]
    assert _held(values[_T]).available_at == _FILED[_T]


def test_a_conflict_at_the_prior_year_end_is_ambiguous_for_that_year_only() -> None:
    same_time = _FILED[_T1] + timedelta(days=1)
    stub = _Filings(
        annuals={
            F.NET_INCOME: [
                _Annual(30.0, _T, _FILED[_T]),
                _Annual(20.0, _T1, same_time),
                _Annual(21.0, _T1, same_time),
                _Annual(10.0, _T2, _FILED[_T2]),
            ]
        }
    )
    values = _annual(stub, [F.NET_INCOME], _YEARS)[F.NET_INCOME]
    assert _unavailable(values[_T1]).reason_code is ReasonCode.AMBIGUOUS_FACT
    assert _held(values[_T]).value == 30.0
    assert _held(values[_T2]).value == 10.0


def test_the_latest_available_version_decides_each_year_separately() -> None:
    stub = _Filings(
        annuals={
            F.NET_INCOME: [
                _Annual(20.0, _T1, _FILED[_T1]),
                _Annual(22.0, _T1, _FILED[_T] - timedelta(days=30)),
                _Annual(30.0, _T, _FILED[_T]),
            ]
        }
    )
    values = _annual(stub, [F.NET_INCOME], _YEARS)[F.NET_INCOME]
    assert _held(values[_T1]).value == 22.0
    assert _held(values[_T]).value == 30.0


def test_a_prior_year_filed_after_the_boundary_is_not_available_as_of_for_that_year_only() -> None:
    boundary = datetime(2026, 3, 5, tzinfo=UTC)
    stub = _Filings(
        annuals={
            F.NET_INCOME: [
                _Annual(30.0, _T, _FILED[_T]),
                _Annual(20.0, _T1, datetime(2026, 6, 1, tzinfo=UTC)),
                _Annual(10.0, _T2, _FILED[_T2]),
            ]
        }
    )
    values = _annual(stub, [F.NET_INCOME], _YEARS, as_of=boundary)[F.NET_INCOME]
    late = _unavailable(values[_T1])
    assert late.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert _held(values[_T]).value == 30.0
    assert _held(values[_T2]).value == 10.0


def test_a_registrant_with_nothing_public_at_the_boundary_is_returned_once() -> None:
    stub = _Filings(annuals={})
    stub.not_available_as_of = "The registrant filed its first annual report after the boundary."
    outcome = _annual(stub, [F.NET_INCOME, F.SALES], _YEARS)
    assert _unavailable(outcome).reason == "The registrant filed its first annual report after the boundary."
    assert len(stub.requests) == 1


def test_fields_that_disagree_on_currency_or_taxonomy_reach_the_caller_unchanged_for_annual_values() -> None:
    stub = _Filings(
        annuals={
            F.NET_INCOME: [_Annual(30.0, _T, _FILED[_T]), _Annual(20.0, _T1, _FILED[_T1], currency="EUR")],
            F.SALES: [_Annual(3.0, _T, _FILED[_T], provider_field="ifrs-full:Revenue")],
        }
    )
    values = _annual(stub, [F.NET_INCOME, F.SALES], (_T1, _T))
    income, sales = values[F.NET_INCOME], values[F.SALES]
    assert (_held(income[_T]).currency, _held(income[_T1]).currency) == ("USD", "EUR")
    assert _held(income[_T]).provider_field == "us-gaap:NetIncomeLoss"
    assert _held(sales[_T]).provider_field == "ifrs-full:Revenue"


def test_annual_results_do_not_depend_on_the_order_of_fields_dates_or_the_providers_answer() -> None:
    annuals = {
        F.NET_INCOME: _years(30.0, 20.0, 10.0),
        F.SALES: _years(3.0, 2.0, 1.0),
        F.OPERATING_CASH_FLOW: _years(33.0, 22.0, 11.0),
    }
    fields = [F.NET_INCOME, F.SALES, F.OPERATING_CASH_FLOW]
    expected = _annual(_Filings(annuals=annuals), fields, _YEARS)
    for ordered_fields, ordered_years, reverse in itertools.product(
        itertools.permutations(fields), itertools.permutations(_YEARS), (False, True)
    ):
        assert _annual(_Filings(annuals=annuals, reverse=reverse), ordered_fields, ordered_years) == expected
    assert _annual(_Filings(annuals=annuals), [*fields, *fields], [*_YEARS, _T]) == expected


def test_an_annual_provider_failure_is_returned_typed_for_the_field() -> None:
    outcome = _annual(_Filings(failure=unreachable()), [F.SALES], _YEARS)
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "sales"
    assert outcome.provider_failure is not None


def test_no_year_end_and_a_field_outside_the_annual_fields_are_caller_errors() -> None:
    with pytest.raises(ValueError, match="At least one year-end"):
        _annual(_Filings(), [F.SALES], [])
    with pytest.raises(ValueError, match="not a completed-annual period field"):
        _annual(_Filings(), [F.SALES, F.TOTAL_ASSETS], _YEARS)
    with pytest.raises(ValueError, match="not a completed-annual period field"):
        _annual(_Filings(), [F.CAPITAL_EXPENDITURES], _YEARS)


# --- operating cash flow -------------------------------------------------------------------------------------------


def test_operating_cash_flow_is_accepted_by_name_by_the_multi_year_function() -> None:
    stub = _Filings(
        annuals={
            F.OPERATING_CASH_FLOW: _years(
                33.0,
                22.0,
                11.0,
                provider_field="us-gaap:NetCashProvidedByUsedInOperatingActivities",
            )
        }
    )
    values = _annual(stub, [F.OPERATING_CASH_FLOW], _YEARS)[F.OPERATING_CASH_FLOW]
    assert {day: _held(item).value for day, item in values.items()} == {_T: 33.0, _T1: 22.0, _T2: 11.0}
    assert _held(values[_T]).provider_field == "us-gaap:NetCashProvidedByUsedInOperatingActivities"
    assert stub.requests[0].field_name is F.OPERATING_CASH_FLOW
    assert stub.requests[0].basis == "fiscal_year"


def test_operating_cash_flow_is_accepted_by_name_by_the_one_year_end_function() -> None:
    stub = _Filings(annuals={F.OPERATING_CASH_FLOW: _years(33.0, 22.0, 11.0)})
    values = resolve_annual_values(
        _resolver(stub), anchor=_ANCHOR, ticker="WMT", fields=[F.OPERATING_CASH_FLOW, F.NET_INCOME], as_of=None
    )
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    assert _held(values[F.OPERATING_CASH_FLOW]).value == 33.0
    assert values[F.NET_INCOME] is None


def test_operating_cash_flow_is_not_accepted_as_a_balance_sheet_field() -> None:
    with pytest.raises(ValueError, match="not a balance-sheet field"):
        _balance(_Filings(), [F.OPERATING_CASH_FLOW], _YEARS)
