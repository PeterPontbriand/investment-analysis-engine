"""Year-end discovery and the share-count series, through the shared assembly functions.

Synthetic providers drive each rule of the year-end derivation and of the share-count series. The captured fixtures
drive the same functions through the real SEC adapter, and their expected values are written here from the captured
documents, not read back from the code.
"""

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.metric_inputs import (
    YEAR_END_START_FIELDS,
    MetricInputsFailure,
    ShareCountPath,
    YearEnds,
    YearEndShareCount,
    anchor_year_end_scope,
    resolve_balance_sheet_values_at,
    resolve_share_count_series,
    resolve_year_ends,
)
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from tests._sec_instants import ANNUAL_FIXTURES, NOW, FixtureFetcher, load
from tests.analysis.shared._metric_input_rig import LIVE_NOW, FactsStub, rig

F = FinancialField
_T = date(2025, 12, 31)
_T1 = date(2024, 12, 31)
_T2 = date(2023, 12, 31)
_FILED = datetime(2026, 2, 20, tzinfo=UTC)
_ANCHOR = AnchorYearEnd(_T, "0000000001-26-000001", "10-K", date(2026, 2, 20), {})
_ACCESSION = "0000000001-26-000001"
_OLDER = "0000000001-25-000001"
_FIELDS = (F.NET_INCOME, F.SALES, F.OPERATING_CASH_FLOW)


@dataclass(frozen=True)
class _Period:
    """A completed annual period as one filing reports it."""

    end: date
    start: date
    available: datetime = _FILED
    value: float = 1.0


def _year(end: date, *, days: int | None = None, **keywords: Any) -> _Period:
    """Return the period that ends on ``end``: a calendar year, or the ``days`` + 1 days that end on ``end``."""
    start = date(end.year - 1, end.month, end.day) + timedelta(days=1) if days is None else end - timedelta(days=days)
    return _Period(end, start, **keywords)


class _Annuals(FactsStub):
    """A provider whose completed-annual answers come from a table of periods."""

    def __init__(
        self,
        periods: Mapping[FinancialField, Sequence[_Period]],
        *,
        reverse: bool = False,
        error: BaseException | None = None,
        not_available_as_of: str | None = None,
    ) -> None:
        super().__init__(error=error, not_available_as_of=not_available_as_of)
        self.periods = dict(periods)
        self.reverse = reverse

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        """Answer the field's periods, in the table's order or reversed."""
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
                "us-gaap:Stub",
                NOW,
                basis=request.basis,
                currency="USD",
                observation_period_start=datetime.combine(item.start, datetime.min.time(), tzinfo=UTC),
                observation_period_end=datetime.combine(item.end, datetime.min.time(), tzinfo=UTC),
                available_at=item.available,
                fiscal_year=item.end.year,
                period_kind=PeriodKind.COMPLETED_ANNUAL,
                provider_fact_id=f"stub:{request.field_name.value}:{item.end}:{item.start}:{item.available:%Y%m%d}",
            )
            for item in self.periods.get(request.field_name, ())
        )
        return tuple(reversed(facts)) if self.reverse else facts


def _everywhere(*periods: _Period) -> dict[FinancialField, list[_Period]]:
    """Return the same periods for each listed start-date field."""
    return {name: list(periods) for name in _FIELDS}


def _year_ends(stub: FactsStub, *, as_of: datetime | None = None) -> YearEnds | InputUnavailable | MetricInputsFailure:
    return resolve_year_ends(InputResolver(stub, clock=lambda: LIVE_NOW), anchor=_ANCHOR, ticker="SYN", as_of=as_of)


def _ends(outcome: object) -> YearEnds:
    assert isinstance(outcome, YearEnds)
    return outcome


def _unavailable(value: object) -> InputUnavailable:
    assert isinstance(value, InputUnavailable)
    return value


# --- the field list ------------------------------------------------------------------------------------------------


def test_the_start_date_fields_are_net_income_sales_and_operating_cash_flow_in_that_order() -> None:
    assert YEAR_END_START_FIELDS == (F.NET_INCOME, F.SALES, F.OPERATING_CASH_FLOW)


# --- the derivation ------------------------------------------------------------------------------------------------


