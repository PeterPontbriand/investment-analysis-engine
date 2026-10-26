"""Related concepts of an absent debt component, and the extra submissions pages older year-ends come from."""

from datetime import date

from investment_analysis_engine.data.financial.facts import (
    FinancialField,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import _MAX_SUBMISSION_PAGES, SEC_PROVIDER_ID
from tests._sec_instants import NOW, FixtureFetcher, adapter_for, series
from tests.data.test_instant_series import (
    _ACCEPTED,
    _MID,
    _NEW,
    _Y23,
    _Y24,
    _Y25,
    _assets,
    _document,
    _fetcher,
    _row,
    _series,
    _values,
)

_REASON = InstantAbsenceReason
_EMPTY_PAGE: dict[str, list[str]] = {
    "accessionNumber": [],
    "form": [],
    "filingDate": [],
    "acceptanceDateTime": [],
    "primaryDocument": [],
}


def _debt(ticker: str, field: FinancialField) -> InstantSeriesFacts:
    return series(ticker, field, count=1)


def _why(result: InstantSeriesFacts) -> list[tuple[InstantAbsenceReason, str | None]]:
    return [(item.reason, item.related_concept) for item in result.absences]


# --- related concepts ---------------------------------------------------------------------------------------------


def test_deere_tags_debt_current_which_is_neither_short_term_borrowings_nor_the_current_portion() -> None:
    for field in (FinancialField.SHORT_TERM_BORROWINGS, FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT):
        result = _debt("DE", field)
        assert result.facts == ()
        assert _why(result) == [(_REASON.NOT_TAGGED, "us-gaap:DebtCurrent")]


def test_honeywell_current_and_noncurrent_debt_are_absent_with_the_lease_inclusive_concepts_named() -> None:
    current = _debt("HON", FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT)
    assert _why(current) == [(_REASON.NOT_TAGGED, "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent")]
    noncurrent = _debt("HON", FinancialField.NONCURRENT_LONG_TERM_DEBT)
    assert _why(noncurrent) == [(_REASON.NOT_TAGGED, "us-gaap:LongTermDebtAndCapitalLeaseObligations")]
    borrowings = _debt("HON", FinancialField.SHORT_TERM_BORROWINGS)
    assert _values(borrowings) == {date(2025, 12, 31): 5_893_000_000.0}
    assert not any(note.startswith("related_concept_tagged") for note in borrowings.facts[0].notes)
    lease = _debt("HON", FinancialField.LEASE_LIABILITIES_AS_DEBT).facts[0]
    assert "related_concept_tagged=us-gaap:FinanceLeaseLiabilityCurrent" in lease.notes


def test_nutriens_ifrs_noncurrent_debt_is_unsupported_and_sap_names_its_combined_concepts() -> None:
    assert _why(_debt("NTR", FinancialField.NONCURRENT_LONG_TERM_DEBT)) == [(_REASON.UNSUPPORTED, None)]
    sap = _debt("SAP", FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT)
    assert _why(sap) == [(_REASON.NOT_TAGGED, "ifrs-full:CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings")]
    assert _why(_debt("SAP", FinancialField.SHORT_TERM_BORROWINGS)) == [
        (_REASON.NOT_TAGGED, "ifrs-full:CommercialPapersIssued")
    ]


def test_alphabet_tags_every_debt_component_it_has_so_nothing_is_absent() -> None:
    day = date(2025, 12, 31)
    paper = _debt("GOOGL", FinancialField.SHORT_TERM_BORROWINGS)
    assert _values(paper) == {day: 0.0}
    assert paper.facts[0].provider_field == "us-gaap:CommercialPaper"
    for field, value in (
        (FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT, 1_996_000_000.0),
        (FinancialField.NONCURRENT_LONG_TERM_DEBT, 46_547_000_000.0),
    ):
        result = _debt("GOOGL", field)
        assert _values(result) == {day: value}
        assert result.absences == ()


def test_a_related_concept_is_reported_for_a_date_the_run_does_not_cover() -> None:
    concepts = {
        "LongTermDebtCurrent": [("USD", [_row("2025-12-31", 5.0, _NEW)])],
        "DebtCurrent": [("USD", [_row("2024-12-31", 9.0, _NEW)])],
    }
    result = _series(concepts, FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT, ends=(_Y24, _Y25))
    assert _values(result) == {_Y25: 5.0}
    assert [(a.period_end, a.reason, a.related_concept) for a in result.absences] == [
        (_Y24, _REASON.NOT_TAGGED, "us-gaap:DebtCurrent")
    ]


def test_duke_receivables_exclude_the_receivables_of_variable_interest_entities() -> None:
    result = series("DUK", FinancialField.RECEIVABLES)
    values = {fact.observation_period_end.year: fact.value for fact in result.facts if fact.observation_period_end}
    assert values == {2023: 3_019_000_000.0, 2024: 1_889_000_000.0, 2025: 16_000_000.0}
    assert all("related_concept_tagged=us-gaap:AccountsAndOtherReceivablesNetCurrent" in f.notes for f in result.facts)


# --- extra submissions pages ----------------------------------------------------------------------------------------


def _pages_read(fetcher: FixtureFetcher) -> list[str]:
    return [call.rsplit("/", 1)[1] for call in fetcher.calls if "-submissions-" in call]


def test_jpmorgan_earlier_year_ends_resolve_from_the_extra_submissions_pages() -> None:
    fetcher = FixtureFetcher("JPM")
    result = series("JPM", FinancialField.TOTAL_ASSETS, adapter=adapter_for("JPM", fetcher))

    assert _values(result) == {
        date(2023, 12, 31): 3_875_393_000_000.0,
        date(2024, 12, 31): 4_002_814_000_000.0,
        date(2025, 12, 31): 4_424_900_000_000.0,
    }
    pages = _pages_read(fetcher)
    # Newest first, stopping at the page that holds the fiscal 2024 report.
    assert len(pages) == 8
    assert pages[0] == "CIK0000019617-submissions-001.json"
    assert pages[-1] == "CIK0000019617-submissions-008.json"
    liabilities = series("JPM", FinancialField.TOTAL_LIABILITIES)
    assert _values(liabilities)[date(2023, 12, 31)] == 3_547_515_000_000.0
    # Total liabilities of 2023 is in the fiscal 2024 report only, which is in the extra pages.
    older = next(
        fact for fact in liabilities.facts if fact.observation_period_end and fact.observation_period_end.year == 2023
    )
    assert older.notes[0] == "accession=0000019617-25-000270"


def test_the_pages_are_read_once_and_only_when_the_recent_block_does_not_reach_back() -> None:
    fetcher = FixtureFetcher("JPM")
    adapter = adapter_for("JPM", fetcher)
    series("JPM", FinancialField.TOTAL_ASSETS, adapter=adapter)
    series("JPM", FinancialField.TOTAL_LIABILITIES, adapter=adapter)
    assert len(_pages_read(fetcher)) == 8

    # The newest two year-ends are in the fiscal 2025 report of the recent block: no page is read.
    recent_only = FixtureFetcher("JPM")
    request = InstantSeriesRequest(
        "JPM", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2024, 12, 31), date(2025, 12, 31))
    )
    adapter_for("JPM", recent_only).fetch_instant_series(request, effective_as_of=NOW)
    assert _pages_read(recent_only) == []
    walmart = FixtureFetcher("WMT")
    series("WMT", FinancialField.TOTAL_ASSETS, adapter=adapter_for("WMT", walmart))
    assert _pages_read(walmart) == []


