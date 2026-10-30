"""The common share count at named fiscal year-ends: an instant series in shares, beside the latest-only path."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.data.financial.facts import (
    INSTANT_SERIES_FIELDS,
    SHARE_COUNT_SERIES_FIELD,
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    _expected_unit,
    instant_series_unit,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.sec_edgar.instant_series import (
    SEC_DERIVED_COMMON_SHARES_FIELD,
    SEC_DIRECT_COMMON_SHARES_FIELDS,
    InstantSource,
    select_instant_series,
)
from tests._sec_instants import NOW, FixtureFetcher, adapter_for

_SHARES = FinancialField.COMMON_SHARES_OUTSTANDING
_OLD, _MID, _NEW = "0000000001-24-000001", "0000000001-25-000001", "0000000001-26-000001"
_ACCEPTED = {_OLD: "2024-02-20T16:00:00.000Z", _MID: "2025-02-20T16:00:00.000Z", _NEW: "2026-02-20T16:00:00.000Z"}
_Y23, _Y24, _Y25 = date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31)
_DIRECT = "CommonStockSharesOutstanding"
_ISSUED = "CommonStockSharesIssued"
_TREASURY = "TreasuryStockCommonShares"


def _row(end: str, val: float, accn: str, *, form: str = "10-K") -> dict[str, Any]:
    return {"end": end, "val": val, "accn": accn, "fy": 2025, "fp": "FY", "form": form, "filed": "2026-02-20"}


def _adapter(concepts: dict[str, list[dict[str, Any]]], *, namespace: str = "us-gaap", form: str = "10-K") -> Any:
    """Return an adapter over a synthetic issuer whose share concepts are ``concepts``."""
    facts = {namespace: {name: {"units": {"shares": rows}} for name, rows in concepts.items()}}
    names = list(_ACCEPTED)
    submissions = {
        "tickers": ["SYN"],
        "filings": {
            "recent": {
                "accessionNumber": names,
                "form": [form] * len(names),
                "filingDate": [_ACCEPTED[name][:10] for name in names],
                "acceptanceDateTime": [_ACCEPTED[name] for name in names],
                "primaryDocument": ["a.htm"] * len(names),
            }
        },
    }
    fetcher = FixtureFetcher(
        "WMT", companyfacts={"cik": 1, "entityName": "Synthetic", "facts": facts}, submissions=submissions
    )
    fetcher.documents["company_tickers.json"] = {"0": {"cik_str": 1, "ticker": "SYN", "title": "Synthetic"}}
    return adapter_for("WMT", fetcher)


def _series(adapter: Any, ends: tuple[date, ...] = (_Y23, _Y24, _Y25), **keywords: Any) -> InstantSeriesFacts:
    request = InstantSeriesRequest("SYN", _SHARES, SEC_PROVIDER_ID, ends, **keywords)
    result: InstantSeriesFacts = adapter.fetch_instant_series(request, effective_as_of=NOW)
    return result


def _reasons(result: InstantSeriesFacts) -> dict[date, InstantAbsenceReason]:
    return {item.period_end: item.reason for item in result.absences}


def _by_day(result: InstantSeriesFacts) -> dict[date, Any]:
    return {fact.observation_period_end.date(): fact for fact in result.facts if fact.observation_period_end}


# --- the request and the unit --------------------------------------------------------------------------------------


def test_the_series_accepts_the_common_share_count_and_no_other_share_field() -> None:
    request = InstantSeriesRequest("syn", _SHARES, "SEC_EDGAR", (_Y25, _Y24))
    assert (request.subject_id, request.provider_id, request.period_ends) == ("SYN", "sec_edgar", (_Y24, _Y25))
    assert SHARE_COUNT_SERIES_FIELD is _SHARES
    for other in (FinancialField.PREFERRED_SHARES_OUTSTANDING, FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES):
        with pytest.raises(ValueError, match="not a balance-sheet field"):
            InstantSeriesRequest("SYN", other, "sec_edgar", (_Y25,))


def test_the_currency_only_field_set_is_unchanged_and_the_units_are_right() -> None:
    assert len(INSTANT_SERIES_FIELDS) == 17
    assert _SHARES not in INSTANT_SERIES_FIELDS
    assert instant_series_unit(_SHARES) is FinancialUnit.SHARES
    assert all(instant_series_unit(name) is FinancialUnit.CURRENCY for name in INSTANT_SERIES_FIELDS)
    assert _expected_unit(_SHARES) is FinancialUnit.SHARES
    for other in (FinancialField.PREFERRED_SHARES_OUTSTANDING, FinancialField.EPS):
        with pytest.raises(ValueError, match="not served by an instant series"):
            instant_series_unit(other)


# --- the direct path -----------------------------------------------------------------------------------------------


def test_a_direct_count_is_the_newest_filings_value_in_shares_with_no_currency_and_its_accession() -> None:
    rows = [
        _row("2024-12-31", 960.0, _MID),
        _row("2024-12-31", 955.0, _NEW),
        _row("2025-12-31", 900.0, _NEW),
        _row("2023-12-31", 990.0, _OLD),
    ]
    result = _series(_adapter({_DIRECT: rows}))
    found = _by_day(result)
    assert {day: fact.value for day, fact in found.items()} == {_Y23: 990.0, _Y24: 955.0, _Y25: 900.0}
    fact = found[_Y24]
    assert (fact.units, fact.currency, fact.period_kind) == (FinancialUnit.SHARES, None, PeriodKind.INSTANT)
    assert (fact.provider_field, fact.basis, fact.subject_kind) == (
        SEC_DIRECT_COMMON_SHARES_FIELDS["us-gaap"],
        "fiscal_year_end",
        FinancialSubjectKind.SECURITY,
    )
    assert f"accession={_NEW}" in fact.notes
    assert found[_Y23].provider_fact_id == f"{_OLD}:{SEC_DIRECT_COMMON_SHARES_FIELDS['us-gaap']}:shares:2023-12-31"
    assert result.absences == ()


def test_a_count_dated_another_day_is_not_taken_for_the_requested_year_end() -> None:
    result = _series(_adapter({_DIRECT: [_row("2025-12-30", 900.0, _NEW), _row("2024-12-31", 955.0, _NEW)]}))
    assert set(_by_day(result)) == {_Y24}
    assert _reasons(result) == {_Y23: InstantAbsenceReason.NOT_TAGGED, _Y25: InstantAbsenceReason.NOT_TAGGED}


def test_two_values_of_the_newest_filing_at_one_date_are_the_classes_of_a_multi_class_issuer() -> None:
    adapter = _adapter(
        {
            _DIRECT: [_row("2025-12-31", 900.0, _NEW), _row("2025-12-31", 450.0, _NEW)],
            _ISSUED: [_row("2025-12-31", 1000.0, _NEW)],
            _TREASURY: [_row("2025-12-31", 100.0, _NEW)],
        }
    )
    result = _series(adapter, ends=(_Y25,))
    assert result.facts == ()
    assert _reasons(result) == {_Y25: InstantAbsenceReason.CONFLICT}


@pytest.mark.parametrize("reported", [0.0, -5.0])
def test_a_direct_count_that_is_not_positive_is_bad_data_and_the_derived_path_is_not_tried(reported: float) -> None:
    adapter = _adapter(
        {
            _DIRECT: [_row("2025-12-31", reported, _NEW)],
            _ISSUED: [_row("2025-12-31", 1000.0, _NEW)],
            _TREASURY: [_row("2025-12-31", 100.0, _NEW)],
        }
    )
    result = _series(adapter, ends=(_Y25,))
    assert result.facts == ()
    assert _reasons(result) == {_Y25: InstantAbsenceReason.CONFLICT}
    assert "is not positive" in result.absences[0].detail
    assert SEC_DIRECT_COMMON_SHARES_FIELDS["us-gaap"] in result.absences[0].detail


def test_a_non_positive_count_in_an_older_filing_is_superseded_by_the_newest_filings_positive_one() -> None:
    adapter = _adapter({_DIRECT: [_row("2025-12-31", 0.0, _MID), _row("2025-12-31", 900.0, _NEW)]})
    assert _by_day(_series(adapter, ends=(_Y25,)))[_Y25].value == 900.0


def test_the_series_does_not_depend_on_the_order_of_the_requested_dates() -> None:
    adapter = _adapter({_DIRECT: [_row("2024-12-31", 955.0, _NEW), _row("2025-12-31", 900.0, _NEW)]})
    assert _series(adapter, ends=(_Y24, _Y25)) == _series(adapter, ends=(_Y25, _Y24))


# --- issued less treasury ------------------------------------------------------------------------------------------


def test_issued_less_treasury_comes_from_the_one_newest_filing_that_tags_both() -> None:
    adapter = _adapter(
        {
            _ISSUED: [_row("2024-12-31", 1000.0, _MID), _row("2024-12-31", 1010.0, _NEW)],
            _TREASURY: [_row("2024-12-31", 100.0, _MID), _row("2024-12-31", 90.0, _NEW)],
        }
    )
    fact = _by_day(_series(adapter, ends=(_Y24,)))[_Y24]
    assert fact.value == 920.0
    assert (fact.units, fact.currency) == (FinancialUnit.SHARES, None)
    assert fact.provider_field == SEC_DERIVED_COMMON_SHARES_FIELD
    assert fact.source_transformation == "common shares issued - treasury common shares"
    assert [source.value for source in fact.source_facts] == [1010.0, 90.0]
    assert f"accession={_NEW}" in fact.notes
    assert not any(note == f"accession={_MID}" for note in fact.notes)


def test_terms_of_different_filings_are_never_mixed() -> None:
    adapter = _adapter({_ISSUED: [_row("2025-12-31", 1000.0, _MID)], _TREASURY: [_row("2025-12-31", 100.0, _NEW)]})
    result = _series(adapter, ends=(_Y25,))
    assert result.facts == ()
    assert _reasons(result) == {_Y25: InstantAbsenceReason.NOT_TAGGED}


@pytest.mark.parametrize(
    ("issued", "treasury"),
    [(1000.0, 1000.0), (1000.0, 1200.0), (0.0, 0.0), (1000.0, -5.0)],
)
def test_a_derived_count_that_is_not_positive_is_a_conflict_not_a_count(issued: float, treasury: float) -> None:
    adapter = _adapter({_ISSUED: [_row("2025-12-31", issued, _NEW)], _TREASURY: [_row("2025-12-31", treasury, _NEW)]})
    result = _series(adapter, ends=(_Y25,))
    assert result.facts == ()
    assert _reasons(result) == {_Y25: InstantAbsenceReason.CONFLICT}


def test_disagreeing_terms_within_the_one_filing_are_a_conflict() -> None:
    adapter = _adapter(
        {
            _ISSUED: [_row("2025-12-31", 1000.0, _NEW), _row("2025-12-31", 2000.0, _NEW)],
            _TREASURY: [_row("2025-12-31", 100.0, _NEW)],
        }
    )
    assert _reasons(_series(adapter, ends=(_Y25,))) == {_Y25: InstantAbsenceReason.CONFLICT}


def test_the_derived_label_is_the_one_the_latest_only_path_gives_its_derived_count() -> None:
    concepts = {_ISSUED: [_row("2025-12-31", 1000.0, _NEW)], _TREASURY: [_row("2025-12-31", 100.0, _NEW)]}
    adapter = _adapter(concepts)
    latest_only = adapter.fetch_facts(
        FinancialFactRequest(FinancialSubjectKind.SECURITY, "SYN", _SHARES, SEC_PROVIDER_ID, basis="fiscal_year_end"),
        effective_as_of=NOW,
    )
    series_fact = _by_day(_series(_adapter(concepts), ends=(_Y25,)))[_Y25]
    assert [fact.provider_field for fact in latest_only] == [series_fact.provider_field]
    assert latest_only[0].value == series_fact.value == 900.0


# --- IFRS, absence and the other taxonomy --------------------------------------------------------------------------


def test_an_ifrs_issuer_gets_its_direct_count_and_no_issued_less_treasury_path() -> None:
    adapter = _adapter(
        {"NumberOfSharesOutstanding": [_row("2024-12-31", 491.0, _NEW, form="20-F")], "NumberOfSharesIssued": []},
        namespace="ifrs-full",
        form="20-F",
    )
    result = _series(adapter, ends=(_Y24, _Y25))
    fact = _by_day(result)[_Y24]
    assert (fact.value, fact.provider_field, fact.units, fact.currency) == (
        491.0,
        SEC_DIRECT_COMMON_SHARES_FIELDS["ifrs-full"],
        FinancialUnit.SHARES,
        None,
    )
    assert _reasons(result) == {_Y25: InstantAbsenceReason.NOT_TAGGED}


def test_a_year_end_after_the_boundary_is_absent_and_the_others_stay() -> None:
    adapter = _adapter({_DIRECT: [_row("2024-12-31", 955.0, _MID), _row("2025-12-31", 900.0, _NEW)]})
    result = _series(adapter, as_of=datetime(2025, 6, 1, tzinfo=UTC), ends=(_Y24, _Y25))
    assert {day: fact.value for day, fact in _by_day(result).items()} == {_Y24: 955.0}
    assert _reasons(result) == {_Y25: InstantAbsenceReason.AFTER_BOUNDARY}


def test_a_count_only_a_filing_on_another_taxonomy_reports_is_a_basis_mismatch() -> None:
    rows: dict[object, object] = {
        "facts": {"us-gaap": {_DIRECT: {"units": {"shares": [_row("2025-12-31", 900.0, _OLD)]}}}}
    }
    source = InstantSource(
        company_facts=rows,
        cik_matches=True,
        taxonomy="us-gaap",
        acceptance_by_accession={_OLD: datetime(2024, 2, 20, tzinfo=UTC), _NEW: datetime(2026, 2, 20, tzinfo=UTC)},
        accession_taxonomies={_OLD: frozenset({"ifrs-full"}), _NEW: frozenset({"us-gaap"})},
        retrieved_at=NOW,
        boundary=NOW,
    )
    result = select_instant_series(InstantSeriesRequest("SYN", _SHARES, SEC_PROVIDER_ID, (_Y25,)), source)
    assert result.facts == ()
    assert _reasons(result) == {_Y25: InstantAbsenceReason.BASIS_MISMATCH}


# --- through the resolver, and the latest-only path ----------------------------------------------------------------


def test_the_resolver_returns_the_share_count_in_shares_with_no_currency() -> None:
    adapter = _adapter({_DIRECT: [_row("2025-12-31", 900.0, _NEW)]})
    resolver = InputResolver(adapter, clock=lambda: NOW)
    resolution = resolver.resolve_instant_series(InstantSeriesRequest("SYN", _SHARES, SEC_PROVIDER_ID, (_Y25,)))
    (held,) = resolution.inputs
    assert (held.value, held.units, held.currency, held.period_kind) == (900.0, "shares", None, PeriodKind.INSTANT)
    assert held.field_name == "common_shares_outstanding"
    assert f"accession={_NEW}" in held.notes


def test_the_latest_only_count_is_the_same_single_value_as_before() -> None:
    adapter = adapter_for("MNST", FixtureFetcher("MNST"))
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "MNST", _SHARES, SEC_PROVIDER_ID, basis="fiscal_year_end"
    )
    with adapter.analysis_scope(subject_id="MNST", provider_id=SEC_PROVIDER_ID, as_of=None):
        (fact,) = adapter.fetch_facts(request, effective_as_of=NOW)
    assert (fact.value, fact.provider_field, fact.units) == (
        978_113_000.0,
        SEC_DIRECT_COMMON_SHARES_FIELDS["us-gaap"],
        FinancialUnit.SHARES,
    )
    assert fact.observation_period_end is not None
    assert fact.observation_period_end.date() == date(2025, 12, 31)