def test_each_earlier_year_end_is_the_day_before_the_start_of_the_period_that_follows() -> None:
    stub = _Annuals(_everywhere(_year(_T), _year(_T1), _year(_T2)))
    ends = _ends(_year_ends(stub))
    assert (ends.year_end, ends.prior, ends.second_prior) == (_T, _T1, _T2)
    assert ends.available_dates() == (_T, _T1, _T2)
    assert [request.field_name for request in stub.requests] == list(_FIELDS)


def test_the_result_does_not_depend_on_the_order_of_the_providers_answer() -> None:
    periods = _everywhere(_year(_T2), _year(_T), _year(_T1))
    assert _year_ends(_Annuals(periods)) == _year_ends(_Annuals(periods, reverse=True))


def test_the_year_ends_follow_a_fifty_two_week_calendar() -> None:
    end, middle, early = date(2025, 11, 2), date(2024, 10, 27), date(2023, 10, 29)
    stub = _Annuals(
        _everywhere(
            _Period(end, middle + timedelta(days=1)),
            _Period(middle, early + timedelta(days=1)),
            _Period(early, date(2022, 10, 31)),
        )
    )
    anchor = AnchorYearEnd(end, _ACCESSION, "10-K", date(2025, 12, 18), {})
    ends = _ends(
        resolve_year_ends(InputResolver(stub, clock=lambda: LIVE_NOW), anchor=anchor, ticker="SYN", as_of=None)
    )
    assert (ends.prior, ends.second_prior) == (middle, early)


def test_a_first_year_registrant_gets_both_earlier_year_ends_from_the_anchor_filings_comparatives() -> None:
    comparatives = _everywhere(_year(_T), _year(_T1))
    ends = _ends(_year_ends(_Annuals(comparatives)))
    assert (ends.prior, ends.second_prior) == (_T1, _T2)


def test_a_missing_period_for_the_prior_year_breaks_the_chain_at_the_second_prior_year_end() -> None:
    ends = _ends(_year_ends(_Annuals(_everywhere(_year(_T)))))
    assert ends.prior == _T1
    second = _unavailable(ends.second_prior)
    assert second.reason_code is ReasonCode.MISSING_FACT
    assert ends.available_dates() == (_T, _T1)


def test_a_transition_period_that_is_not_a_fiscal_year_breaks_the_chain() -> None:
    transition = _year(_T1, days=181)
    ends = _ends(_year_ends(_Annuals(_everywhere(_year(_T), transition))))
    assert ends.prior == _T1
    assert _unavailable(ends.second_prior).reason_code is ReasonCode.INCOMPATIBLE_PERIOD


def test_no_period_for_the_anchor_year_makes_both_earlier_year_ends_unavailable_for_the_same_reason() -> None:
    ends = _ends(_year_ends(_Annuals(_everywhere(_year(_T1), _year(_T2)))))
    prior, second = _unavailable(ends.prior), _unavailable(ends.second_prior)
    assert prior.reason_code is second.reason_code is ReasonCode.MISSING_FACT
    assert prior is second
    assert ends.available_dates() == (_T,)


@pytest.mark.parametrize(
    ("days_before", "available"),
    [(334, False), (335, True), (365, True), (395, True), (396, False)],
)
def test_the_derived_year_end_must_be_335_to_395_days_before_the_later_one(days_before: int, available: bool) -> None:
    start = _T - timedelta(days=days_before - 1)
    ends = _ends(_year_ends(_Annuals(_everywhere(_Period(_T, start)))))
    if available:
        assert ends.prior == start - timedelta(days=1)
    else:
        assert _unavailable(ends.prior).reason_code is ReasonCode.INCOMPATIBLE_PERIOD
        assert _unavailable(ends.second_prior).reason_code is ReasonCode.INCOMPATIBLE_PERIOD


@pytest.mark.parametrize(("days_before", "available"), [(334, False), (335, True), (395, True), (396, False)])
def test_the_bounds_apply_again_between_the_prior_and_the_second_prior_year_end(
    days_before: int, available: bool
) -> None:
    prior_start = _T1 - timedelta(days=days_before - 1)
    ends = _ends(_year_ends(_Annuals(_everywhere(_year(_T), _Period(_T1, prior_start)))))
    assert ends.prior == _T1
    if available:
        assert ends.second_prior == prior_start - timedelta(days=1)
    else:
        assert _unavailable(ends.second_prior).reason_code is ReasonCode.INCOMPATIBLE_PERIOD