def _paged(pages: int, *, hit: int | None) -> tuple[InstantSeriesFacts, FixtureFetcher]:
    """A synthetic issuer whose fiscal 2024 report sits in page ``hit`` of ``pages`` (never, when ``None``)."""
    facts, submissions = _document(
        _assets(("2025-12-31", 300.0, _NEW), ("2024-12-31", 200.0, _MID)), accessions={_NEW: _ACCEPTED[_NEW]}
    )
    names = [f"CIK{1:010d}-submissions-{number:03d}.json" for number in range(1, pages + 1)]
    listed: list[object] = [
        {
            "name": name,
            "filingFrom": f"2025-{9 - min(number, 8):02d}-01",
            "filingTo": f"2025-{9 - min(number, 8):02d}-28",
        }
        for number, name in enumerate(names)
    ]
    listed += [
        {"name": "other.json", "filingFrom": "2025-01-01", "filingTo": "2025-01-31"},
        {"name": f"CIK{2:010d}-submissions-001.json", "filingFrom": "2025-01-01", "filingTo": "2025-01-31"},
        {"name": f"CIK{1:010d}-submissions-099.json", "filingFrom": "2025-02-01", "filingTo": "2025-01-31"},
        {"name": f"CIK{1:010d}-submissions-098.json", "filingFrom": "bad", "filingTo": "2025-01-31"},
        {"name": 5, "filingFrom": "2025-01-01", "filingTo": "2025-01-31"},
        "junk",
    ]
    submissions["filings"]["files"] = listed
    fetcher = _fetcher(facts, submissions)
    fetcher.pages = dict.fromkeys(names, _EMPTY_PAGE)
    if hit is not None:
        fetcher.pages[names[hit]] = {
            "accessionNumber": [_MID],
            "form": ["10-K"],
            "filingDate": [_ACCEPTED[_MID][:10]],
            "acceptanceDateTime": [_ACCEPTED[_MID]],
            "primaryDocument": ["a.htm"],
        }
    request = InstantSeriesRequest("SYN", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (_Y23, _Y24, _Y25))
    return adapter_for("WMT", fetcher).fetch_instant_series(request, effective_as_of=NOW), fetcher


def test_pages_are_read_newest_first_until_one_is_enough_and_only_the_issuers_own_are_read() -> None:
    result, fetcher = _paged(3, hit=2)
    assert _values(result) == {_Y24: 200.0, _Y25: 300.0}
    assert _pages_read(fetcher) == [f"CIK0000000001-submissions-{number:03d}.json" for number in (1, 2, 3)]


def test_the_number_of_pages_read_is_bounded() -> None:
    result, fetcher = _paged(_MAX_SUBMISSION_PAGES + 5, hit=None)
    assert len(_pages_read(fetcher)) == _MAX_SUBMISSION_PAGES
    assert _values(result) == {_Y25: 300.0}
