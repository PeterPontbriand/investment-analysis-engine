"""Deterministic provider evidence tests for security identity metadata."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from unittest.mock import patch

from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.instrument_profile import InstrumentKind, InstrumentKindRequest
from src.data.sec_edgar import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from src.data.security_identity import SecurityIdentityRequest
from src.data.yfinance import YFINANCE_PROVIDER_ID, YFinanceClient, YFinanceFinancialFactsAdapter
from tests.analysis.graham_value.conftest import SEC_TEST_USER_AGENT

NOW = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


def test_sec_retains_ticker_title_and_cik_without_duplicate_mapping_fetch() -> None:
    calls = 0

    def fetcher(url: str, *, headers: Mapping[str, str]) -> object:
        nonlocal calls
        calls += 1
        assert url.endswith("company_tickers.json")
        assert headers["User-Agent"] == SEC_TEST_USER_AGENT
        return {
            "0": {
                "ticker": "KO",
                "title": "  The   Coca-Cola Company ",
                "cik_str": 21344,
            }
        }

    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher,
        clock=lambda: NOW,
        user_agent=SEC_TEST_USER_AGENT,
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=adapter)
    request = SecurityIdentityRequest("ko", SEC_PROVIDER_ID)

    first = provider.resolve_security_identity(request)
    second = provider.resolve_security_identity(request)

    assert calls == 1
    assert first is second
    assert first is not None
    assert first.ticker == "KO"
    assert first.instrument_name == "The Coca-Cola Company"
    assert first.issuer_identifier == "0000021344"
    assert first.listing_venue is None
    assert first.resolved_at == NOW


def test_yahoo_retains_non_company_name_venue_and_instrument_identifier() -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {
            "longName": " Bitcoin   USD ",
            "fullExchangeName": "CCC",
            "uuid": "crypto:btc-usd",
        }
        identity = YFinanceClient(clock=lambda: NOW).resolve_security_identity(
            SecurityIdentityRequest("btc-usd", YFINANCE_PROVIDER_ID)
        )

    assert mock_ticker.call_count == 1
    assert identity is not None
    assert identity.instrument_name == "Bitcoin USD"
    assert identity.listing_venue == "CCC"
    assert identity.instrument_identifier == "crypto:btc-usd"
    assert identity.issuer_identifier is None
    assert identity.resolved_at == NOW


def test_production_facade_routes_yahoo_identity_and_kind_through_one_client_snapshot() -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {
            "longName": "Franklin FTSE Switzerland ETF",
            "quoteType": "ETF",
        }
        adapter = YFinanceFinancialFactsAdapter(client=YFinanceClient(clock=lambda: NOW))
        provider = ProductionFinancialFactsProvider(
            sec_edgar=SecEdgarFinancialFactsAdapter(user_agent=SEC_TEST_USER_AGENT),
            yfinance=adapter,
        )

        identity = provider.resolve_security_identity(SecurityIdentityRequest("FLSW", YFINANCE_PROVIDER_ID))
        kind = provider.resolve_instrument_kind(InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID))

    assert mock_ticker.call_count == 1
    assert identity is not None
    assert identity.instrument_name == "Franklin FTSE Switzerland ETF"
    assert kind is not None
    assert kind.kind is InstrumentKind.ETF
