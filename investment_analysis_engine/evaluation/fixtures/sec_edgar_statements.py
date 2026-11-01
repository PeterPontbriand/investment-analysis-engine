"""Deterministic SEC statement fixtures for the Golden Suite, composed from the captured SEC documents.

An issuer's balance-sheet facts and annual facts are captured as two trimmed Company Facts documents, and the as-filed
SIC code of its anchor filing as a filing header. This module serves them to the real SEC adapter as one issuer: the
two fact documents are merged and the filings of both are listed, so the adapter runs its own year-end discovery,
series resolution and header reading, with no network access. Nothing is computed here.
"""

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.sec_edgar.filing_document import FilingHeaderPolicy
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter

STATEMENTS_APPLE_FIXTURE_ID: Final = "sec_statements_aapl_fy2024"
STATEMENTS_MONSTER_FIXTURE_ID: Final = "sec_statements_mnst_fy2025"
STATEMENTS_FIXTURE_IDS: Final = frozenset({STATEMENTS_APPLE_FIXTURE_ID, STATEMENTS_MONSTER_FIXTURE_ID})

_ROOT: Final = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar"
_ISSUERS: Final = {
    STATEMENTS_APPLE_FIXTURE_ID: ("aapl", "aapl_fy2024.hdr.sgml"),
    STATEMENTS_MONSTER_FIXTURE_ID: ("mnst", "mnst_fy2025.hdr.sgml"),
}
"""Each fixture's issuer file stem and the filing header of its anchor filing."""

_USER_AGENT: Final = "Golden fixture tests@example.invalid"
_RECENT_FILINGS: Final = "recent"


def _load(folder: str, stem: str) -> dict[str, Any]:
    """Load one captured issuer document."""
    document: dict[str, Any] = json.loads((_ROOT / folder / f"{stem}.json").read_text(encoding="utf-8"))
    return document


def _merged_facts(balance: Mapping[str, Any], annual: Mapping[str, Any]) -> dict[str, Any]:
    """Return the Company Facts of both captured documents as one, the balance-sheet document's facts first."""
    merged: dict[str, Any] = {key: dict(value) for key, value in balance["facts"].items()}
    for taxonomy, concepts in annual["facts"].items():
        merged.setdefault(taxonomy, {})
        for concept, body in concepts.items():
            merged[taxonomy].setdefault(concept, body)
    return {"cik": balance["cik"], "entityName": balance["entityName"], "facts": merged}


def _merged_submissions(balance: Mapping[str, Any], annual: Mapping[str, Any]) -> dict[str, Any]:
    """Return the submissions of both captured documents as one: every filing of either, once."""
    columns = list(balance["filings"][_RECENT_FILINGS])
    filings: dict[str, dict[str, Any]] = {}
    for source in (balance, annual):
        block = source["filings"][_RECENT_FILINGS]
        for index, accession in enumerate(block["accessionNumber"]):
            filings.setdefault(accession, {column: block[column][index] for column in columns})
    ordered = sorted(filings.values(), key=lambda row: row["acceptanceDateTime"], reverse=True)
    return {
        **{key: value for key, value in balance.items() if key != "filings"},
        "filings": {_RECENT_FILINGS: {column: [row[column] for row in ordered] for column in columns}},
    }


class StatementsFetcher:
    """Serve one issuer's merged documents to the SEC adapter.

    A test may replace either document to model a different filing history; the others stay as captured. The captured
    files are read on first use of ``documents``, so a case that never reaches the SEC adapter reads none of them.
    """

    def __init__(self, stem: str, *, companyfacts: object | None = None, submissions: object | None = None) -> None:
        """Remember the issuer ``stem`` and any replacement document; nothing is read yet."""
        self._stem = stem
        self._companyfacts = companyfacts
        self._submissions = submissions
        self._documents: dict[str, object] | None = None

    @property
    def documents(self) -> dict[str, object]:
        """The merged documents by URL marker, built from the captured files on first access."""
        if self._documents is None:
            balance, annual = _load("instant_facts", self._stem), _load("annual_facts", self._stem)
            self._documents = {
                "company_tickers.json": {
                    "0": {
                        "cik_str": balance["cik"],
                        "ticker": self._stem.upper(),
                        "title": balance["companyfacts"]["entityName"],
                    }
                },
                "/companyfacts/": self._companyfacts or _merged_facts(balance["companyfacts"], annual["companyfacts"]),
                "/submissions/": self._submissions
                or _merged_submissions(balance["submissions"], annual["submissions"]),
            }
        return self._documents

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        """Return the document whose marker the URL carries."""
        del headers, not_found, provider_id  # captured documents never fail
        for marker, document in self.documents.items():
            if marker in url:
                return document
        raise AssertionError(f"Unexpected deterministic SEC URL: {url}")


class HeaderFetcher:
    """Serve the captured filing header of an issuer's anchor filing."""

    def __init__(self, header: Path | str) -> None:
        """Serve the header file at ``header``, or the header text itself when a string is given."""
        self._header = header

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        policy: FilingHeaderPolicy,
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        """Return the header text for any header URL."""
        del headers, policy, not_found, provider_id  # captured headers never fail
        if not url.endswith(".hdr.sgml"):
            raise AssertionError(f"Unexpected deterministic SEC header URL: {url}")
        return self._header if isinstance(self._header, str) else self._header.read_text(encoding="utf-8")


def statements_adapter(
    json_fetcher: StatementsFetcher, header_fetcher: HeaderFetcher, *, clock_at: datetime
) -> SecEdgarFinancialFactsAdapter:
    """Build the real SEC adapter over the given fetchers, which serve captured documents."""
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=json_fetcher, header_fetcher=header_fetcher, clock=lambda: clock_at, user_agent=_USER_AGENT
    )


def captured_header(name: str) -> Path:
    """Return the path of a captured filing header, such as ``aapl_fy2024.hdr.sgml``."""
    return _ROOT / "filing_headers" / name


def fixture_statements_adapter(fixture_id: str, *, clock_at: datetime) -> SecEdgarFinancialFactsAdapter:
    """Build the real SEC adapter over the captured documents the fixture identifier selects."""
    stem, header = _ISSUERS[fixture_id]
    return statements_adapter(StatementsFetcher(stem), HeaderFetcher(captured_header(header)), clock_at=clock_at)
