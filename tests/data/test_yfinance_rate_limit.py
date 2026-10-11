"""Yahoo throttling through the real library, with its HTTP layer stubbed to answer 429; no network.

The library raises its own rate-limit error from the quote and metadata reads, but ``yf.download`` swallows it and
returns an empty frame, so the history path cannot tell throttling from an empty answer and reports ``no_data``.
"""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
import yfinance

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.yfinance import YFinanceClient


class _TooManyRequests:
    """The HTTP answer Yahoo gives a throttled client."""

    status_code = 429
    text = "Too Many Requests"
    content = b"Too Many Requests"
    headers: dict[str, str] = {}  # noqa: RUF012
    cookies: dict[str, str] = {}  # noqa: RUF012
    url = "https://query2.finance.yahoo.com/"

    def json(self) -> dict[str, object]:
        return {}


@pytest.fixture
def throttled_yahoo() -> Iterator[None]:
    """Run the real library against a transport that always answers HTTP 429."""

    def answer(*_args: object, **_kwargs: object) -> _TooManyRequests:
        return _TooManyRequests()

    with (
        patch("src.data.yfinance.client.yf", yfinance),
        patch("yfinance.data.YfData._get_cookie_and_crumb", lambda *_args, **_kwargs: (None, "basic")),
        patch("curl_cffi.requests.Session.request", answer),
        patch("curl_cffi.requests.Session.get", answer),
    ):
        yield


@pytest.mark.usefixtures("throttled_yahoo")
def test_the_quote_read_reports_the_library_rate_limit_error_as_rate_limited() -> None:
    with pytest.raises(DataFetchError) as raised:
        YFinanceClient().fetch_current_quote("AAPL")
    assert (raised.value.kind, raised.value.provider_id) == (ProviderFailureKind.RATE_LIMITED, "yfinance")


@pytest.mark.usefixtures("throttled_yahoo")
def test_the_metadata_read_reports_the_library_rate_limit_error_as_rate_limited() -> None:
    with pytest.raises(DataFetchError) as raised:
        YFinanceClient()._fetch_metadata_snapshot("AAPL")
    assert raised.value.kind is ProviderFailureKind.RATE_LIMITED


@pytest.mark.usefixtures("throttled_yahoo")
def test_a_throttled_history_download_stays_no_data_because_the_library_swallows_the_error() -> None:
    with pytest.raises(DataFetchError) as raised:
        YFinanceClient().fetch_data("AAPL", "2026-01-01")
    assert (raised.value.kind, raised.value.provider_id) == (ProviderFailureKind.NO_DATA, "yfinance")
