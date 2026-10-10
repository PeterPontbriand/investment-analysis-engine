"""Unit tests for the YFinanceClient market-data and quote boundaries.

All yfinance access is mocked so no network calls are ever made.
"""

import logging
from datetime import date
from unittest.mock import PropertyMock, patch

import curl_cffi.requests.exceptions as curl_exceptions
import pandas as pd
import pytest
import requests.exceptions as requests_exceptions
from yfinance.exceptions import (
    YFDataException,
    YFException,
    YFInvalidPeriodError,
    YFNotImplementedError,
    YFPricesMissingError,
    YFRateLimitError,
    YFTickerMissingError,
    YFTzMissingError,
)

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.yfinance import YFinanceClient
from src.data.yfinance.client import YFINANCE_HISTORY_COLUMNS

_COLUMNS = list(YFINANCE_HISTORY_COLUMNS)


def _history(dates: list[str], close: list[float]) -> pd.DataFrame:
    """Return a daily frame carrying every column the adapter requires."""
    return pd.DataFrame(
        {column: close if column == "Close" else [1.0] * len(close) for column in _COLUMNS},
        index=pd.to_datetime(dates),
    )


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

    def test_daily_download_passes_ignore_tz_explicitly(self) -> None:
        """ESC-26: daily frames must not depend on the library's default for dropping the timezone."""
        frame = _history(["2026-08-19"], [100.0])
        with patch("src.data.yfinance.client.yf.download", return_value=frame) as mock_download:
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        assert mock_download.call_args.kwargs["ignore_tz"] is True

    def test_context_retains_daily_interval_date_currency_and_observation_count(self) -> None:
        frame = _history(["2026-08-19", "2026-08-20", "2026-08-21"], [100.0, 101.0, 102.0])
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
        frame = _history(["2026-08-21"], [100.0])
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


_UNREACHABLE_FAULTS = [
    ConnectionError("connection refused"),
    TimeoutError("timed out"),
    YFRateLimitError(),
    curl_exceptions.ConnectionError("curl connection failure"),
    requests_exceptions.SSLError("tls failure"),
]
_UNEXPECTED_FAULTS = [
    YFDataException("unreadable payload"),
    curl_exceptions.JSONDecodeError("not json", 0, "{"),
    requests_exceptions.ContentDecodingError("bad encoding"),
    RuntimeError("an exception no rule names"),
]
_NO_DATA_FAULTS = [
    YFTickerMissingError("TEST", "unknown ticker"),
    YFPricesMissingError("TEST", "no prices"),
    YFTzMissingError("TEST"),
]
_DEFECTS = [
    YFInvalidPeriodError("TEST", "9y", "1d, 5d"),
    YFNotImplementedError("history"),
    YFException("a bare library exception"),
    requests_exceptions.InvalidURL("bad url"),
    curl_exceptions.InvalidURL("bad url"),
]
_KIND_FAULTS = [
    *[(fault, ProviderFailureKind.UNREACHABLE) for fault in _UNREACHABLE_FAULTS],
    *[(fault, ProviderFailureKind.UNEXPECTED_RESPONSE) for fault in _UNEXPECTED_FAULTS],
    *[(fault, ProviderFailureKind.NO_DATA) for fault in _NO_DATA_FAULTS],
]
_FAULT_IDS = [f"{type(fault).__module__.split('.')[0]}.{type(fault).__name__}" for fault, _ in _KIND_FAULTS]
_DEFECT_IDS = [f"{type(defect).__module__.split('.')[0]}.{type(defect).__name__}" for defect in _DEFECTS]


def _assert_failure(failure: DataFetchError, kind: ProviderFailureKind) -> None:
    assert failure.kind is kind
    assert failure.provider_id == "yfinance"


class TestHistoryFailureKinds:
    """``fetch_data`` reports what it observed as one of the three kinds, with provider identity."""

    @pytest.mark.parametrize(("fault", "kind"), _KIND_FAULTS, ids=_FAULT_IDS)
    def test_exception_escaping_the_download_is_classified(self, fault: Exception, kind: ProviderFailureKind) -> None:
        with (
            patch("src.data.yfinance.client.yf.download", side_effect=fault),
            pytest.raises(DataFetchError) as raised,
        ):
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        _assert_failure(raised.value, kind)
        assert raised.value.__cause__ is fault

    @pytest.mark.parametrize("empty", [pd.DataFrame(), None], ids=["empty frame", "none"])
    def test_empty_result_is_no_data(self, empty: pd.DataFrame | None) -> None:
        with (
            patch("src.data.yfinance.client.yf.download", return_value=empty),
            pytest.raises(DataFetchError) as raised,
        ):
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        _assert_failure(raised.value, ProviderFailureKind.NO_DATA)

    def test_non_frame_result_is_an_unexpected_response(self) -> None:
        with (
            patch("src.data.yfinance.client.yf.download", return_value={"Close": [1.0]}),
            pytest.raises(DataFetchError, match="instead of a data frame") as raised,
        ):
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        _assert_failure(raised.value, ProviderFailureKind.UNEXPECTED_RESPONSE)

    @pytest.mark.parametrize("missing", _COLUMNS)
    def test_missing_ohlcv_column_is_an_unexpected_response_naming_it(self, missing: str) -> None:
        frame = _history(["2026-08-19"], [100.0]).drop(columns=[missing])
        with (
            patch("src.data.yfinance.client.yf.download", return_value=frame),
            pytest.raises(DataFetchError, match=f"missing columns: {missing}") as raised,
        ):
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        _assert_failure(raised.value, ProviderFailureKind.UNEXPECTED_RESPONSE)

    @pytest.mark.parametrize("defect", _DEFECTS, ids=_DEFECT_IDS)
    def test_a_non_provider_exception_propagates_unchanged(self, defect: Exception) -> None:
        with (
            patch("src.data.yfinance.client.yf.download", side_effect=defect),
            pytest.raises(type(defect)) as raised,
        ):
            YFinanceClient().fetch_data("TEST", "2026-01-01")

        assert raised.value is defect


