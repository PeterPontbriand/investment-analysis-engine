"""Unit tests for the YFinanceClient market-data and quote boundaries.

All yfinance access is mocked so no network calls are ever made.
"""

import logging
from unittest.mock import patch

import pandas as pd
import pytest

from src.data.base_client import DataFetchError
from src.data.yfinance_client import YFinanceClient


class TestFetchData:
    """Historical market-data validation and error mapping."""

    def test_empty_result_raises_friendly_error_without_error_level_internal_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("src.data.yfinance_client.yf.download", return_value=pd.DataFrame()),
            caplog.at_level(logging.DEBUG, logger="src.data.yfinance_client"),
            pytest.raises(DataFetchError, match="No market data was returned for ticker 'BAD'"),
        ):
            YFinanceClient().fetch_data("BAD", "2026-01-01")

        assert not any(record.levelno >= logging.ERROR for record in caplog.records)


class TestFetchCurrentPrice:
    """Quote boundary validation and error mapping."""

    def test_valid_quote_returned(self) -> None:
        with patch("src.data.yfinance_client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {"last_price": 151.25}
            assert YFinanceClient().fetch_current_price("TEST") == pytest.approx(151.25)

    @pytest.mark.parametrize(
        "bad_price",
        [0.0, -1.0, float("nan"), float("inf"), float("-inf")],
        ids=["zero", "negative", "nan", "inf", "-inf"],
    )
    def test_non_finite_or_non_positive_quote_rejected(self, bad_price: float) -> None:
        with patch("src.data.yfinance_client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {"last_price": bad_price}
            with pytest.raises(DataFetchError, match="finite and positive"):
                YFinanceClient().fetch_current_price("TEST")

    def test_missing_quote_field_wrapped_as_data_fetch_error(self) -> None:
        with patch("src.data.yfinance_client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {}
            with pytest.raises(DataFetchError, match="Unable to resolve"):
                YFinanceClient().fetch_current_price("TEST")

    def test_provider_lookup_failure_wrapped_without_error_level_internal_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch(
                "src.data.yfinance_client.yf.Ticker",
                side_effect=ConnectionError("simulated network failure"),
            ),
            caplog.at_level(logging.DEBUG, logger="src.data.yfinance_client"),
            pytest.raises(DataFetchError, match="Unable to resolve"),
        ):
            YFinanceClient().fetch_current_price("TEST")

        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
