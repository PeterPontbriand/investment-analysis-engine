"""Balance-sheet values at named fiscal year-ends from SEC Company Facts, and the share-count paths beside them."""

import copy
import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.data.financial.facts import (
    COVER_PAGE_BASIS,
    INSTANT_SERIES_FIELDS,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderAmountSource,
    ProviderFact,
    _expected_unit,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.sec_edgar import financial_facts as module
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from tests._sec_instants import (
    FIXTURES,
    NOW,
    REGRESSION_SET,
    FixtureFetcher,
    adapter_for,
    load,
    series,
)

_REASON = InstantAbsenceReason

# --- a synthetic issuer ------------------------------------------------------------------------------------------

_OLD, _MID, _NEW = "0000000001-24-000001", "0000000001-25-000001", "0000000001-26-000001"
_ACCEPTED = {_OLD: "2024-02-20T16:00:00.000Z", _MID: "2025-02-20T16:00:00.000Z", _NEW: "2026-02-20T16:00:00.000Z"}
_Y23, _Y24, _Y25 = date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31)


def _row(end: str, val: float, accn: str, *, form: str = "10-K") -> dict[str, Any]:
    return {"end": end, "val": val, "accn": accn, "fy": 2025, "fp": "FY", "form": form, "filed": "2026-02-20"}


