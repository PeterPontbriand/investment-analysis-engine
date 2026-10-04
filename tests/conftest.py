"""Global pytest configurations and safety cleanups."""

import logging
import traceback
from collections.abc import Generator
from typing import NoReturn

import pytest

from src.data.yfinance import client as yfinance_client_module


class YahooNetworkAccessError(AssertionError):
    """Raised when a test reaches the live Yahoo network layer without an explicit stub."""


class _BlockedYFinance:
    """Stand-in for the ``yfinance`` module whose network entry points fail loudly.

    yfinance performs its requests through ``curl_cffi``, which bypasses Python's ``socket`` module, so blocking
    sockets would not catch it. ``src/data/yfinance/client.py`` is the only importer of yfinance, and it reaches the
    network only through ``yf.download`` and ``yf.Ticker`` (``fast_info`` / ``info``); guarding those two names on
    the client module covers every ``YFinanceClient`` network method. Each blocked call is also recorded so the
    test still fails if production code catches the raised error.
    """

    def __init__(self) -> None:
        self.blocked_calls: list[str] = []

    def _block(self, name: str) -> NoReturn:
        caller = traceback.extract_stack(limit=4)[0]
        self.blocked_calls.append(f"{name} (from {caller.filename}:{caller.lineno} {caller.name})")
        msg = (
            f"yfinance.{name} was reached without a stub, which would make a live Yahoo call. "
            "Inject a fake client or patch 'src.data.yfinance.client.yf' for this test."
        )
        raise YahooNetworkAccessError(msg)

    def download(self, *_arguments: object, **_keywords: object) -> NoReturn:
        self._block("download")

    def Ticker(self, *_arguments: object, **_keywords: object) -> NoReturn:  # noqa: N802
        self._block("Ticker")


@pytest.fixture(autouse=True)
def block_live_yahoo(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Fail any test that reaches YFinanceClient's network methods unless it stubs them explicitly.

    A test that patches ``src.data.yfinance.client.yf`` or replaces the client's methods overrides this guard.
    """
    blocked = _BlockedYFinance()
    monkeypatch.setattr(yfinance_client_module, "yf", blocked)
    yield
    if blocked.blocked_calls:
        msg = f"Test reached live Yahoo network entry points without a stub: {blocked.blocked_calls}"
        raise YahooNetworkAccessError(msg)


@pytest.fixture(autouse=True)
def cleanup_logging_handlers() -> Generator[None, None, None]:
    """Automatically flush and detach logging handlers after every test to prevent process hangs."""
    yield
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
            root_logger.removeHandler(handler)
        except Exception:
            pass
