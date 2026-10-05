"""Suite-wide guards that fail any test reaching a live network path without an explicit stub.

Two layers are needed because the project reaches the network two ways:

* yfinance performs its requests through ``curl_cffi``, which bypasses Python's ``socket`` module, so it is
  guarded at the only module that imports it (``src/data/yfinance/client.py``) by replacing its ``yf`` name.
* ``urllib`` and ``httpx`` go through Python sockets, so ``socket.socket.connect`` and ``connect_ex`` are guarded for
  every non-loopback address, and ``socket.getaddrinfo`` is guarded for every non-loopback host name so the call
  fails before a DNS lookup. Loopback (and ``AF_UNIX``) stays allowed: the Windows asyncio event loop connects a
  local socket pair. IP literals are not looked up, so ``getaddrinfo`` lets them through and ``connect`` judges them.

Each blocked call raises at the call site and is also recorded, and the fixture re-raises at teardown, so the test
still fails when production code catches the raised error. A test marked ``live_network`` is exempt from both
guards; the marker is not registered or used yet.
"""

from __future__ import annotations

import ipaddress
import socket
import traceback
from collections.abc import Generator
from typing import Any, NoReturn

import pytest

from src.data.yfinance import client as yfinance_client_module

LIVE_NETWORK_MARKER = "live_network"
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})


class NetworkAccessError(AssertionError):
    """Raised when a test reaches a live network path without an explicit stub."""


class YahooNetworkAccessError(NetworkAccessError):
    """Raised when a test reaches the live Yahoo network layer without an explicit stub."""


class SocketNetworkAccessError(NetworkAccessError):
    """Raised when a test opens a non-loopback socket connection without an explicit stub."""


def _caller(depth: int) -> str:
    frame = traceback.extract_stack(limit=depth)[0]
    return f"{frame.filename}:{frame.lineno} {frame.name}"


class BlockedYFinance:
    """Stand-in for the ``yfinance`` module whose network entry points fail loudly and are recorded.

    ``src/data/yfinance/client.py`` reaches the network only through ``yf.download`` and ``yf.Ticker``
    (``fast_info`` / ``info``), so guarding those two names covers every ``YFinanceClient`` network method.
    """

    def __init__(self) -> None:
        self.blocked_calls: list[str] = []

    def _block(self, name: str) -> NoReturn:
        self.blocked_calls.append(f"yfinance.{name} (from {_caller(4)})")
        msg = (
            f"yfinance.{name} was reached without a stub, which would make a live Yahoo call. "
            "Inject a fake client or patch 'src.data.yfinance.client.yf' for this test."
        )
        raise YahooNetworkAccessError(msg)

    def download(self, *_arguments: object, **_keywords: object) -> NoReturn:
        self._block("download")

    def Ticker(self, *_arguments: object, **_keywords: object) -> NoReturn:  # noqa: N802
        self._block("Ticker")


def is_loopback_address(address: object) -> bool:
    """Return whether a socket address stays on the local machine (loopback host or a non-IP address family)."""
    if not isinstance(address, tuple) or not address:
        return True  # AF_UNIX path or other non-network address
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    # IPv6Address.is_loopback ignores IPv4-mapped addresses before later 3.12 patch releases; unwrap explicitly.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


class SocketGuard:
    """Records and rejects non-loopback ``connect`` / ``connect_ex`` calls."""

    def __init__(self) -> None:
        self.blocked_calls: list[str] = []
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex
        self._getaddrinfo = socket.getaddrinfo

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace the socket connect methods for the current test."""
        monkeypatch.setattr(socket.socket, "connect", self._guarded(self._connect, "connect"))
        monkeypatch.setattr(socket.socket, "connect_ex", self._guarded(self._connect_ex, "connect_ex"))
        monkeypatch.setattr(socket, "getaddrinfo", self._guarded_lookup(self._getaddrinfo))

    def _guarded(self, original: Any, name: str) -> Any:
        def guarded(sock: socket.socket, address: Any) -> Any:
            if not is_loopback_address(address):
                self.blocked_calls.append(f"socket.{name}{address!r} (from {_caller(4)})")
                msg = (
                    f"socket.{name} to {address!r} was reached without a stub, which would make a live network "
                    "call. Inject a fake transport or patch the calling module for this test."
                )
                raise SocketNetworkAccessError(msg)
            return original(sock, address)

        return guarded

    def _guarded_lookup(self, original: Any) -> Any:
        def guarded(host: Any, *arguments: Any, **keywords: Any) -> Any:
            name = host.decode("ascii", "replace") if isinstance(host, bytes) else host
            if isinstance(name, str) and name and not _is_ip_literal(name) and not is_loopback_address((name,)):
                self.blocked_calls.append(f"socket.getaddrinfo({name!r}) (from {_caller(4)})")
                msg = (
                    f"socket.getaddrinfo for {name!r} was reached without a stub, which would make a live DNS "
                    "lookup. Inject a fake transport or patch the calling module for this test."
                )
                raise SocketNetworkAccessError(msg)
            return original(host, *arguments, **keywords)

        return guarded


def _exempt(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker(LIVE_NETWORK_MARKER) is not None


@pytest.fixture(autouse=True)
def block_live_yahoo(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Fail any test that reaches YFinanceClient's network methods unless it stubs them explicitly.

    A test that patches ``src.data.yfinance.client.yf`` or replaces the client's methods overrides this guard.
    """
    if _exempt(request):
        yield
        return
    blocked = BlockedYFinance()
    monkeypatch.setattr(yfinance_client_module, "yf", blocked)
    yield
    if blocked.blocked_calls:
        msg = f"Test reached live Yahoo network entry points without a stub: {blocked.blocked_calls}"
        raise YahooNetworkAccessError(msg)


@pytest.fixture(autouse=True)
def block_external_sockets(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Fail any test that opens a non-loopback socket connection unless it stubs the caller explicitly."""
    if _exempt(request):
        yield
        return
    guard = SocketGuard()
    guard.install(monkeypatch)
    yield
    if guard.blocked_calls:
        msg = f"Test opened non-loopback socket connections without a stub: {guard.blocked_calls}"
        raise SocketNetworkAccessError(msg)
