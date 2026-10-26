"""The extra submissions pages of a frequent filer give its older annual facts their acceptance times."""

from datetime import UTC, datetime
from typing import Any

from investment_analysis_engine.data.financial.facts import FinancialFactRequest, FinancialField
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from tests._sec_instants import NOW, FixtureFetcher, adapter_for
from tests.data.test_instant_series import _ACCEPTED, _MID, _NEW, _OLD, _document, _fetcher

_PAGE = "CIK0000000001-submissions-{number:03d}.json"


def _duration(year: int, value: float, accession: str) -> dict[str, Any]:
    return {
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "val": value,
        "accn": accession,
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": _ACCEPTED[accession][:10],
    }


def _issuer(*, in_recent: tuple[str, ...]) -> FixtureFetcher:
    concepts = {
        "NetCashProvidedByUsedInOperatingActivities": [
            ("USD", [_duration(2025, 30.0, _NEW), _duration(2024, 20.0, _MID), _duration(2023, 10.0, _OLD)])
        ]
    }
    facts, submissions = _document(concepts, accessions={name: _ACCEPTED[name] for name in in_recent})
    submissions["filings"]["files"] = [
        {"name": _PAGE.format(number=1), "filingFrom": "2025-02-01", "filingTo": "2025-02-28"},
        {"name": _PAGE.format(number=2), "filingFrom": "2024-02-01", "filingTo": "2024-02-28"},
    ]
    fetcher = _fetcher(facts, submissions)
    fetcher.pages = {
        _PAGE.format(number=1): _page(_MID),
        _PAGE.format(number=2): _page(_OLD),
    }
    return fetcher


def _page(accession: str) -> dict[str, list[str]]:
    return {
        "accessionNumber": [accession],
        "form": ["10-K"],
        "filingDate": [_ACCEPTED[accession][:10]],
        "acceptanceDateTime": [_ACCEPTED[accession]],
        "primaryDocument": ["a.htm"],
    }


def _request(count: int = 3, as_of: datetime | None = None) -> FinancialFactRequest:
    return FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        "SYN",
        FinancialField.OPERATING_CASH_FLOW,
        SEC_PROVIDER_ID,
        basis="fiscal_year",
        as_of=as_of,
        observation_count=count,
    )


def _pages(fetcher: FixtureFetcher) -> list[str]:
    return [call.rsplit("/", 1)[1] for call in fetcher.calls if "-submissions-" in call]


def test_older_annual_facts_take_their_acceptance_time_from_the_extra_pages() -> None:
    fetcher = _issuer(in_recent=(_NEW,))
    facts = adapter_for("WMT", fetcher).fetch_facts(_request(), effective_as_of=NOW)

    assert [fact.value for fact in facts] == [10.0, 20.0, 30.0]
    accepted = [datetime.fromisoformat(_ACCEPTED[name]) for name in (_OLD, _MID, _NEW)]
    assert [fact.available_at for fact in facts] == accepted
    assert all("acceptanceDateTime" in fact.notes[-1] for fact in facts)
    assert sorted(_pages(fetcher)) == [_PAGE.format(number=1), _PAGE.format(number=2)]


def test_without_the_pages_the_older_facts_fall_back_to_the_end_of_the_filing_date() -> None:
    fetcher = _issuer(in_recent=(_NEW,))
    fetcher.documents["/submissions/"]["filings"]["files"] = []  # type: ignore[index]
    facts = adapter_for("WMT", fetcher).fetch_facts(_request(), effective_as_of=NOW)

    assert [fact.value for fact in facts] == [10.0, 20.0, 30.0]
    assert facts[0].available_at != accepted_of(_OLD)
    assert "acceptanceDateTime unavailable" in facts[0].notes[-1]
    assert _pages(fetcher) == []


def accepted_of(accession: str) -> datetime:
    return datetime.fromisoformat(_ACCEPTED[accession]).astimezone(UTC)


def test_no_page_is_read_when_every_annual_filing_is_in_the_recent_block() -> None:
    fetcher = _issuer(in_recent=(_NEW, _MID, _OLD))
    adapter_for("WMT", fetcher).fetch_facts(_request(), effective_as_of=NOW)
    assert _pages(fetcher) == []


def test_only_the_filings_the_series_needs_are_read_and_each_page_once() -> None:
    fetcher = _issuer(in_recent=(_NEW,))
    adapter = adapter_for("WMT", fetcher)
    adapter.fetch_facts(_request(count=1), effective_as_of=NOW)
    assert _pages(fetcher) == []
    adapter.fetch_facts(_request(count=2), effective_as_of=NOW)
    assert _pages(fetcher) == [_PAGE.format(number=1)]
    adapter.fetch_facts(_request(count=3), effective_as_of=NOW)
    assert _pages(fetcher) == [_PAGE.format(number=1), _PAGE.format(number=2)]


def test_a_filing_after_the_boundary_is_not_looked_up() -> None:
    fetcher = _issuer(in_recent=(_NEW,))
    boundary = datetime(2024, 6, 1, tzinfo=UTC)
    adapter_for("WMT", fetcher).fetch_facts(_request(as_of=boundary), effective_as_of=boundary)
    assert _pages(fetcher) == [_PAGE.format(number=2)]