class TestQuoteFailureKinds:
    """``fetch_current_quote`` classifies a failed read and a received value that cannot be used."""

    @pytest.mark.parametrize(("fault", "kind"), _KIND_FAULTS, ids=_FAULT_IDS)
    def test_exception_from_the_quote_read_is_classified(self, fault: Exception, kind: ProviderFailureKind) -> None:
        with (
            patch("src.data.yfinance.client.yf.Ticker", side_effect=fault),
            pytest.raises(DataFetchError) as raised,
        ):
            YFinanceClient().fetch_current_quote("TEST")

        _assert_failure(raised.value, kind)

    @pytest.mark.parametrize(
        "fast_info",
        [{}, {"last_price": None}, {"last_price": "n/a"}, {"last_price": float("nan")}, {"last_price": -1.0}],
        ids=["absent field", "none", "non-numeric", "nan", "non-positive"],
    )
    def test_unusable_quote_value_is_an_unexpected_response(self, fast_info: dict[str, object]) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = fast_info
            with pytest.raises(DataFetchError) as raised:
                YFinanceClient().fetch_current_quote("TEST")

        _assert_failure(raised.value, ProviderFailureKind.UNEXPECTED_RESPONSE)

    def test_a_non_provider_exception_propagates_unchanged(self) -> None:
        defect = YFNotImplementedError("fast_info")
        with (
            patch("src.data.yfinance.client.yf.Ticker", side_effect=defect),
            pytest.raises(YFNotImplementedError) as raised,
        ):
            YFinanceClient().fetch_current_quote("TEST")

        assert raised.value is defect

    def test_a_missing_currency_stays_best_effort_when_the_read_raises_key_error(self) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = {"last_price": 10.0}
            quote = YFinanceClient().fetch_current_quote("TEST")

        assert quote.price == pytest.approx(10.0)
        assert quote.currency is None


class _FailingCurrencyInfo:
    """``fast_info`` whose price reads but whose currency read raises the given exception."""

    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    def __getitem__(self, key: str) -> object:
        if key == "currency":
            raise self.failure
        return 10.0


class TestMetadataFailureKinds:
    """``_fetch_metadata_snapshot`` classifies the failure and remembers it, with its kind."""

    @pytest.mark.parametrize(("fault", "kind"), _KIND_FAULTS, ids=_FAULT_IDS)
    def test_exception_from_the_metadata_read_is_classified_and_memoized_with_its_kind(
        self, fault: Exception, kind: ProviderFailureKind
    ) -> None:
        client = YFinanceClient()
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            type(mock_ticker.return_value).info = PropertyMock(side_effect=fault)
            with pytest.raises(DataFetchError) as first:
                client._fetch_metadata_snapshot("TEST")
            with pytest.raises(DataFetchError) as second:
                client._fetch_metadata_snapshot("TEST")

        _assert_failure(first.value, kind)
        assert second.value is first.value
        assert mock_ticker.call_count == 1

    def test_a_non_provider_exception_propagates_and_is_not_memoized(self) -> None:
        defect = YFNotImplementedError("info")
        client = YFinanceClient()
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            type(mock_ticker.return_value).info = PropertyMock(side_effect=defect)
            with pytest.raises(YFNotImplementedError):
                client._fetch_metadata_snapshot("TEST")

        assert client._metadata_by_ticker == {}


class TestCurrencyStaysBestEffort:
    """The optional currency never invalidates price history, but a defect is not hidden."""

    @pytest.mark.parametrize("fault", [fault for fault, _ in _KIND_FAULTS], ids=_FAULT_IDS)
    def test_a_typed_provider_failure_returns_no_currency(self, fault: Exception) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = _FailingCurrencyInfo(fault)
            assert YFinanceClient()._fetch_currency("TEST") is None

    def test_key_error_from_a_connection_fault_returns_no_currency(self) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = _FailingCurrencyInfo(KeyError("currency"))
            assert YFinanceClient()._fetch_currency("TEST") is None

    @pytest.mark.parametrize("defect", _DEFECTS, ids=_DEFECT_IDS)
    def test_a_non_provider_exception_propagates(self, defect: Exception) -> None:
        with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = _FailingCurrencyInfo(defect)
            with pytest.raises(type(defect)):
                YFinanceClient()._fetch_currency("TEST")

    def test_price_history_stays_usable_when_the_currency_read_fails_with_a_typed_failure(self) -> None:
        frame = _history(["2026-08-21"], [100.0])
        with (
            patch("src.data.yfinance.client.yf.download", return_value=frame),
            patch("src.data.yfinance.client.yf.Ticker", side_effect=ConnectionError("down")),
        ):
            result = YFinanceClient().fetch_data_with_context("TEST", "2026-01-01")

        assert result.context.currency is None
        assert result.frame is frame


def test_an_exception_escaping_the_download_is_logged_with_its_kind_and_cause(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        patch("src.data.yfinance.client.yf.download", side_effect=ConnectionError("connection refused")),
        caplog.at_level(logging.ERROR, logger="src.data.yfinance.client"),
        pytest.raises(DataFetchError),
    ):
        YFinanceClient().fetch_data("TEST", "2026-01-01")

    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR] == [
        "yfinance download for 'TEST' failed (unreachable): "
        "yfinance history download failed for 'TEST': connection refused"
    ]
