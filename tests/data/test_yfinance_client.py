"""Unit tests for the YFinanceClient market-data and quote boundaries.

All yfinance access is mocked so no network calls are ever made.
"""

import logging
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.data.base_client import DataFetchError
from src.data.yfinance import YFinanceClient


class TestFetchData:
    """Historical market-data validation and error mapping."""

    def test_empty_result_raises_friendly_error_without_error_level_internal_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("src.data.yfinance.client.yf.download", return_value=pd.DataFrame()),
            caplog.at_level(logging.DEBUG, logger="src.data.yfinance.client"),
            pytest.raises(DataFetchError, match="No market data was returned for ticker 'BAD'"),
        ):
            YFinanceClient().fetch_data("BAD", "2026-01-01")

        assert not any(record.levelno >= logging.ERROR for record in caplog.records)

    def test_context_retains_daily_interval_date_currency_and_observation_count(self) -> None:
        frame = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0]},
            index=pd.to_datetime(["2026-08-19", "2026-08-20", "2026-08-21"]),
        )
        with (
            patch("src.data.yfinance.client.yf.download", return_value=frame) as mock_download,
            patch("src.data.yfinance.client.yf.Ticker") as mock_ticker,
        ):
            mock_ticker.return_value.fast_info = {"currency": "usd"}
            result = YFinanceClient().fetch_data_with_context("TEST", "2026-01-01")

        assert result.frame is frame
        assert result.context.provider_id == "yfinance"
        assert result.context.observation_interval == "1d"
        assert result.context.data_as_of == date(2026, 8, 21)
        assert result.context.currency == "USD"
        assert result.context.observation_count == 3
        assert result.context.price_adjustment == "adjusted"
        assert mock_download.call_args.kwargs["interval"] == "1d"
        assert mock_download.call_args.kwargs["auto_adjust"] is True

    def test_context_degrades_only_optional_currency_metadata(self) -> None:
        frame = pd.DataFrame({"Close": [100.0]}, index=pd.to_datetime(["2026-08-21"]))
        with (
            patch("src.data.yfinance.client.yf.download", return_value=frame),
            patch("src.data.yfinance.client.yf.Ticker", side_effect=RuntimeError("metadata unavailable")),
        ):
            result = YFinanceClient().fetch_data_with_context("TEST", "2026-01-01")

        assert result.context.currency is None
        assert result.context.data_as_of == date(2026, 8, 21)
        assert result.context.observation_count == 1


class TestFetchCurrentPrice:
    """Quote boundary validation and error mapping."""

    def test_valid_quote_returned(self) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {"last_price": 151.25}
            assert YFinanceClient().fetch_current_price("TEST") == pytest.approx(151.25)

    @pytest.mark.parametrize(
        "bad_price",
        [0.0, -1.0, float("nan"), float("inf"), float("-inf")],
        ids=["zero", "negative", "nan", "inf", "-inf"],
    )
    def test_non_finite_or_non_positive_quote_rejected(self, bad_price: float) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {"last_price": bad_price}
            with pytest.raises(DataFetchError, match="finite and positive"):
                YFinanceClient().fetch_current_price("TEST")

    def test_missing_quote_field_wrapped_as_data_fetch_error(self) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {}
            with pytest.raises(DataFetchError, match="Unable to resolve"):
                YFinanceClient().fetch_current_price("TEST")

    def test_provider_lookup_failure_wrapped_without_error_level_internal_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch(
                "src.data.yfinance.client.yf.Ticker",
                side_effect=ConnectionError("simulated network failure"),
            ),
            caplog.at_level(logging.DEBUG, logger="src.data.yfinance.client"),
            pytest.raises(DataFetchError, match="Unable to resolve"),
        ):
            YFinanceClient().fetch_current_price("TEST")

        assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_current_quote_retains_normalized_currency() -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.fast_info = {"last_price": 151.25, "currency": "usd"}
        quote = YFinanceClient().fetch_current_quote("TEST")
    assert quote.price == pytest.approx(151.25)
    assert quote.currency == "USD"