def test_fields_that_disagree_on_the_start_date_make_the_year_end_ambiguous() -> None:
    periods = _everywhere(_year(_T), _year(_T1))
    periods[F.SALES] = [_year(_T, days=363), _year(_T1)]
    ends = _ends(_year_ends(_Annuals(periods)))
    prior = _unavailable(ends.prior)
    assert prior.reason_code is ReasonCode.AMBIGUOUS_FACT
    assert "net_income" in prior.reason
    assert _unavailable(ends.second_prior).reason_code is ReasonCode.AMBIGUOUS_FACT


def test_a_disagreement_only_at_the_prior_year_leaves_the_prior_year_end_and_spoils_the_second() -> None:
    periods = _everywhere(_year(_T), _year(_T1))
    periods[F.OPERATING_CASH_FLOW] = [_year(_T), _year(_T1, days=363)]
    ends = _ends(_year_ends(_Annuals(periods)))
    assert ends.prior == _T1
    assert _unavailable(ends.second_prior).reason_code is ReasonCode.AMBIGUOUS_FACT


def test_two_latest_versions_of_one_field_with_different_starts_are_ambiguous() -> None:
    periods = _everywhere(_year(_T), _year(_T1))
    periods[F.NET_INCOME] = [_year(_T), _year(_T, days=363), _year(_T1)]
    assert _unavailable(_ends(_year_ends(_Annuals(periods))).prior).reason_code is ReasonCode.AMBIGUOUS_FACT


def test_only_the_latest_available_version_of_a_field_gives_its_start_date() -> None:
    older = datetime(2025, 2, 20, tzinfo=UTC)
    periods = _everywhere(_year(_T), _year(_T1))
    periods[F.NET_INCOME] = [_year(_T, days=363, available=older), _year(_T), _year(_T1)]
    ends = _ends(_year_ends(_Annuals(periods)))
    assert (ends.prior, ends.second_prior) == (_T1, _T2)


def test_no_listed_field_present_makes_the_year_end_missing_and_no_other_field_stands_in() -> None:
    stub = _Annuals({F.GROSS_PROFIT: [_year(_T), _year(_T1)], F.PRETAX_INCOME: [_year(_T)]})
    ends = _ends(_year_ends(stub))
    prior = _unavailable(ends.prior)
    assert prior.reason_code is ReasonCode.MISSING_FACT
    assert prior is ends.second_prior


def test_a_issuer_that_tags_no_net_income_gets_its_year_ends_from_the_other_fields() -> None:
    periods = {F.SALES: [_year(_T), _year(_T1)], F.OPERATING_CASH_FLOW: [_year(_T), _year(_T1)]}
    ends = _ends(_year_ends(_Annuals(periods)))
    assert (ends.prior, ends.second_prior) == (_T1, _T2)


def test_a_single_field_present_is_enough_and_a_second_field_that_disagrees_still_spoils_the_year() -> None:
    alone = _ends(_year_ends(_Annuals({F.SALES: [_year(_T), _year(_T1)]})))
    assert (alone.prior, alone.second_prior) == (_T1, _T2)
    spoiled = _ends(_year_ends(_Annuals({F.SALES: [_year(_T)], F.NET_INCOME: [_year(_T, days=360)]})))
    assert _unavailable(spoiled.prior).reason_code is ReasonCode.AMBIGUOUS_FACT


def test_a_period_filed_after_the_boundary_makes_the_year_end_derived_from_it_unavailable() -> None:
    boundary = datetime(2026, 6, 1, tzinfo=UTC)
    late = datetime(2026, 9, 1, tzinfo=UTC)
    stub = _Annuals(_everywhere(_year(_T), _year(_T1, available=late)))
    ends = _ends(_year_ends(stub, as_of=boundary))
    assert ends.prior == _T1
    assert _unavailable(ends.second_prior).reason_code is ReasonCode.NOT_AVAILABLE_AS_OF


def test_a_registrant_with_nothing_public_at_the_boundary_is_returned_once() -> None:
    stub = _Annuals({}, not_available_as_of="First annual report filed later.")
    outcome = _unavailable(_year_ends(stub))
    assert (outcome.reason_code, outcome.reason) == (ReasonCode.NOT_AVAILABLE_AS_OF, "First annual report filed later.")
    assert len(stub.requests) == 1


