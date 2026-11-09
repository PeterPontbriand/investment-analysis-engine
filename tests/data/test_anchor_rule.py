"""The anchor annual filing rule: the first original fixes the fiscal year, and an older year's amendment never wins."""

from datetime import UTC, date, datetime

import pytest

from investment_analysis_engine.analysis.shared.anchor_filing import assess_anchor_filing
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEnd,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    AnchorYearEndUnavailableReason,
    SecEdgarFinancialFactsAdapter,
)
from tests._sec_instants import NOW, FixtureFetcher, load

_BOUNDARY = datetime(2025, 6, 30, tzinfo=UTC)

_Row = tuple[str, str, str, str, str]


def _row(number: int, form: str, accepted: str, report: str) -> _Row:
    """Return a submissions row accepted on ``accepted`` (a date) for the fiscal year ended ``report``."""
    return (f"0000019617-25-{number:06d}", form, accepted, report, f"{accepted}T12:00:00.000Z")


def _adapter(*rows: _Row) -> SecEdgarFinancialFactsAdapter:
    """Return an adapter whose recent block holds exactly these rows."""
    accessions, forms, filed, reported, accepted = (list(column) for column in zip(*rows, strict=True))
    submissions = {
        "tickers": ["JPM"],
        "filings": {
            "recent": {
                "accessionNumber": accessions,
                "form": forms,
                "filingDate": filed,
                "reportDate": reported,
                "acceptanceDateTime": accepted,
                "primaryDocument": [f"{accession}.htm" for accession in accessions],
            },
            "files": [],
        },
    }
    fetcher = FixtureFetcher("JPM", companyfacts=load("JPM")["companyfacts"], submissions=submissions)
    return SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")


def _resolution(*rows: _Row, boundary: datetime = _BOUNDARY) -> AnchorYearEndResolution:
    """Return what the adapter resolves as the anchor for a recent block holding exactly these rows."""
    adapter = _adapter(*rows)
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=boundary):
        return adapter.resolve_anchor_year_end(AnchorYearEndRequest("JPM", SEC_PROVIDER_ID))


def _anchor(*rows: _Row, boundary: datetime = _BOUNDARY) -> AnchorYearEnd:
    """Return the anchor the adapter finds in a recent block holding exactly these rows."""
    resolution = _resolution(*rows, boundary=boundary)
    assert resolution.anchor is not None, resolution.message
    return resolution.anchor


def test_an_older_years_amendment_accepted_after_the_newer_years_report_is_not_the_anchor() -> None:
    anchor = _anchor(
        _row(1, "10-K", "2024-02-15", "2023-12-31"),
        _row(2, "10-K", "2025-02-14", "2024-12-31"),
        _row(3, "10-K/A", "2025-03-10", "2023-12-31"),
    )
    assert (anchor.accession, anchor.form, anchor.year_end) == ("0000019617-25-000002", "10-K", date(2024, 12, 31))
    assert assess_anchor_filing(anchor, _BOUNDARY).stale is False


def test_an_amendment_of_the_anchors_own_year_is_the_anchor() -> None:
    anchor = _anchor(
        _row(1, "10-K", "2024-02-15", "2023-12-31"),
        _row(2, "10-K", "2025-02-14", "2024-12-31"),
        _row(3, "10-K/A", "2025-03-10", "2024-12-31"),
    )
    assert (anchor.accession, anchor.form, anchor.year_end) == ("0000019617-25-000003", "10-K/A", date(2024, 12, 31))


def test_the_newest_amendment_of_the_anchors_year_wins_over_an_earlier_one() -> None:
    anchor = _anchor(
        _row(1, "10-K", "2025-02-14", "2024-12-31"),
        _row(2, "10-K/A", "2025-03-10", "2024-12-31"),
        _row(3, "10-K/A", "2025-04-10", "2024-12-31"),
    )
    assert anchor.accession == "0000019617-25-000003"


def test_a_twenty_f_amendment_of_an_older_year_is_not_the_anchor() -> None:
    anchor = _anchor(
        _row(1, "20-F", "2024-04-20", "2023-12-31"),
        _row(2, "20-F", "2025-04-18", "2024-12-31"),
        _row(3, "20-F/A", "2025-05-01", "2023-12-31"),
    )
    assert (anchor.accession, anchor.form, anchor.year_end) == ("0000019617-25-000002", "20-F", date(2024, 12, 31))


def test_a_twenty_f_amendment_of_the_anchors_year_is_the_anchor() -> None:
    anchor = _anchor(
        _row(1, "20-F", "2025-04-18", "2024-12-31"),
        _row(2, "20-F/A", "2025-05-10", "2024-12-31"),
    )
    assert (anchor.accession, anchor.form) == ("0000019617-25-000002", "20-F/A")


def test_a_boundary_between_the_original_and_its_amendment_anchors_to_the_original() -> None:
    anchor = _anchor(
        _row(1, "10-K", "2025-02-14", "2024-12-31"),
        _row(2, "10-K/A", "2025-03-10", "2024-12-31"),
        boundary=datetime(2025, 3, 1, tzinfo=UTC),
    )
    assert anchor.accession == "0000019617-25-000001"


def test_an_original_with_no_report_date_is_its_own_anchor_with_no_year_end() -> None:
    resolution = _resolution(_row(1, "10-K", "2025-02-14", ""))
    assert resolution.reason is AnchorYearEndUnavailableReason.REPORT_DATE_UNAVAILABLE


def test_amendments_alone_give_no_anchor() -> None:
    snapshot = _adapter(_row(1, "10-K/A", "2025-03-10", "2024-12-31")).create_analysis_snapshot(
        subject_id="JPM", as_of=_BOUNDARY
    )
    assert snapshot.latest_annual_accession is None
    assert snapshot.eligible_annual_accessions == ("0000019617-25-000001",)


@pytest.mark.parametrize("boundary_day", [date(2025, 3, 11), date(2025, 6, 30)])
def test_the_anchor_does_not_depend_on_how_late_the_boundary_is(boundary_day: date) -> None:
    anchor = _anchor(
        _row(1, "10-K", "2025-02-14", "2024-12-31"),
        _row(2, "10-K/A", "2024-03-10", "2023-12-31"),
        boundary=datetime(boundary_day.year, boundary_day.month, boundary_day.day, tzinfo=UTC),
    )
    assert anchor.year_end == date(2024, 12, 31)


def test_an_anchor_stale_at_an_old_boundary_is_not_stale_at_a_later_one_that_sees_the_late_report() -> None:
    rows = (
        _row(1, "10-K", "2023-03-29", "2022-12-31"),
        _row(2, "10-K", "2024-05-15", "2023-12-31"),
    )
    old = datetime(2024, 5, 1, tzinfo=UTC)
    later = datetime(2024, 6, 1, tzinfo=UTC)

    at_the_old_boundary = _anchor(*rows, boundary=old)
    assert at_the_old_boundary.year_end == date(2022, 12, 31)
    assessed = assess_anchor_filing(at_the_old_boundary, old)
    assert (assessed.next_report_due, assessed.stale) == (date(2024, 4, 21), True)

    after_the_late_report = _anchor(*rows, boundary=later)
    assert after_the_late_report.year_end == date(2023, 12, 31)
    assert assess_anchor_filing(after_the_late_report, later).stale is False
