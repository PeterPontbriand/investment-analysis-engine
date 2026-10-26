"""The trimmed Company Facts of the Step 3.5 regression issuers, served as the SEC would serve them.

Each fixture under ``evaluation/fixtures/sec_edgar/instant_facts`` holds the facts of one issuer that the balance-sheet
tests read, from the annual filing named in its ``anchor_accession`` and the earlier annual filings it compares with.
"""

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import (
    FinancialField,
    InstantSeriesFacts,
    InstantSeriesRequest,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "instant_facts"
NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)

# The regression issuer set of Step 3.5 and each issuer's latest fiscal year-end.
REGRESSION_SET: dict[str, date] = {
    "JPM": date(2025, 12, 31),
    "PLD": date(2025, 12, 31),
    "DUK": date(2025, 12, 31),
    "DE": date(2025, 11, 2),
    "SAP": date(2025, 12, 31),
    "NTR": date(2025, 12, 31),
    "WMT": date(2026, 1, 31),
    "MRNA": date(2025, 12, 31),
    "MNST": date(2025, 12, 31),
    "GOOGL": date(2025, 12, 31),
    "HON": date(2025, 12, 31),
}


def load(ticker: str) -> dict[str, Any]:
    """Return one issuer's fixture."""
    document: dict[str, Any] = json.loads((FIXTURES / f"{ticker.lower()}.json").read_text(encoding="utf-8"))
    return document


class FixtureFetcher:
    """A JSON fetcher that answers the three SEC documents an analysis reads from fixtures."""

    def __init__(self, ticker: str, *, companyfacts: object | None = None, submissions: object | None = None) -> None:
        """Serve the fixture of ``ticker``, with either document replaced when given."""
        document = load(ticker)
        self.documents: dict[str, object] = {
            "company_tickers.json": {"0": {"cik_str": document["cik"], "ticker": ticker, "title": ticker}},
            "/companyfacts/": document["companyfacts"] if companyfacts is None else companyfacts,
            "/submissions/": document["submissions"] if submissions is None else submissions,
        }
        self.pages: dict[str, object] = dict(document.get("pages", {}))
        self.calls: list[str] = []

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        """Return the document whose marker the URL carries."""
        assert headers["User-Agent"]
        assert provider_id == SEC_PROVIDER_ID
        assert isinstance(not_found, ProviderFailureKind)
        self.calls.append(url)
        for name, page in self.pages.items():
            if url.endswith(f"/submissions/{name}"):
                return page
        for marker, document in self.documents.items():
            if marker in url:
                return document
        raise AssertionError(f"Unexpected SEC URL: {url}")


def adapter_for(ticker: str, fetcher: FixtureFetcher | None = None) -> SecEdgarFinancialFactsAdapter:
    """Return an adapter reading the fixture of ``ticker``."""
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher or FixtureFetcher(ticker), clock=lambda: NOW, user_agent="Synthetic test"
    )


def year_ends(latest: date, count: int = 3) -> tuple[date, ...]:
    """Return the latest fiscal year-end and the ``count - 1`` before it, a calendar year apart."""
    return tuple(date(latest.year - back, latest.month, latest.day) for back in range(count - 1, -1, -1))


def series(
    ticker: str, field: FinancialField, *, count: int = 3, adapter: SecEdgarFinancialFactsAdapter | None = None
) -> InstantSeriesFacts:
    """Return the field at the issuer's latest ``count`` year-ends through the SEC adapter."""
    latest = REGRESSION_SET[ticker]
    ends = year_ends(latest, count)
    if ticker == "DE":
        ends = (date(2023, 10, 29), date(2024, 10, 27), latest)[-count:]
    request = InstantSeriesRequest(ticker, field, SEC_PROVIDER_ID, ends)
    return (adapter or adapter_for(ticker)).fetch_instant_series(request, effective_as_of=NOW)