def test_a_provider_failure_is_returned_not_raised() -> None:
    failure = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    outcome = _year_ends(_Annuals({}, error=failure))
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "net_income"
    assert outcome.reason_code is ReasonCode.PROVIDER_ERROR


def test_a_second_prior_year_end_cannot_be_known_when_the_prior_is_not() -> None:
    reason = InputUnavailable(ReasonCode.MISSING_FACT, "none")
    with pytest.raises(ValueError, match="second prior"):
        YearEnds(_T, reason, _T2)
    assert YearEnds(_T, reason, reason).available_dates() == (_T,)


# --- the share-count series, synthetic ----------------------------------------------------------------------------

_DIRECT = "us-gaap:CommonStockSharesOutstanding"
_DERIVED = "derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares"


@dataclass(frozen=True)
class _Count:
    """A share count as one filing reports it."""

    value: float
    provider_field: str = _DIRECT
    notes: tuple[str, ...] = (f"accession={_ACCESSION}",)


class _Counts(FactsStub):
    """A provider whose share-count series answers come from a table."""

    def __init__(
        self,
        table: Mapping[date, _Count | InstantAbsence],
        *,
        reverse: bool = False,
        error: BaseException | None = None,
    ) -> None:
        super().__init__(error=error)
        self.table = dict(table)
        self.reverse = reverse

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:  # noqa: ARG002
        """Answer each requested date from the table."""
        self.series_requests.append(request)
        if self.error is not None:
            raise self.error
        facts: list[ProviderFact] = []
        absences: list[InstantAbsence] = []
        for day in request.period_ends:
            held = self.table.get(day) or InstantAbsence(day, InstantAbsenceReason.NOT_TAGGED, "not tagged")
            if isinstance(held, _Count):
                facts.append(
                    ProviderFact(
                        FinancialSubjectKind.SECURITY,
                        request.subject_id,
                        request.field_name,
                        held.value,
                        FinancialUnit.SHARES,
                        request.provider_id,
                        held.provider_field,
                        NOW,
                        basis="fiscal_year_end",
                        observation_period_end=datetime.combine(day, datetime.max.time(), tzinfo=UTC),
                        available_at=_FILED,
                        period_kind=PeriodKind.INSTANT,
                        provider_fact_id=f"{day}:{held.provider_field}",
                        notes=held.notes,
                    )
                )
            else:
                absences.append(held)
        if self.reverse:
            facts.reverse()
            absences.reverse()
        return InstantSeriesFacts(tuple(facts), tuple(absences))


def _counts(
    stub: FactsStub, years: Sequence[date] = (_T, _T1, _T2), *, as_of: datetime | None = None
) -> Mapping[date, YearEndShareCount | InputUnavailable] | InputUnavailable | MetricInputsFailure:
    return resolve_share_count_series(
        InputResolver(stub, clock=lambda: LIVE_NOW), ticker="SYN", year_ends=years, as_of=as_of
    )


def _series(outcome: object) -> Mapping[date, YearEndShareCount | InputUnavailable]:
    assert not isinstance(outcome, (InputUnavailable, MetricInputsFailure))
    return outcome  # type: ignore[return-value]


def _count(value: object) -> YearEndShareCount:
    assert isinstance(value, YearEndShareCount)
    return value


def test_a_direct_count_carries_its_accession_its_path_and_its_unit_in_shares() -> None:
    result = _series(_counts(_Counts({_T: _Count(900.0), _T1: _Count(950.0), _T2: _Count(990.0)})))
    held = _count(result[_T])
    assert (held.count.value, held.accession, held.path) == (900.0, _ACCESSION, ShareCountPath.DIRECT)
    assert (held.count.units, held.count.currency) == ("shares", None)
    assert set(result) == {_T, _T1, _T2}


def test_a_count_issued_less_treasury_names_its_path_and_the_one_filing_both_terms_came_from() -> None:
    stub = _Counts({_T: _Count(800.0, _DERIVED), _T1: _Count(850.0, _DERIVED, (f"accession={_OLDER}",))})
    result = _series(_counts(stub, (_T, _T1)))
    assert (_count(result[_T]).path, _count(result[_T]).accession) == (ShareCountPath.ISSUED_LESS_TREASURY, _ACCESSION)
    assert _count(result[_T1]).accession == _OLDER


