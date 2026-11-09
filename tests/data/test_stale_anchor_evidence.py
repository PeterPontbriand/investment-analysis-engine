"""A captured real filer that stopped filing: its anchor annual filing goes stale and stays stale.

The fixture is the SEC submissions and Company Facts of WeWork Inc. (CIK 1813756), served as the SEC served them.
WeWork filed its 10-K for the fiscal year ended 2022-12-31 on 2023-03-29, filed a notice of late filing (NT 10-K) for
the fiscal year ended 2023-12-31 on 2024-03-19, never filed that report, and deregistered with a Form 15 on
2024-06-11. The stale-anchor evidence record under ``docs/project`` says why it qualifies.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.anchor_filing import assess_anchor_filing
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEnd,
    AnchorYearEndRequest,
    SecEdgarFinancialFactsAdapter,
)

_FOLDER = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "stale_anchor"
_CIK = "0001813756"
_ANCHOR = "0001813756-23-000016"
_NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def _load(name: str) -> Any:
    return json.loads((_FOLDER / name).read_text(encoding="utf-8"))


class _Fetcher:
    """Serve WeWork's captured documents without network access."""

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        del not_found, provider_id
        assert headers["User-Agent"]
        if "/companyfacts/" in url:
            return _load("wework_companyfacts.json")
        if "/submissions/" in url:
            return _load("wework_submissions.json")
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _anchor_at(boundary: datetime) -> AnchorYearEnd:
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=_Fetcher(), clock=lambda: _NOW, user_agent="Synthetic test", ticker_overrides={"WE": _CIK}
    )
    with adapter.analysis_scope(subject_id="WE", provider_id=SEC_PROVIDER_ID, as_of=boundary):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WE", SEC_PROVIDER_ID))
    assert resolution.anchor is not None, resolution.message
    return resolution.anchor


def _filings() -> list[tuple[str, str, str, str]]:
    recent = _load("wework_submissions.json")["filings"]["recent"]
    return list(zip(recent["form"], recent["filingDate"], recent["reportDate"], recent["accessionNumber"], strict=True))


def test_the_fixture_is_the_captured_documents() -> None:
    expected = dict(
        line.split("  ")[::-1] for line in (_FOLDER / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    assert set(expected) == {"wework_companyfacts.json", "wework_submissions.json"}
    for name, digest in expected.items():
        assert hashlib.sha256((_FOLDER / name).read_bytes()).hexdigest() == digest


def test_the_registrant_filed_a_notice_of_late_filing_and_never_the_report_it_covered() -> None:
    filings = _filings()
    assert ("NT 10-K", "2024-03-19", "2023-12-31", "0001193125-24-070358") in filings
    annual = [(form, report) for form, _filed, report, _accession in filings if form in {"10-K", "10-K/A"}]
    assert ("10-K", "2023-12-31") not in annual
    newest_original = max(report for form, report in annual if form == "10-K")
    assert newest_original == "2022-12-31"
    assert max(filed for form, filed, _report, _accession in filings if form == "10-K") == "2023-03-29"


@pytest.mark.parametrize(
    ("boundary", "stale"),
    [
        (datetime(2023, 3, 29, 23, tzinfo=UTC), False),
        (datetime(2024, 4, 21, 12, tzinfo=UTC), False),
        (datetime(2024, 4, 22, 12, tzinfo=UTC), True),
        (datetime(2024, 6, 1, tzinfo=UTC), True),
        (datetime(2026, 11, 9, tzinfo=UTC), True),
    ],
)
def test_the_anchor_is_the_last_annual_report_and_goes_stale_the_day_after_the_next_was_due(
    boundary: datetime, stale: bool
) -> None:
    anchor = _anchor_at(boundary)
    assert (anchor.accession, anchor.form, anchor.year_end) == (_ANCHOR, "10-K", date(2022, 12, 31))
    assert anchor.filing_date == date(2023, 3, 29)
    evidence = assess_anchor_filing(anchor, boundary)
    assert evidence.next_report_due == date(2024, 4, 21)
    assert evidence.stale is stale


def test_the_anchor_before_the_last_annual_report_was_filed_is_the_one_before_it() -> None:
    anchor = _anchor_at(datetime(2023, 3, 1, tzinfo=UTC))
    assert (anchor.form, anchor.year_end) == ("10-K", date(2021, 12, 31))
    assert assess_anchor_filing(anchor, datetime(2023, 3, 1, tzinfo=UTC)).stale is False
