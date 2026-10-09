"""Focused tests for SEC EDGAR declared User-Agent configuration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter


class HeaderCaptureFetcher:
    """Minimal SEC transport fake that records request headers."""

    def __init__(self) -> None:
        """Initialize an empty call log."""
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> object:
        """Record one request and return the minimal payload needed for the URL."""
        self.calls.append((url, dict(headers)))
        if "company_tickers.json" in url:
            return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        if "/companyfacts/" in url:
            return {"facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {}}}}}
        if "/submissions/" in url:
            return {"filings": {"recent": {"accessionNumber": [], "acceptanceDateTime": []}}}
        msg = f"Unexpected URL: {url}"
        raise AssertionError(msg)


def _annual_eps_request() -> FinancialFactRequest:
    """Return a supported SEC request that reaches the fake transport."""
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=3,
    )


def test_sec_user_agent_is_sent_on_every_request() -> None:
    """Send the identity the caller declared."""
    fetcher = HeaderCaptureFetcher()
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher,
        user_agent="explicit-agent explicit@example.invalid",
    )

    assert adapter.fetch_facts(_annual_eps_request(), effective_as_of=datetime.now(UTC)) == ()
    assert fetcher.calls
    assert all(headers["User-Agent"] == "explicit-agent explicit@example.invalid" for _url, headers in fetcher.calls)


def test_sec_user_agent_is_required_and_never_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject construction without an identity, even when the environment declares one."""
    monkeypatch.setenv("SEC_USER_AGENT", "environment-agent env@example.invalid")

    with pytest.raises(TypeError, match="user_agent"):
        SecEdgarFinancialFactsAdapter(json_fetcher=HeaderCaptureFetcher())  # type: ignore[call-arg]


def test_sec_user_agent_blank_identity_is_invalid() -> None:
    """Treat a blank identity as invalid before any network access."""
    with pytest.raises(ValueError, match="declared User-Agent"):
        SecEdgarFinancialFactsAdapter(
            json_fetcher=HeaderCaptureFetcher(),
            user_agent="   ",
        )