def test_counts_from_different_filings_and_by_different_paths_are_each_kept_with_their_own_origin() -> None:
    stub = _Counts({_T: _Count(900.0), _T1: _Count(850.0, _DERIVED, (f"accession={_OLDER}",))})
    result = _series(_counts(stub, (_T, _T1)))
    newer, older = _count(result[_T]), _count(result[_T1])
    assert newer.accession != older.accession
    assert newer.path is not older.path


def test_a_count_whose_provenance_names_two_filings_or_none_is_unavailable() -> None:
    two = _Count(800.0, _DERIVED, (f"accession={_ACCESSION}; accession={_OLDER}",))
    none = _Count(790.0, _DIRECT, ())
    result = _series(_counts(_Counts({_T: two, _T1: none}), (_T, _T1)))
    assert _unavailable(result[_T]).reason_code is ReasonCode.AMBIGUOUS_FACT
    assert _unavailable(result[_T1]).reason_code is ReasonCode.MISSING_FACT


def test_two_notes_that_name_the_same_filing_are_one_filing() -> None:
    twice = _Count(800.0, _DERIVED, (f"accession={_ACCESSION}", f"issued_source=x; accession={_ACCESSION}"))
    assert _count(_series(_counts(_Counts({_T: twice}), (_T,)))[_T]).accession == _ACCESSION


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (InstantAbsenceReason.NOT_TAGGED, ReasonCode.MISSING_FACT),
        (InstantAbsenceReason.CONFLICT, ReasonCode.AMBIGUOUS_FACT),
        (InstantAbsenceReason.BASIS_MISMATCH, ReasonCode.INCOMPATIBLE_SCOPE),
        (InstantAbsenceReason.AFTER_BOUNDARY, ReasonCode.NOT_AVAILABLE_AS_OF),
    ],
)
def test_an_absent_count_is_that_years_reason_and_the_other_years_stay(
    reason: InstantAbsenceReason, code: ReasonCode
) -> None:
    stub = _Counts({_T: _Count(900.0), _T1: InstantAbsence(_T1, reason, "why"), _T2: _Count(990.0)})
    result = _series(_counts(stub))
    assert _unavailable(result[_T1]) == InputUnavailable(code, "why")
    assert _count(result[_T]).count.value == 900.0
    assert _count(result[_T2]).count.value == 990.0


def test_every_year_end_after_the_boundary_is_returned_once() -> None:
    late = {day: InstantAbsence(day, InstantAbsenceReason.AFTER_BOUNDARY, "after.") for day in (_T, _T1)}
    outcome = _unavailable(_counts(_Counts(late), (_T, _T1)))
    assert (outcome.reason_code, outcome.reason) == (ReasonCode.NOT_AVAILABLE_AS_OF, "after.")


def test_the_series_does_not_depend_on_the_order_of_the_dates_or_of_the_answer() -> None:
    table = {_T: _Count(900.0), _T1: _Count(950.0), _T2: _Count(990.0)}
    expected = _series(_counts(_Counts(table)))
    stub = _Counts(table, reverse=True)
    assert _series(_counts(stub, (_T1, _T2, _T, _T1))) == expected
    assert stub.series_requests[0].period_ends == (_T2, _T1, _T)
    assert len(stub.series_requests) == 1


def test_a_provider_failure_in_the_series_is_returned_not_raised() -> None:
    failure = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    outcome = _counts(_Counts({}, error=failure))
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "common_shares_outstanding"


def test_no_year_end_is_an_error_and_a_share_count_is_not_a_balance_sheet_amount() -> None:
    with pytest.raises(ValueError, match="At least one"):
        _counts(_Counts({}), ())
    with pytest.raises(ValueError, match="share count"):
        resolve_balance_sheet_values_at(
            InputResolver(_Counts({}), clock=lambda: LIVE_NOW),
            ticker="SYN",
            fields=[F.TOTAL_ASSETS, F.COMMON_SHARES_OUTSTANDING],
            year_ends=[_T],
            as_of=None,
        )


# --- the captured fixtures, through the real SEC adapter -----------------------------------------------------------