def _document(  # noqa: PLR0913
    concepts: dict[str, list[tuple[str, list[dict[str, Any]]]]],
    *,
    namespace: str = "us-gaap",
    cik: int = 1,
    accessions: dict[str, str] | None = None,
    forms: dict[str, str] | None = None,
    extra_facts: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a Company Facts payload and a submissions payload for the synthetic issuer."""
    accepted = accessions or _ACCEPTED
    facts: dict[str, Any] = {namespace: {name: {"units": dict(units)} for name, units in concepts.items()}}
    facts.update(extra_facts or {})
    names = list(accepted)
    submissions = {
        "tickers": ["SYN"],
        "filings": {
            "recent": {
                "accessionNumber": names,
                "form": [(forms or {}).get(name, "10-K") for name in names],
                "filingDate": [accepted[name][:10] for name in names],
                "acceptanceDateTime": [accepted[name] for name in names],
                "primaryDocument": ["a.htm"] * len(names),
            }
        },
    }
    return {"cik": cik, "entityName": "Synthetic", "facts": facts}, submissions


def _fetcher(companyfacts: object, submissions: object) -> FixtureFetcher:
    fetcher = FixtureFetcher("WMT", companyfacts=companyfacts, submissions=submissions)
    fetcher.documents["company_tickers.json"] = {"0": {"cik_str": 1, "ticker": "SYN", "title": "Synthetic"}}
    return fetcher


def _series(
    concepts: dict[str, list[tuple[str, list[dict[str, Any]]]]],
    field: FinancialField = FinancialField.TOTAL_ASSETS,
    *,
    ends: tuple[date, ...] = (_Y23, _Y24, _Y25),
    as_of: datetime | None = None,
    **document: Any,
) -> InstantSeriesFacts:
    facts, submissions = _document(concepts, **document)
    adapter = adapter_for("WMT", _fetcher(facts, submissions))
    request = InstantSeriesRequest("SYN", field, SEC_PROVIDER_ID, ends, as_of=as_of)
    return adapter.fetch_instant_series(request, effective_as_of=NOW)


def _values(result: InstantSeriesFacts) -> dict[date, float]:
    return {fact.observation_period_end.date(): fact.value for fact in result.facts if fact.observation_period_end}


def _reasons(result: InstantSeriesFacts) -> dict[date, InstantAbsenceReason]:
    return {item.period_end: item.reason for item in result.absences}


def _assets(*rows: tuple[str, float, str]) -> dict[str, list[tuple[str, list[dict[str, Any]]]]]:
    return {"Assets": [("USD", [_row(end, value, accn) for end, value, accn in rows])]}


# --- fields, units and the request --------------------------------------------------------------------------------


def test_the_seventeen_instant_fields_are_currency_fields_and_the_older_routing_is_unchanged() -> None:
    assert len(INSTANT_SERIES_FIELDS) == 17
    assert all(_expected_unit(field) is FinancialUnit.CURRENCY for field in INSTANT_SERIES_FIELDS)
    assert _expected_unit(FinancialField.EPS) is FinancialUnit.CURRENCY_PER_SHARE
    assert _expected_unit(FinancialField.BVPS) is FinancialUnit.CURRENCY_PER_SHARE
    assert _expected_unit(FinancialField.CURRENT_PRICE) is FinancialUnit.CURRENCY_PER_SHARE
    assert _expected_unit(FinancialField.STOCKHOLDERS_EQUITY) is FinancialUnit.CURRENCY
    assert _expected_unit(FinancialField.COMMON_SHARES_OUTSTANDING) is FinancialUnit.SHARES
    assert _expected_unit(FinancialField.CURRENT_AAA_YIELD) is FinancialUnit.PERCENTAGE_POINTS


def test_a_provider_fact_of_a_new_field_requires_a_currency_amount() -> None:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    common: dict[str, Any] = {
        "subject_kind": FinancialSubjectKind.SECURITY,
        "subject_id": "SYN",
        "field_name": FinancialField.TOTAL_ASSETS,
        "value": 5.0,
        "provider_id": "sec_edgar",
        "provider_field": "us-gaap:Assets",
        "retrieved_at": stamp,
        "observation_period_end": stamp,
        "period_kind": PeriodKind.INSTANT,
    }
    assert ProviderFact(units=FinancialUnit.CURRENCY, currency="usd", **common).currency == "USD"
    with pytest.raises(ValueError, match="requires units CURRENCY"):
        ProviderFact(units=FinancialUnit.CURRENCY_PER_SHARE, currency="USD", **common)
    with pytest.raises(ValueError, match="requires a currency"):
        ProviderFact(units=FinancialUnit.CURRENCY, **common)
    with pytest.raises(ValueError, match="period_kind=instant"):
        ProviderFact(units=FinancialUnit.CURRENCY, currency="USD", **{**common, "observation_period_start": stamp})
    with pytest.raises(ValueError, match="period_kind=instant"):
        ProviderFact(units=FinancialUnit.CURRENCY, currency="USD", **{**common, "observation_period_end": None})


def test_the_latest_only_request_does_not_serve_the_new_fields() -> None:
    fetcher = FixtureFetcher("WMT")
    adapter = adapter_for("WMT", fetcher)
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "WMT", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, basis="fiscal_year_end"
    )
    assert adapter.fetch_facts(request, effective_as_of=NOW) == ()
    assert fetcher.calls == []


def test_a_request_names_instant_fields_and_consecutive_fiscal_year_ends() -> None:
    request = InstantSeriesRequest(" wmt ", FinancialField.NET_PPE, " SEC_EDGAR ", (_Y25, _Y23, _Y24))
    assert request.subject_id == "WMT"
    assert request.provider_id == "sec_edgar"
    assert request.period_ends == (_Y23, _Y24, _Y25)
    for field in (FinancialField.EPS, FinancialField.COMMON_SHARES_OUTSTANDING, FinancialField.CURRENT_PRICE):
        with pytest.raises(ValueError, match="not a balance-sheet field"):
            InstantSeriesRequest("WMT", field, "sec_edgar", (_Y25,))
    with pytest.raises(ValueError, match="at least one"):
        InstantSeriesRequest("WMT", FinancialField.NET_PPE, "sec_edgar", ())
    with pytest.raises(ValueError, match="timezone-aware"):
        InstantSeriesRequest("WMT", FinancialField.NET_PPE, "sec_edgar", (_Y25,), as_of=datetime(2026, 1, 1))  # noqa: DTZ001


def test_fifty_two_and_fifty_three_week_years_are_consecutive_but_quarters_and_stubs_are_not() -> None:
    deere = (date(2023, 10, 29), date(2024, 10, 27), date(2025, 11, 2))
    assert InstantSeriesRequest("DE", FinancialField.TOTAL_ASSETS, "sec_edgar", deere).period_ends == deere
    for ends in (
        (date(2025, 6, 30), date(2025, 12, 31)),
        (date(2025, 3, 31), date(2025, 12, 31)),
        (date(2024, 12, 31), date(2025, 12, 31), date(2026, 3, 31)),
        (date(2024, 12, 31), date(2025, 12, 31), date(2025, 12, 31)),
        (date(2023, 12, 31), date(2025, 12, 31)),
        (date(2024, 12, 31), date(2026, 2, 5)),
    ):
        with pytest.raises(ValueError, match="consecutive fiscal year-ends"):
            InstantSeriesRequest("DE", FinancialField.TOTAL_ASSETS, "sec_edgar", ends)
    assert InstantSeriesRequest("DE", FinancialField.TOTAL_ASSETS, "sec_edgar", (date(2024, 12, 31), date(2025, 12, 5)))


def test_absences_and_answers_are_checked() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        InstantAbsence(_Y25, _REASON.NOT_TAGGED, " ")
    fact = _series_fact()
    with pytest.raises(ValueError, match="once"):
        InstantSeriesFacts(facts=(fact,), absences=(InstantAbsence(_Y25, _REASON.NOT_TAGGED, "x"),))
    with pytest.raises(ValueError, match="instant facts only"):
        InstantSeriesFacts(facts=(replace(fact, period_kind=None),))


def _series_fact() -> ProviderFact:
    return _series(_assets(("2025-12-31", 10.0, _NEW)), ends=(_Y25,)).facts[0]


def test_an_amount_source_keeps_a_negative_value_and_demands_evidence() -> None:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    common: dict[str, Any] = {
        "subject_id": "SYN",
        "provider_id": "sec_edgar",
        "provider_field": "us-gaap:X",
        "value": -4.0,
        "currency": "USD",
        "retrieved_at": stamp,
        "observation_period_end": stamp,
        "available_at": stamp,
        "provider_fact_id": "a:b",
    }
    assert ProviderAmountSource(**common).value == -4.0
    with pytest.raises(ValueError, match="non-empty"):
        ProviderAmountSource(**{**common, "currency": " "})
    with pytest.raises(ValueError, match="finite"):
        ProviderAmountSource(**{**common, "value": float("inf")})
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderAmountSource(**{**common, "available_at": datetime(2026, 1, 1)})  # noqa: DTZ001


# --- exact-date selection -----------------------------------------------------------------------------------------


def test_three_year_ends_come_back_by_exact_date_from_the_filings_that_report_them() -> None:
    result = series("WMT", FinancialField.TOTAL_ASSETS)

    assert [
        (fact.observation_period_end.date(), fact.value) for fact in result.facts if fact.observation_period_end
    ] == [
        (date(2024, 1, 31), 252_399_000_000.0),
        (date(2025, 1, 31), 260_823_000_000.0),
        (date(2026, 1, 31), 284_668_000_000.0),
    ]
    assert result.absences == ()
    assert all(
        fact.period_kind is PeriodKind.INSTANT and fact.observation_period_start is None for fact in result.facts
    )
    assert {fact.provider_field for fact in result.facts} == {"us-gaap:Assets"}
    assert all(fact.units is FinancialUnit.CURRENCY and fact.currency == "USD" for fact in result.facts)


def test_the_newest_balance_sheet_is_never_returned_for_an_earlier_date() -> None:
    result = _series(_assets(("2025-12-31", 300.0, _NEW), ("2024-12-31", 200.0, _NEW)))

    assert _values(result) == {_Y24: 200.0, _Y25: 300.0}
    assert _reasons(result) == {_Y23: _REASON.NOT_TAGGED}


def test_a_year_end_the_anchor_does_not_report_comes_from_an_earlier_eligible_filing() -> None:
    result = _series(
        _assets(
            ("2025-12-31", 300.0, _NEW),
            ("2024-12-31", 200.0, _NEW),
            ("2024-12-31", 200.0, _MID),
            ("2023-12-31", 100.0, _MID),
        )
    )

    assert _values(result) == {_Y23: 100.0, _Y24: 200.0, _Y25: 300.0}
    by_year = {fact.observation_period_end.date(): fact for fact in result.facts if fact.observation_period_end}
    assert _MID in by_year[_Y23].notes[0]
    assert _NEW in by_year[_Y25].notes[0]


def test_a_later_comparative_restatement_replaces_the_earlier_value_only_once_it_is_knowable() -> None:
    rows = _assets(("2024-12-31", 200.0, _MID), ("2024-12-31", 210.0, _NEW), ("2025-12-31", 300.0, _NEW))

    assert _values(_series(rows, ends=(_Y24, _Y25))) == {_Y24: 210.0, _Y25: 300.0}
    before_restatement = datetime(2026, 1, 1, tzinfo=UTC)
    earlier = _series(rows, ends=(_Y24, _Y25), as_of=before_restatement)
    assert _values(earlier) == {_Y24: 200.0}
    assert _reasons(earlier) == {_Y25: _REASON.NOT_TAGGED}


def test_a_filing_accepted_after_the_boundary_is_ignored_and_a_later_year_end_is_after_the_boundary() -> None:
    rows = _assets(("2024-12-31", 200.0, _MID), ("2025-12-31", 300.0, _NEW), ("2023-12-31", 100.0, _OLD))
    result = _series(rows, as_of=datetime(2025, 6, 1, tzinfo=UTC))

    assert _values(result) == {_Y23: 100.0, _Y24: 200.0}
    assert _reasons(result) == {_Y25: _REASON.AFTER_BOUNDARY}
    one_second = datetime(2025, 2, 20, 16, 0, 0, tzinfo=UTC)
    assert _values(_series(rows, ends=(_Y24,), as_of=one_second)) == {_Y24: 200.0}
    assert _reasons(_series(rows, ends=(_Y24,), as_of=datetime(2024, 1, 1, tzinfo=UTC))) == {
        _Y24: _REASON.NO_ANCHOR_FILING
    }


def test_a_conflicting_duplicate_of_equal_priority_is_reported_not_chosen() -> None:
    same_filing = _series(_assets(("2025-12-31", 300.0, _NEW), ("2025-12-31", 301.0, _NEW)), ends=(_Y25,))
    assert same_filing.facts == ()
    assert _reasons(same_filing) == {_Y25: _REASON.CONFLICT}

    identical = _series(_assets(("2025-12-31", 300.0, _NEW), ("2025-12-31", 300.0, _NEW)), ends=(_Y25,))
    assert _values(identical) == {_Y25: 300.0}

    accepted = dict(_ACCEPTED, **{"0000000001-26-000002": _ACCEPTED[_NEW]})
    twin = _series(
        _assets(("2025-12-31", 300.0, _NEW), ("2025-12-31", 301.0, "0000000001-26-000002")),
        ends=(_Y25,),
        accessions=accepted,
    )
    assert _reasons(twin) == {_Y25: _REASON.CONFLICT}


def test_a_payload_of_another_issuer_is_unsupported() -> None:
    result = _series(_assets(("2025-12-31", 300.0, _NEW)), ends=(_Y25,), cik=2)

    assert result.facts == ()
    assert _reasons(result) == {_Y25: _REASON.UNSUPPORTED}


def test_a_value_from_a_filing_on_another_taxonomy_is_not_used() -> None:
    facts, submissions = _document(_assets(("2025-12-31", 300.0, _NEW), ("2024-12-31", 200.0, _MID)))
    facts["facts"]["ifrs-full"] = {"Assets": {"units": {"USD": [_row("2024-12-31", 199.0, _OLD)]}}}
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"].append(_row("2023-12-31", 100.0, _OLD))
    request = InstantSeriesRequest("SYN", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (_Y23, _Y24, _Y25))
    result = adapter_for("WMT", _fetcher(facts, submissions)).fetch_instant_series(request, effective_as_of=NOW)

    assert _values(result) == {_Y24: 200.0, _Y25: 300.0}
    assert _reasons(result) == {_Y23: _REASON.BASIS_MISMATCH}


def test_an_anchor_filing_on_both_or_neither_taxonomy_is_unsupported() -> None:
    facts, submissions = _document(_assets(("2025-12-31", 300.0, _NEW)))
    facts["facts"]["ifrs-full"] = {"Assets": {"units": {"USD": [_row("2025-12-31", 300.0, _NEW)]}}}
    request = InstantSeriesRequest("SYN", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (_Y25,))
    result = adapter_for("WMT", _fetcher(facts, submissions)).fetch_instant_series(request, effective_as_of=NOW)
    assert _reasons(result) == {_Y25: _REASON.UNSUPPORTED}


def test_one_currency_runs_through_a_series() -> None:
    concepts = {
        "Assets": [
            ("USD", [_row("2025-12-31", 300.0, _NEW), _row("2024-12-31", 200.0, _NEW)]),
            ("EUR", [_row("2023-12-31", 90.0, _MID)]),
            ("USDX", [_row("2022-12-31", 1.0, _MID)]),
        ]
    }
    result = _series(concepts)

    assert _values(result) == {_Y24: 200.0, _Y25: 300.0}
    assert _reasons(result) == {_Y23: _REASON.BASIS_MISMATCH}
    assert {fact.currency for fact in result.facts} == {"USD"}


def test_unreadable_observations_are_skipped() -> None:
    concepts: dict[str, list[tuple[str, list[Any]]]] = {
        "Assets": [
            (
                "USD",
                [
                    _row("2025-12-31", 300.0, _NEW),
                    {**_row("2024-12-31", 1.0, _NEW), "start": "2024-01-01"},
                    {**_row("2024-12-31", True, _NEW)},
                    {**_row("2024-12-31", float("inf"), _NEW)},
                    {**_row("not-a-date", 1.0, _NEW)},
                    {**_row("2024-12-31", 1.0, "unknown-accession")},
                    {"end": "2024-12-31", "val": 1.0},
                    "garbage",
                ],
            )
        ]
    }
    concepts["Assets"].append(("USD1", [_row("2024-12-31", 5.0, _NEW)]))
    assert _values(_series(concepts)) == {_Y25: 300.0}


def test_a_series_with_no_annual_filing_is_absent_for_that_reason() -> None:
    result = _series(_assets(("2025-12-31", 300.0, _NEW)), forms={_NEW: "10-Q", _MID: "8-K", _OLD: "S-1"})
    assert _reasons(result) == dict.fromkeys((_Y23, _Y24, _Y25), _REASON.NO_ANCHOR_FILING)


def test_an_unknown_ticker_is_absent_and_another_provider_is_unsupported() -> None:
    adapter = adapter_for("WMT")
    unknown = InstantSeriesRequest("ZZZZ", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (_Y25,))
    assert _reasons(adapter.fetch_instant_series(unknown, effective_as_of=NOW)) == {_Y25: _REASON.NO_ANCHOR_FILING}
    other = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, "yfinance", (_Y25,))
    assert _reasons(adapter.fetch_instant_series(other, effective_as_of=NOW)) == {_Y25: _REASON.UNSUPPORTED}


def test_inside_an_analysis_scope_the_series_reuses_the_snapshot_and_another_issuer_does_not() -> None:
    fetcher = FixtureFetcher("WMT")
    adapter = adapter_for("WMT", fetcher)
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2026, 1, 31),))
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        calls = len(fetcher.calls)
        first = adapter.fetch_instant_series(request, effective_as_of=NOW)
        assert len(fetcher.calls) == calls
        # The snapshot is WMT's; a request for another subject reads its own documents.
        other = InstantSeriesRequest("ZZZZ", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2026, 1, 31),))
        assert _reasons(adapter.fetch_instant_series(other, effective_as_of=NOW)) == {
            date(2026, 1, 31): _REASON.NO_ANCHOR_FILING
        }
    assert _values(first) == {date(2026, 1, 31): 284_668_000_000.0}


def test_the_series_without_a_scope_fetches_the_documents_itself() -> None:
    fetcher = FixtureFetcher("WMT")
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2026, 1, 31),))
    result = adapter_for("WMT", fetcher).fetch_instant_series(request, effective_as_of=NOW)
    assert _values(result) == {date(2026, 1, 31): 284_668_000_000.0}
    assert sum("companyfacts" in call for call in fetcher.calls) == 1


def test_a_company_document_that_is_not_an_object_is_a_provider_error() -> None:
    facts, submissions = _document(_assets(("2025-12-31", 300.0, _NEW)))
    broken = _fetcher(facts, submissions)
    broken.documents["/companyfacts/"] = []
    request = InstantSeriesRequest("SYN", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (_Y25,))
    with pytest.raises(FinancialProviderError):
        adapter_for("WMT", broken).fetch_instant_series(request, effective_as_of=NOW)


# --- the regression set, field by field ---------------------------------------------------------------------------


def test_values_match_the_rendered_statements_the_evidence_checked() -> None:
    expected = {
        ("WMT", FinancialField.TOTAL_ASSETS): (date(2026, 1, 31), 284_668_000_000.0),
        ("WMT", FinancialField.RETAINED_EARNINGS): (date(2026, 1, 31), 104_774_000_000.0),
        ("WMT", FinancialField.RECEIVABLES): (date(2026, 1, 31), 11_172_000_000.0),
        ("WMT", FinancialField.LEASE_LIABILITIES_AS_DEBT): (date(2026, 1, 31), 6_761_000_000.0),
        ("WMT", FinancialField.NONCONTROLLING_INTEREST): (date(2026, 1, 31), 6_270_000_000.0),
        ("SAP", FinancialField.TOTAL_ASSETS): (date(2025, 12, 31), 70_362_000_000.0),
        ("SAP", FinancialField.NET_PPE): (date(2025, 12, 31), 4_497_000_000.0),
        ("SAP", FinancialField.RECEIVABLES): (date(2025, 12, 31), 5_790_000_000.0),
        ("SAP", FinancialField.LEASE_LIABILITIES_AS_DEBT): (date(2025, 12, 31), 1_684_000_000.0),
        ("NTR", FinancialField.SHORT_TERM_BORROWINGS): (date(2025, 12, 31), 873_000_000.0),
        ("NTR", FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT): (date(2025, 12, 31), 513_000_000.0),
        ("PLD", FinancialField.PREFERRED_STOCK): (date(2025, 12, 31), 63_948_000.0),
        ("GOOGL", FinancialField.SHORT_TERM_INVESTMENTS): (date(2025, 12, 31), 96_135_000_000.0),
        ("MRNA", FinancialField.SHORT_TERM_INVESTMENTS): (date(2025, 12, 31), 3_204_000_000.0),
        ("MNST", FinancialField.LONG_TERM_INVESTMENTS): (date(2025, 12, 31), 487_329_000.0),
    }
    for (ticker, field), (day, value) in expected.items():
        result = series(ticker, field, count=1)
        assert _values(result) == {day: value}, (ticker, field)


def test_every_field_of_every_regression_issuer_resolves_or_says_why_not() -> None:
    for ticker in REGRESSION_SET:
        for field in sorted(INSTANT_SERIES_FIELDS, key=lambda item: item.value):
            result = series(ticker, field)
            dates = {fact.observation_period_end.date() for fact in result.facts if fact.observation_period_end}
            dates |= {item.period_end for item in result.absences}
            assert len(dates) == 3, (ticker, field)
            assert all(fact.currency == ("EUR" if ticker == "SAP" else "USD") for fact in result.facts)


def test_unsupported_mappings_are_reported_unsupported_under_ifrs_only() -> None:
    unsupported = (
        FinancialField.SHORT_TERM_INVESTMENTS,
        FinancialField.LONG_TERM_INVESTMENTS,
        FinancialField.NONCURRENT_LONG_TERM_DEBT,
        FinancialField.LONG_TERM_DEBT_TOTAL,
        FinancialField.PREFERRED_STOCK,
    )
    for ticker in ("SAP", "NTR"):
        for field in unsupported:
            result = series(ticker, field)
            assert result.facts == ()
            assert set(_reasons(result).values()) == {_REASON.UNSUPPORTED}
            assert "not zero" in result.absences[0].detail
    for field in unsupported:
        assert _REASON.UNSUPPORTED not in set(_reasons(series("WMT", field)).values())


def test_a_taxonomy_without_a_filing_on_the_requested_concept_is_not_tagged_not_zero() -> None:
    result = series("JPM", FinancialField.CURRENT_ASSETS)
    assert result.facts == ()
    assert set(_reasons(result).values()) == {_REASON.NOT_TAGGED}


def test_deere_has_an_unclassified_balance_sheet_and_honeywell_a_classified_one() -> None:
    for field in (FinancialField.CURRENT_ASSETS, FinancialField.CURRENT_LIABILITIES, FinancialField.NET_PPE):
        assert series("DE", field).facts == ()
    assert _values(series("HON", FinancialField.CURRENT_ASSETS, count=1)) == {date(2025, 12, 31): 30_387_000_000.0}
    assert series("DE", FinancialField.TOTAL_ASSETS).facts[0].observation_period_end == datetime(
        2023, 10, 29, 23, 59, 59, 999999, tzinfo=UTC
    )


def test_a_direct_debt_total_is_returned_beside_its_parts_and_is_never_added_to_them() -> None:
    day = date(2025, 12, 31)
    total = _values(series("GOOGL", FinancialField.LONG_TERM_DEBT_TOTAL, count=1))[day]
    parts = (
        _values(series("GOOGL", FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT, count=1))[day],
        _values(series("GOOGL", FinancialField.NONCURRENT_LONG_TERM_DEBT, count=1))[day],
    )
    assert total == 49_085_000_000.0
    assert sum(parts) == 48_543_000_000.0
    assert total != sum(parts)
    assert total != total + sum(parts)
    honeywell = series("HON", FinancialField.LONG_TERM_DEBT_TOTAL, count=1)
    assert _values(honeywell) == {day: 29_046_000_000.0}
    for field in (FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT, FinancialField.NONCURRENT_LONG_TERM_DEBT):
        assert series("HON", field, count=1).facts == ()


def test_commercial_paper_is_not_the_current_portion_and_operating_leases_are_not_the_lease_field() -> None:
    concepts = {
        "CommercialPaper": [("USD", [_row("2025-12-31", 77.0, _NEW)])],
        "OperatingLeaseLiability": [("USD", [_row("2025-12-31", 55.0, _NEW)])],
        "DebtCurrent": [("USD", [_row("2025-12-31", 99.0, _NEW)])],
    }
    for field in (
        FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT,
        FinancialField.SHORT_TERM_BORROWINGS,
        FinancialField.LEASE_LIABILITIES_AS_DEBT,
    ):
        assert _series(concepts, field, ends=(_Y25,)).facts == ()
    finance = {**concepts, "FinanceLeaseLiability": [("USD", [_row("2025-12-31", 11.0, _NEW)])]}
    assert _values(_series(finance, FinancialField.LEASE_LIABILITIES_AS_DEBT, ends=(_Y25,))) == {_Y25: 11.0}
    ifrs = {"LeaseLiabilities": [("EUR", [_row("2025-12-31", 8.0, _NEW)])]}
    assert _values(_series(ifrs, FinancialField.LEASE_LIABILITIES_AS_DEBT, ends=(_Y25,), namespace="ifrs-full")) == {
        _Y25: 8.0
    }


# --- equivalent concepts (H10) and net PP&E under IFRS (H11) -------------------------------------------------------


def test_equivalent_concepts_are_a_priority_list_with_one_concept_for_the_run() -> None:
    for ticker, field, concept in (
        ("WMT", FinancialField.RECEIVABLES, "us-gaap:ReceivablesNetCurrent"),
        ("GOOGL", FinancialField.SHORT_TERM_INVESTMENTS, "us-gaap:MarketableSecuritiesCurrent"),
        ("MRNA", FinancialField.SHORT_TERM_INVESTMENTS, "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
        ("MNST", FinancialField.SHORT_TERM_INVESTMENTS, "us-gaap:ShortTermInvestments"),
        ("MNST", FinancialField.RECEIVABLES, "us-gaap:AccountsReceivableNetCurrent"),
    ):
        result = series(ticker, field)
        assert {fact.provider_field for fact in result.facts} == {concept}, (ticker, field)
        assert len(result.facts) == 3


def test_the_first_listed_concept_wins_and_another_is_never_filled_in() -> None:
    concepts = {
        "AccountsReceivableNetCurrent": [("USD", [_row("2025-12-31", 30.0, _NEW), _row("2024-12-31", 20.0, _NEW)])],
        "ReceivablesNetCurrent": [
            ("USD", [_row("2025-12-31", 31.0, _NEW), _row("2024-12-31", 21.0, _NEW), _row("2023-12-31", 11.0, _MID)])
        ],
    }
    result = _series(concepts, FinancialField.RECEIVABLES)

    assert _values(result) == {_Y24: 20.0, _Y25: 30.0}
    assert {fact.provider_field for fact in result.facts} == {"us-gaap:AccountsReceivableNetCurrent"}
    assert _reasons(result) == {_Y23: _REASON.OTHER_CONCEPT}
    assert "none is substituted" in result.absences[0].detail
    only_second = {"ReceivablesNetCurrent": concepts["ReceivablesNetCurrent"]}
    assert _values(_series(only_second, FinancialField.RECEIVABLES)) == {_Y23: 11.0, _Y24: 21.0, _Y25: 31.0}
    nothing_listed = _series(_assets(("2025-12-31", 1.0, _NEW)), FinancialField.RECEIVABLES)
    assert _reasons(nothing_listed) == dict.fromkeys((_Y23, _Y24, _Y25), _REASON.NOT_TAGGED)


def test_net_ppe_under_ifrs_uses_the_plain_concept_or_the_right_of_use_concept_and_never_their_sum() -> None:
    for ticker in ("SAP", "NTR"):
        result = series(ticker, FinancialField.NET_PPE)
        assert {fact.provider_field for fact in result.facts} == {
            "ifrs-full:PropertyPlantAndEquipmentIncludingRightofuseAssets"
        }
    both = {
        "PropertyPlantAndEquipment": [("EUR", [_row("2025-12-31", 70.0, _NEW)])],
        "PropertyPlantAndEquipmentIncludingRightofuseAssets": [("EUR", [_row("2025-12-31", 100.0, _NEW)])],
    }
    result = _series(both, FinancialField.NET_PPE, ends=(_Y25,), namespace="ifrs-full")
    assert _values(result) == {_Y25: 70.0}
    assert result.facts[0].provider_field == "ifrs-full:PropertyPlantAndEquipment"
    assert 170.0 not in _values(result).values()


# --- derived total liabilities (H3, H8) ---------------------------------------------------------------------------


def _terms(
    *, total: float | None = 500.0, equity: float | None = 120.0, temporary: dict[str, float] | None = None
) -> dict[str, list[tuple[str, list[dict[str, Any]]]]]:
    concepts: dict[str, list[tuple[str, list[dict[str, Any]]]]] = {}
    if total is not None:
        concepts["LiabilitiesAndStockholdersEquity"] = [("USD", [_row("2025-12-31", total, _NEW)])]
    if equity is not None:
        concepts["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = [
            ("USD", [_row("2025-12-31", equity, _NEW)])
        ]
    for name, value in (temporary or {}).items():
        concepts[name] = [("USD", [_row("2025-12-31", value, _NEW)])]
    return concepts


def test_total_liabilities_is_derived_from_one_filing_where_it_is_not_tagged() -> None:
    result = _series(_terms(), FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))

    fact = result.facts[0]
    assert fact.value == 380.0
    assert fact.provider_field.startswith("derived:us-gaap:LiabilitiesAndStockholdersEquity-")
    assert fact.source_transformation is not None
    assert [source.value for source in fact.source_facts if isinstance(source, ProviderAmountSource)] == [500.0, 120.0]
    assert fact.available_at == datetime(2026, 2, 20, 16, tzinfo=UTC)


def test_temporary_equity_is_subtracted_once_with_the_first_tagged_concept() -> None:
    first = "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests"
    second = "RedeemableNoncontrollingInterestEquityCarryingAmount"

    both = _series(_terms(temporary={first: 51.0, second: 51.0}), FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))
    assert both.facts[0].value == 329.0
    assert len(both.facts[0].source_facts) == 3
    only_second = _series(_terms(temporary={second: 20.0}), FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))
    assert only_second.facts[0].value == 360.0
    assert only_second.facts[0].provider_field.endswith(second)


def test_the_derivation_equals_the_tagged_value_for_every_us_gaap_issuer_that_tags_both() -> None:
    checked: set[str] = set()
    for ticker in REGRESSION_SET:
        document = load(ticker)
        if "us-gaap" not in document["companyfacts"]["facts"]:
            continue
        direct = series(ticker, FinancialField.TOTAL_LIABILITIES)
        stripped = copy.deepcopy(document["companyfacts"])
        stripped["facts"]["us-gaap"].pop("Liabilities", None)
        fetcher = FixtureFetcher(ticker, companyfacts=stripped)
        derived = series(ticker, FinancialField.TOTAL_LIABILITIES, adapter=adapter_for(ticker, fetcher))
        tagged = {
            fact.observation_period_end: fact.value for fact in direct.facts if "derived" not in fact.provider_field
        }
        for fact in derived.facts:
            if fact.observation_period_end in tagged and fact.provider_field.startswith("derived:"):
                assert fact.value == tagged[fact.observation_period_end], (ticker, fact.observation_period_end)
                checked.add(ticker)
    assert {"PLD", "DE"} <= checked


def test_the_derivation_needs_every_term_in_one_filing() -> None:
    assert _series(_terms(equity=None), FinancialField.TOTAL_LIABILITIES, ends=(_Y25,)).facts == ()
    assert _series(_terms(total=None), FinancialField.TOTAL_LIABILITIES, ends=(_Y25,)).facts == ()
    split = _terms(equity=None)
    split["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = [
        ("USD", [_row("2025-12-31", 120.0, _MID)])
    ]
    result = _series(split, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))
    assert result.facts == ()
    assert _reasons(result) == {_Y25: _REASON.NOT_TAGGED}


def test_a_derivation_that_disagrees_with_itself_is_reported() -> None:
    twice = _terms()
    twice["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"][0][1].append(
        _row("2025-12-31", 121.0, _NEW)
    )
    assert _reasons(_series(twice, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {_Y25: _REASON.CONFLICT}
    temporary_twice = _terms(temporary={"RedeemableNoncontrollingInterestEquityCarryingAmount": 5.0})
    temporary_twice["RedeemableNoncontrollingInterestEquityCarryingAmount"][0][1].append(_row("2025-12-31", 6.0, _NEW))
    assert _reasons(_series(temporary_twice, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {
        _Y25: _REASON.CONFLICT
    }
    negative = _terms(total=100.0, equity=120.0)
    assert _reasons(_series(negative, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {_Y25: _REASON.CONFLICT}


def test_the_terms_of_a_derivation_must_share_one_currency() -> None:
    mixed = _terms()
    mixed["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = [
        ("EUR", [_row("2025-12-31", 120.0, _NEW)])
    ]
    assert _reasons(_series(mixed, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {_Y25: _REASON.BASIS_MISMATCH}
    temporary = _terms()
    temporary["RedeemableNoncontrollingInterestEquityCarryingAmount"] = [("EUR", [_row("2025-12-31", 5.0, _NEW)])]
    assert _reasons(_series(temporary, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {
        _Y25: _REASON.BASIS_MISMATCH
    }


def test_a_tagged_total_is_read_directly_and_a_conflicting_one_is_not_derived_over() -> None:
    tagged = {"Liabilities": [("USD", [_row("2025-12-31", 380.0, _NEW)])], **_terms()}
    assert (
        _series(tagged, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,)).facts[0].provider_field == "us-gaap:Liabilities"
    )
    disagreeing = {
        "Liabilities": [("USD", [_row("2025-12-31", 380.0, _NEW), _row("2025-12-31", 381.0, _NEW)])],
        **_terms(),
    }
    assert _reasons(_series(disagreeing, FinancialField.TOTAL_LIABILITIES, ends=(_Y25,))) == {_Y25: _REASON.CONFLICT}


def test_the_ifrs_derivation_is_not_offered_because_rounding_makes_it_inexact() -> None:
    document = load("SAP")
    stripped = copy.deepcopy(document["companyfacts"])
    stripped["facts"]["ifrs-full"].pop("Liabilities")
    assert {"EquityAndLiabilities", "Equity"} <= set(stripped["facts"]["ifrs-full"])
    adapter = adapter_for("SAP", FixtureFetcher("SAP", companyfacts=stripped))
    result = series("SAP", FinancialField.TOTAL_LIABILITIES, adapter=adapter)
    assert result.facts == ()
    assert set(_reasons(result).values()) == {_REASON.NOT_TAGGED}
    tagged = series("SAP", FinancialField.TOTAL_LIABILITIES, count=1)
    assert _values(tagged) == {date(2025, 12, 31): 25_288_000_000.0}


def test_total_liabilities_of_the_filers_that_tag_none_comes_from_the_derivation() -> None:
    expected = {
        "DUK": (date(2025, 12, 31), 142_717_000_000.0),
        "WMT": (date(2026, 1, 31), 178_488_000_000.0),
        "HON": (date(2025, 12, 31), 58_651_000_000.0),
    }
    for ticker, (day, value) in expected.items():
        result = series(ticker, FinancialField.TOTAL_LIABILITIES, count=1)
        assert _values(result) == {day: value}
        assert result.facts[0].provider_field.startswith("derived:")
    monster = series("MNST", FinancialField.TOTAL_LIABILITIES)
    assert monster.facts == ()
    assert set(_reasons(monster).values()) == {_REASON.NOT_TAGGED}


# --- share counts: the paths, the cover page and the coverage of the regression set ---------------------------------


def _count(ticker: str, basis: str = "fiscal_year_end") -> tuple[ProviderFact, ...]:
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, ticker, FinancialField.COMMON_SHARES_OUTSTANDING, SEC_PROVIDER_ID, basis=basis
    )
    return adapter_for(ticker).fetch_facts(request, effective_as_of=NOW)


def test_share_count_coverage_of_the_regression_set_at_the_latest_year_end() -> None:
    # Each path the existing resolver reads, plus the IFRS direct path, at the latest year-end: the field's result.
    direct = "us-gaap:CommonStockSharesOutstanding"
    expected: dict[str, tuple[str, float] | None] = {
        "JPM": (direct, 2_696_200_000.0),
        "PLD": (direct, 929_153_000.0),
        "DUK": (direct, 778_000_000.0),
        "DE": (direct, 270_400_000.0),
        "MRNA": (direct, 394_000_000.0),
        "MNST": (direct, 978_113_000.0),
        "GOOGL": (direct, 12_088_000_000.0),
        "HON": (direct, 635_300_000.0),
        "WMT": None,
        "SAP": None,
        "NTR": ("ifrs-full:NumberOfSharesOutstanding", 491_025_446.0),
    }
    assert set(expected) == set(REGRESSION_SET)
    for ticker, result in expected.items():
        facts = _count(ticker)
        if result is None:
            assert facts == (), ticker
            continue
        assert (facts[0].provider_field, facts[0].value) == result, ticker
        latest = REGRESSION_SET[ticker]
        assert facts[0].observation_period_end is not None
        if ticker == "NTR":
            # The IFRS count is for the year before the latest year-end; an older year is never a stand-in.
            assert facts[0].observation_period_end.date() == date(2024, 12, 31) != latest
        else:
            assert facts[0].observation_period_end.date() == latest


def test_the_issued_minus_treasury_fallback_agrees_with_the_direct_count_where_both_exist() -> None:
    document = load("MNST")
    stripped = copy.deepcopy(document["companyfacts"])
    stripped["facts"]["us-gaap"].pop("CommonStockSharesOutstanding")
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        "MNST",
        FinancialField.COMMON_SHARES_OUTSTANDING,
        SEC_PROVIDER_ID,
        basis="fiscal_year_end",
    )
    derived = adapter_for("MNST", FixtureFetcher("MNST", companyfacts=stripped)).fetch_facts(
        request, effective_as_of=NOW
    )
    assert derived[0].value == _count("MNST")[0].value == 978_113_000.0
    assert derived[0].provider_field.startswith("derived:")


def test_walmart_and_sap_have_a_cover_page_count_and_nutrien_has_none() -> None:
    walmart = _count("WMT", COVER_PAGE_BASIS)[0]
    assert (walmart.value, walmart.provider_field, walmart.basis) == (
        7_972_402_501.0,
        "dei:EntityCommonStockSharesOutstanding",
        COVER_PAGE_BASIS,
    )
    assert walmart.observation_period_end == datetime(2026, 3, 11, 23, 59, 59, 999999, tzinfo=UTC)
    assert walmart.available_at is not None
    assert walmart.available_at > walmart.observation_period_end.replace(hour=0)
    assert "0000104169-26-000055" in walmart.notes[0]
    sap = _count("SAP", COVER_PAGE_BASIS)[0]
    assert (sap.value, sap.observation_period_end) == (
        1_228_504_232.0,
        datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    )
    assert _count("NTR", COVER_PAGE_BASIS) == ()
    assert _count("GOOGL", COVER_PAGE_BASIS) == ()


def test_the_year_end_basis_never_returns_the_cover_page_count() -> None:
    assert _count("WMT") == ()
    assert _count("SAP") == ()
    assert {fact.basis for ticker in REGRESSION_SET for fact in _count(ticker)} == {"fiscal_year_end"}


def _cover(
    rows: list[dict[str, Any]], *, accepted: dict[str, str] | None = None, as_of: datetime | None = None
) -> tuple[ProviderFact, ...]:
    facts, submissions = _document(
        {},
        extra_facts={"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": rows}}}},
        accessions=accepted,
    )
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        "SYN",
        FinancialField.COMMON_SHARES_OUTSTANDING,
        SEC_PROVIDER_ID,
        basis=COVER_PAGE_BASIS,
        as_of=as_of,
    )
    return adapter_for("WMT", _fetcher(facts, submissions)).fetch_facts(request, effective_as_of=NOW)


def test_a_cover_page_count_is_one_non_dimensional_total_of_the_anchor_filing() -> None:
    assert _cover([_row("2026-02-10", 1_000.0, _NEW)])[0].value == 1_000.0
    duplicate = [_row("2026-02-10", 1_000.0, _NEW), _row("2026-02-10", 1_000.0, _NEW)]
    assert len(_cover(duplicate)) == 1
    # Two totals in the anchor filing (a filer with per-class counts): no count.
    assert _cover([_row("2026-02-10", 1_000.0, _NEW), _row("2026-02-10", 500.0, _NEW)]) == ()
    assert _cover([_row("2026-02-10", 1_000.0, _NEW), _row("2026-02-12", 1_000.0, _NEW)]) == ()
    # A count of an earlier filing is not the anchor's.
    assert _cover([_row("2025-02-10", 900.0, _MID)]) == ()
    assert _cover([]) == ()


def test_a_cover_page_count_that_cannot_be_used_is_not_returned() -> None:
    for bad in (0.0, -5.0, float("inf"), True):
        assert _cover([_row("2026-02-10", bad, _NEW)]) == ()
    assert _cover([_row("not-a-date", 1_000.0, _NEW)]) == ()
    assert _cover([{"end": "2026-02-10", "accn": _NEW}]) == ()
    assert _cover([_row("2026-02-10", 1_000.0, _NEW)], as_of=datetime(2026, 2, 15, tzinfo=UTC)) == ()
    assert _cover([_row("2026-02-10", 1_000.0, _NEW)], as_of=datetime(2026, 3, 1, tzinfo=UTC))[0].value == 1_000.0
    # A cover date after the boundary is not knowable then, even where the filing is.
    assert _cover([_row("2026-04-10", 1_000.0, _NEW)], as_of=datetime(2026, 3, 1, tzinfo=UTC)) == ()


def test_a_cover_page_count_is_read_with_the_anchor_filing_without_a_scope_too() -> None:
    fetcher = FixtureFetcher("WMT")
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        "WMT",
        FinancialField.COMMON_SHARES_OUTSTANDING,
        SEC_PROVIDER_ID,
        basis=COVER_PAGE_BASIS,
        as_of=datetime(2025, 6, 1, tzinfo=UTC),
    )
    # At a boundary before the fiscal 2026 filing the anchor is the fiscal 2025 filing, whose cover is not in the
    # fixture: no count, and never the later filing's count.
    assert adapter_for("WMT", fetcher).fetch_facts(request, effective_as_of=NOW) == ()


def test_the_fixture_checksums_match_the_files() -> None:
    lines = (FIXTURES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ")[1]: line.split("  ")[0] for line in lines}
    assert set(listed) == {path.name for path in FIXTURES.glob("*.json")}
    for name, digest in listed.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


def test_the_regression_set_is_the_one_the_evidence_names() -> None:
    anchors = {
        "JPM": ("0001628280-26-008131", 19617),
        "PLD": ("0001193125-26-051453", 1045609),
        "DUK": ("0001326160-26-000014", 1326160),
        "DE": ("0001104659-25-122321", 315189),
        "SAP": ("0001104659-26-020058", 1000184),
        "NTR": ("0001193125-26-081326", 1725964),
        "WMT": ("0000104169-26-000055", 104169),
        "MRNA": ("0001682852-26-000033", 1682852),
        "MNST": ("0001104659-26-020831", 865752),
        "GOOGL": ("0001652044-26-000018", 1652044),
        "HON": ("0000773840-26-000013", 773840),
    }
    assert set(REGRESSION_SET) == set(anchors)
    for ticker, (accession, cik) in anchors.items():
        document = load(ticker)
        assert (document["anchor_accession"], document["cik"]) == (accession, cik)
        assert document["anchor_year_end"] == REGRESSION_SET[ticker].isoformat()
        assert accession in document["submissions"]["filings"]["recent"]["accessionNumber"]


def test_a_snapshot_for_another_cik_is_unsupported_and_a_failure_to_read_is_an_unexpected_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = adapter_for("WMT")
    snapshot = adapter.create_analysis_snapshot(subject_id="WMT", as_of=None)
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2026, 1, 31),))
    token = module._ACTIVE_SNAPSHOT.set(replace(snapshot, cik="0000000099"))
    try:
        assert _reasons(adapter.fetch_instant_series(request, effective_as_of=NOW)) == {
            date(2026, 1, 31): _REASON.UNSUPPORTED
        }
    finally:
        module._ACTIVE_SNAPSHOT.reset(token)

    def broken(*_arguments: object) -> InstantSeriesFacts:
        raise ValueError("unreadable")

    monkeypatch.setattr(module, "select_instant_series", broken)
    with pytest.raises(FinancialProviderError, match="balance-sheet series retrieval failed") as raised:
        adapter.fetch_instant_series(request, effective_as_of=NOW)
    assert raised.value.reason_code.value == "provider_unexpected_response"
