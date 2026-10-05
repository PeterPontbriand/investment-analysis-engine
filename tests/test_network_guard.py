"""Prove the suite-wide network guards record a blocked call, fail the test, and yield to explicit stubs.

Each case runs a tiny inner test session that loads the real guard fixtures, so the guards are exercised exactly
as every other test sees them. No live call is made: the guards reject it before it leaves the process.
"""

import pytest

from tests._network_guard import is_loopback_address

pytest_plugins = ["pytester"]

_INNER_CONFTEST = "from tests._network_guard import block_external_sockets, block_live_yahoo  # noqa: F401\n"
_EXTERNAL_ADDRESS = "('203.0.113.1', 80)"


def _run(pytester: pytest.Pytester, source: str) -> pytest.RunResult:
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    pytester.makeconftest(_INNER_CONFTEST)
    pytester.makepyfile(source)
    return pytester.runpytest("-p", "no:cacheprovider")


@pytest.mark.parametrize("entry_point", ["download", "Ticker"])
def test_yahoo_entry_point_fails_the_test_even_when_the_caller_swallows_the_error(
    pytester: pytest.Pytester, entry_point: str
) -> None:
    result = _run(
        pytester,
        f"""
        from src.data.yfinance import client

        def test_swallows() -> None:
            try:
                client.yf.{entry_point}("ACME")
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([f"*yfinance.{entry_point}*"])


def test_explicit_yahoo_stub_overrides_the_guard(pytester: pytest.Pytester) -> None:
    result = _run(
        pytester,
        """
        from unittest.mock import MagicMock, patch

        from src.data.yfinance import client

        def test_stubbed() -> None:
            stub = MagicMock()
            stub.Ticker.return_value.fast_info = {"currency": "USD"}
            with patch.object(client, "yf", stub):
                assert client.yf.Ticker("ACME").fast_info["currency"] == "USD"
        """,
    )
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("method", ["connect", "connect_ex"])
def test_external_socket_connection_fails_the_test_even_when_the_caller_swallows_the_error(
    pytester: pytest.Pytester, method: str
) -> None:
    result = _run(
        pytester,
        f"""
        import socket

        def test_swallows() -> None:
            with socket.socket() as sock:
                try:
                    sock.{method}({_EXTERNAL_ADDRESS})
                except Exception:
                    pass
        """,
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([f"*socket.{method}*203.0.113.1*"])


def test_urllib_request_is_blocked_before_it_leaves_the_process(pytester: pytest.Pytester) -> None:
    result = _run(
        pytester,
        """
        from urllib.request import urlopen

        def test_urllib() -> None:
            try:
                urlopen("http://203.0.113.1/", timeout=1)
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(passed=1, errors=1)


def test_loopback_connections_and_socket_pairs_stay_allowed(pytester: pytest.Pytester) -> None:
    result = _run(
        pytester,
        """
        import asyncio
        import socket

        def test_loopback() -> None:
            with socket.socket() as server:
                server.bind(("127.0.0.1", 0))
                server.listen(1)
                with socket.socket() as client:
                    client.connect(server.getsockname())
            first, second = socket.socketpair()
            first.close()
            second.close()

        def test_event_loop() -> None:
            asyncio.run(asyncio.sleep(0))
        """,
    )
    result.assert_outcomes(passed=2)


def test_explicit_socket_stub_overrides_the_guard(pytester: pytest.Pytester) -> None:
    result = _run(
        pytester,
        f"""
        import socket
        from unittest.mock import patch

        def test_stubbed() -> None:
            with patch.object(socket.socket, "connect", return_value=None):
                socket.socket().connect({_EXTERNAL_ADDRESS})
        """,
    )
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (("127.0.0.1", 80), True),
        (("::1", 80, 0, 0), True),
        (("localhost", 80), True),
        (("::ffff:127.0.0.1", 80), True),
        ("/tmp/socket", True),
        (("203.0.113.1", 80), False),
        (("example.com", 443), False),
        (("2001:db8::1", 443, 0, 0), False),
    ],
)
def test_is_loopback_address(address: object, expected: bool) -> None:
    assert is_loopback_address(address) is expected