def _merged(ticker: str) -> dict[str, Any]:
    """Return the Company Facts of the balance-sheet fixture with the annual fixture's concepts added."""
    facts = copy.deepcopy(load(ticker)["companyfacts"])
    for taxonomy, concepts in load(ticker, ANNUAL_FIXTURES)["companyfacts"]["facts"].items():
        known = facts["facts"].setdefault(taxonomy, {})
        known.update({name: node for name, node in concepts.items() if name not in known})
    assert isinstance(facts, dict)
    return facts


def _captured(
    ticker: str, as_of: datetime | None = None, *, facts: dict[str, Any] | None = None
) -> tuple[YearEnds, Mapping[date, YearEndShareCount | InputUnavailable]]:
    """Return the year-ends and the share-count series the assembly finds for a captured issuer."""
    chosen = rig(ticker, fetcher=FixtureFetcher(ticker, companyfacts=facts or _merged(ticker)))
    with anchor_year_end_scope(chosen.resolver, ticker=ticker, as_of=as_of) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        ends = resolve_year_ends(chosen.resolver, anchor=anchor, ticker=ticker, as_of=as_of)
        assert isinstance(ends, YearEnds)
        counts = resolve_share_count_series(
            chosen.resolver, ticker=ticker, year_ends=ends.available_dates(), as_of=as_of
        )
    return ends, _series(counts)


def _apple() -> tuple[YearEnds, Mapping[date, YearEndShareCount | InputUnavailable]]:
    return _captured("AAPL", datetime(2024, 11, 15, tzinfo=UTC))


def test_apples_year_ends_follow_its_fifty_two_week_fiscal_calendar() -> None:
    ends, _ = _apple()
    assert (ends.year_end, ends.prior, ends.second_prior) == (date(2024, 9, 28), date(2023, 9, 30), date(2022, 9, 24))


def test_apples_counts_at_both_year_ends_are_direct_and_from_the_fiscal_2024_filing() -> None:
    _, counts = _apple()
    accession = "0000320193-24-000123"
    now, before = _count(counts[date(2024, 9, 28)]), _count(counts[date(2023, 9, 30)])
    assert (now.count.value, now.accession, now.path) == (15_116_786_000.0, accession, ShareCountPath.DIRECT)
    assert (before.count.value, before.accession, before.path) == (15_550_061_000.0, accession, ShareCountPath.DIRECT)


def test_apples_count_two_years_back_comes_from_the_fiscal_2023_filing() -> None:
    _, counts = _apple()
    oldest = _count(counts[date(2022, 9, 24)])
    assert (oldest.count.value, oldest.accession) == (15_943_425_000.0, "0000320193-23-000106")


def test_the_boundary_after_the_fiscal_2024_filing_excludes_the_later_filing_from_the_fixture_anchor() -> None:
    chosen = rig("AAPL", fetcher=FixtureFetcher("AAPL", companyfacts=_merged("AAPL")))
    with anchor_year_end_scope(chosen.resolver, ticker="AAPL", as_of=datetime(2024, 10, 31, tzinfo=UTC)) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        assert anchor.accession == "0000320193-23-000106"
        assert anchor.year_end == date(2023, 9, 30)


def test_monster_tags_no_net_income_and_still_gets_its_year_ends_and_counts() -> None:
    assert "NetIncomeLoss" not in load("MNST", ANNUAL_FIXTURES)["companyfacts"]["facts"]["us-gaap"]
    ends, counts = _captured("MNST")
    assert (ends.prior, ends.second_prior) == (date(2024, 12, 31), date(2023, 12, 31))
    filing = "0001104659-26-020831"
    assert (_count(counts[date(2025, 12, 31)]).count.value, _count(counts[date(2025, 12, 31)]).accession) == (
        978_113_000.0,
        filing,
    )
    assert (_count(counts[date(2024, 12, 31)]).count.value, _count(counts[date(2024, 12, 31)]).accession) == (
        973_079_000.0,
        filing,
    )
    assert _count(counts[date(2023, 12, 31)]).accession == "0001410578-25-000248"


