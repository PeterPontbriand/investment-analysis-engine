"""Focused tests for SEC EDGAR declared User-Agent configuration."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter


class HeaderCaptureFetcher:
    """Minimal SEC transport fake that records request headers."""

    def __init__(self) -> None:
        """Initialize an empty call log."""
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
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


def test_sec_user_agent_explicit_constructor_value_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the explicit declared identity even when the environment differs."""
    monkeypatch.setenv("SEC_USER_AGENT", "environment-agent env@example.invalid")
    fetcher = HeaderCaptureFetcher()
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher,
        user_agent="explicit-agent explicit@example.invalid",
    )

    assert adapter.fetch_facts(_annual_eps_request()) == ()
    assert fetcher.calls
    assert all(headers["User-Agent"] == "explicit-agent explicit@example.invalid" for _url, headers in fetcher.calls)


def test_sec_user_agent_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use SEC_USER_AGENT when the constructor does not supply an identity."""
    monkeypatch.setenv("SEC_USER_AGENT", "environment-agent env@example.invalid")
    fetcher = HeaderCaptureFetcher()
    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetcher)

    assert adapter.fetch_facts(_annual_eps_request()) == ()
    assert fetcher.calls
    assert all(headers["User-Agent"] == "environment-agent env@example.invalid" for _url, headers in fetcher.calls)


def test_sec_user_agent_missing_identity_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject construction before network access when no declared identity exists."""
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)

    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        SecEdgarFinancialFactsAdapter(json_fetcher=HeaderCaptureFetcher())


def test_sec_user_agent_blank_explicit_identity_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat an explicitly blank identity as invalid instead of masking it with env."""
    monkeypatch.setenv("SEC_USER_AGENT", "environment-agent env@example.invalid")

    with pytest.raises(ValueError, match="declared User-Agent"):
        SecEdgarFinancialFactsAdapter(
            json_fetcher=HeaderCaptureFetcher(),
            user_agent="   ",
        )
