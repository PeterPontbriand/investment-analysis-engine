"""Deterministic tests for the Yahoo valuation quote adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.data.base_client import DataFetchError
from src.data.valuation.facts import ValuationFactRequest, ValuationField, ValuationProviderError
from src.data.valuation.provenance import ValuationSubjectKind
from src.data.yfinance import (
    YFINANCE_CURRENT_PRICE_FIELD,
    YFINANCE_PROVIDER_ID,
    YFinanceClient,
    YFinanceQuote,
    YFinanceValuationAdapter,
)

NOW = datetime(2026, 8, 23, 22, 30, tzinfo=UTC)


def _quote_request(*, as_of: datetime | None = None) -> ValuationFactRequest:
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="ko",
        field_name=ValuationField.CURRENT_PRICE,
        provider_id=YFINANCE_PROVIDER_ID,
        as_of=as_of,
    )


def test_current_quote_becomes_currency_safe_provider_fact() -> None:
    client = MagicMock(spec=YFinanceClient)
    client.fetch_current_quote.return_value = YFinanceQuote(price=70.25, currency="USD")
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: NOW)

    facts = adapter.fetch_facts(_quote_request())

    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(70.25)
    assert fact.currency == "USD"
    assert fact.provider_id == YFINANCE_PROVIDER_ID
    assert fact.provider_field == YFINANCE_CURRENT_PRICE_FIELD
    assert fact.observed_at == NOW
    assert fact.available_at == NOW
    client.fetch_current_quote.assert_called_once_with("KO")


def test_historical_quote_request_is_unavailable_without_live_lookup() -> None:
    client = MagicMock(spec=YFinanceClient)
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: NOW)

    result = adapter.fetch_facts(_quote_request(as_of=datetime(2025, 12, 31, tzinfo=UTC)))

    assert result == ()
    client.fetch_current_quote.assert_not_called()


def test_missing_quote_currency_degrades_to_unavailable() -> None:
    client = MagicMock(spec=YFinanceClient)
    client.fetch_current_quote.return_value = YFinanceQuote(price=70.25, currency=None)
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: NOW)

    assert adapter.fetch_facts(_quote_request()) == ()


def test_quote_client_failure_maps_to_provider_error() -> None:
    client = MagicMock(spec=YFinanceClient)
    client.fetch_current_quote.side_effect = DataFetchError("simulated transport failure")
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: NOW)

    with pytest.raises(ValuationProviderError, match="Yahoo Finance quote retrieval failed for KO"):
        adapter.fetch_facts(_quote_request())


def test_unsupported_field_is_unavailable_without_quote_lookup() -> None:
    client = MagicMock(spec=YFinanceClient)
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: NOW)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="KO",
        field_name=ValuationField.EPS,
        provider_id=YFINANCE_PROVIDER_ID,
        basis="ttm",
    )

    assert adapter.fetch_facts(request) == ()
    client.fetch_current_quote.assert_not_called()


def test_naive_adapter_clock_is_provider_error() -> None:
    client = MagicMock(spec=YFinanceClient)
    adapter = YFinanceValuationAdapter(client=client, clock=lambda: datetime(2026, 8, 23, 22, 30))

    with pytest.raises(ValuationProviderError, match="clock returned a naive datetime"):
        adapter.fetch_facts(_quote_request())

    client.fetch_current_quote.assert_not_called()