def test_monsters_count_issued_less_treasury_agrees_with_its_direct_count_when_the_direct_one_is_not_tagged() -> None:
    facts = _merged("MNST")
    del facts["facts"]["us-gaap"]["CommonStockSharesOutstanding"]
    _, counts = _captured("MNST", facts=facts)
    derived = _count(counts[date(2025, 12, 31)])
    assert derived.path is ShareCountPath.ISSUED_LESS_TREASURY
    assert derived.count.value == 1_132_906_000.0 - 154_793_000.0 == 978_113_000.0
    assert derived.accession == "0001104659-26-020831"
    assert (derived.count.units, derived.count.currency) == ("shares", None)


def test_the_classes_of_a_multi_class_issuer_are_refused_and_issued_less_treasury_is_not_tried() -> None:
    facts = _merged("MNST")
    rows = facts["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"]
    twin = next(row for row in rows if row["end"] == "2025-12-31")
    rows.append({**twin, "val": twin["val"] // 2})
    _, counts = _captured("MNST", facts=facts)
    refused = _unavailable(counts[date(2025, 12, 31)])
    assert refused.reason_code is ReasonCode.AMBIGUOUS_FACT
    assert _count(counts[date(2024, 12, 31)]).count.value == 973_079_000.0


def test_deeres_count_a_year_back_comes_from_the_earlier_filing_that_reported_it() -> None:
    ends, counts = _captured("DE")
    assert ends.available_dates() == (date(2025, 11, 2), date(2024, 10, 27), date(2023, 10, 29))
    assert [(_count(counts[day]).count.value, _count(counts[day]).accession) for day in ends.available_dates()] == [
        (270_400_000.0, "0001104659-25-122321"),
        (271_800_000.0, "0001558370-24-016169"),
        (281_600_000.0, "0001558370-23-019812"),
    ]


def test_jpmorgans_counts_are_direct_and_all_from_the_latest_filing() -> None:
    _, counts = _captured("JPM")
    assert {day: (_count(item).count.value, _count(item).accession) for day, item in counts.items()} == {
        date(2025, 12, 31): (2_696_200_000.0, "0001628280-26-008131"),
        date(2024, 12, 31): (2_797_600_000.0, "0001628280-26-008131"),
        date(2023, 12, 31): (2_876_600_000.0, "0001628280-26-008131"),
    }


def test_nutriens_ifrs_direct_count_is_found_for_the_earlier_years_and_not_for_the_latest() -> None:
    ends, counts = _captured("NTR")
    assert ends.available_dates() == (date(2025, 12, 31), date(2024, 12, 31), date(2023, 12, 31))
    assert _unavailable(counts[date(2025, 12, 31)]).reason_code is ReasonCode.MISSING_FACT
    earlier = _count(counts[date(2024, 12, 31)])
    assert (earlier.count.value, earlier.accession, earlier.path) == (
        491_025_446.0,
        "0001193125-25-041502",
        ShareCountPath.DIRECT,
    )
    assert earlier.count.provider_field == "ifrs-full:NumberOfSharesOutstanding"


@pytest.mark.parametrize("ticker", ["SAP", "WMT"])
def test_an_issuer_that_tags_no_balance_sheet_count_gets_none_at_any_year_end(ticker: str) -> None:
    _, counts = _captured(ticker)
    assert {item.reason_code for item in counts.values() if isinstance(item, InputUnavailable)} == {
        ReasonCode.MISSING_FACT
    }
    assert len(counts) == 3


def test_alphabets_combined_count_is_a_single_direct_value_per_year_end() -> None:
    _, counts = _captured("GOOGL")
    assert _count(counts[date(2025, 12, 31)]).count.value == 12_088_000_000.0
    assert _count(counts[date(2024, 12, 31)]).count.value == 12_211_000_000.0


def test_the_year_ends_of_the_captured_regression_set_follow_each_issuers_calendar() -> None:
    expected = {
        "JPM": (date(2024, 12, 31), date(2023, 12, 31)),
        "WMT": (date(2025, 1, 31), date(2024, 1, 31)),
        "DE": (date(2024, 10, 27), date(2023, 10, 29)),
        "SAP": (date(2024, 12, 31), date(2023, 12, 31)),
        "HON": (date(2024, 12, 31), date(2023, 12, 31)),
    }
    for ticker, (prior, second) in expected.items():
        ends, _ = _captured(ticker)
        assert (ends.prior, ends.second_prior) == (prior, second), ticker
