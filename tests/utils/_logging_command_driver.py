"""Run one real ``ian momentum`` command offline, for the operational-logging tests.

The driver is executed in a subprocess so that ``src.main.main`` installs the real global logging, the real
command runs against a migrated throwaway database named by the environment, and the process exits the way the
installed command does. Only the network is replaced: ``yfinance.download`` returns a canned frame (or nothing),
the optional Yahoo metadata lookups return nothing, and any socket is refused.

Usage: ``python -m tests.utils._logging_command_driver MODE [--json] [--no-logging]`` where MODE is
``success`` (a canned price history), ``fail`` (no price history, exit 1), ``unexpected`` (an exception a
command handler reports generically) or ``crash`` (an exception that no command handler catches).
"""

import socket
import sys
from typing import Any
from unittest.mock import patch

import pandas as pd

TICKER = "OFFLINE"
SHORT_WINDOW = "2"
LONG_WINDOW = "5"


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=10)
    close = [10.0, 11.0, 12.0, 13.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": [1000] * 10},
        index=dates,
    )


def _refuse(*_args: object, **_kwargs: object) -> None:
    raise OSError("network access is not allowed in this driver")


def main(argv: list[str]) -> None:
    """Patch the network, optionally disable logging, and run the command through the real entry point."""
    mode = argv[0]
    json_output = "--json" in argv
    no_logging = "--no-logging" in argv
    download = pd.DataFrame() if mode == "fail" else _frame()
    patches: list[Any] = [
        patch("socket.socket", _refuse),
        patch.object(socket, "create_connection", _refuse),
        patch("src.data.yfinance.client.yf.download", return_value=download),
        patch("src.data.yfinance.client.YFinanceClient._fetch_currency", return_value="USD"),
        patch("src.data.yfinance.client.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.data.yfinance.client.YFinanceClient.resolve_instrument_kind", return_value=None),
    ]
    if mode == "unexpected":
        patches.append(
            patch("src.data.yfinance.client.YFinanceClient.fetch_data", side_effect=RuntimeError("driver unexpected"))
        )
    if mode == "crash":
        patches.append(
            patch("src.strategies.momentum.cli._presentation_mode", side_effect=RuntimeError("driver crash"))
        )
    if no_logging:
        patches.append(patch("src.main.setup_global_logging", lambda: None))
    command = ["ian", "momentum", TICKER, "--short-window", SHORT_WINDOW, "--long-window", LONG_WINDOW]
    if json_output:
        command.append("--json")
    sys.argv = command
    for item in patches:
        item.start()
    from src.main import main as ian_main  # noqa: PLC0415

    ian_main()


if __name__ == "__main__":
    main(sys.argv[1:])
