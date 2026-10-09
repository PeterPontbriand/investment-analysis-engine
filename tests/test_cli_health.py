"""Offline tests of the ``health`` command: injected fake adapters, no call to a real service."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src import cli_health
from src.cli import app
from src.config import settings
from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.provider_checks import ProviderClients, SecTransport, SecUnavailable
from src.data.yfinance.client import YFinanceQuote
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()
_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SEC_AGENT = "Test Agent test@example.com"
_TIMED_OUT_PROCESS_LIMIT_SECONDS = 60


class _FakeYahoo:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:  # noqa: ARG002
        self.calls += 1
        columns = {name: [1.0, 2.0] for name in ("Open", "High", "Low", "Close", "Volume")}
        return pd.DataFrame(columns, index=pd.date_range("2026-09-01", periods=2))

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:  # noqa: ARG002
        return YFinanceQuote(price=10.0, currency="USD")


def _sec_fetcher(*, facts: object | None = None) -> object:
    def fetch(url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:  # noqa: ARG001
        if url.endswith("company_tickers.json"):
            return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        return {"facts": {"us-gaap": {}}} if facts is None else facts

    return fetch


def _connected(host: str, port: int, timeout_seconds: float) -> None:  # noqa: ARG001
    """Stand in for a successful connection."""


def _clients(yahoo: _FakeYahoo | None = None, *, facts: object | None = None) -> ProviderClients:
    transport = SecTransport(_sec_fetcher(facts=facts), _SEC_AGENT)  # type: ignore[arg-type]
    return ProviderClients(yahoo=yahoo or _FakeYahoo(), sec=transport, connect=_connected)


def _invoke(clients: ProviderClients, *arguments: str) -> tuple[int, str]:
    with patch.object(cli_health, "build_provider_clients", return_value=clients):
        result = runner.invoke(app, ["health", *arguments])
    return result.exit_code, result.output


def test_all_checks_passing_exits_zero_with_one_line_per_provider() -> None:
    exit_code, output = _invoke(_clients())

    lines = output.strip().splitlines()
    assert exit_code == 0
    assert len(lines) == 2
    assert lines[0].startswith(
        "yfinance: ok (probe: connection to query2.finance.yahoo.com, AAPL quote and daily history, "
    )
    assert lines[1].startswith("sec_edgar: ok (probe: AAPL ticker map and company facts, ")
    assert all(line.endswith(" s)") for line in lines)


def test_one_failing_check_with_a_kind_prints_the_kind_and_its_detail_after_a_dash() -> None:
    exit_code, output = _invoke(_clients(facts={"facts": {}}))

    lines = output.strip().splitlines()
    assert exit_code == 1
    assert lines[0].startswith("yfinance: ok")
    assert lines[1].startswith("sec_edgar: unexpected response (probe: AAPL ticker map and company facts, ")
    assert lines[1].endswith(" s) - company facts document has no 'us-gaap' mapping under 'facts'")


class _FailingYahoo(_FakeYahoo):
    def __init__(self, failure: Exception) -> None:
        super().__init__()
        self.failure = failure

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:  # noqa: ARG002
        raise self.failure


@pytest.mark.parametrize(
    ("failure", "verdict"),
    [
        (DataFetchError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance"), "unreachable"),
        (
            DataFetchError("odd", kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id="yfinance"),
            "unexpected response",
        ),
        (DataFetchError("none", kind=ProviderFailureKind.NO_DATA, provider_id="yfinance"), "no data"),
        (RuntimeError("defect"), "failed"),
    ],
    ids=["unreachable", "unexpected response", "no data", "no kind"],
)
def test_a_failed_check_prints_its_verdict_and_keeps_the_detail(failure: Exception, verdict: str) -> None:
    exit_code, output = _invoke(_clients(_FailingYahoo(failure)), "--provider", "yfinance")

    assert exit_code == 1
    assert output.startswith(
        f"yfinance: {verdict} (probe: connection to query2.finance.yahoo.com, AAPL quote and daily history, "
    )
    assert output.strip().endswith(f" s) - {type(failure).__name__}: {failure}")


def test_provider_option_runs_only_the_named_provider() -> None:
    yahoo = _FakeYahoo()

    exit_code, output = _invoke(_clients(yahoo), "--provider", "sec_edgar")

    assert exit_code == 0
    assert [line.split(":")[0] for line in output.strip().splitlines()] == ["sec_edgar"]
    assert yahoo.calls == 0


def test_provider_option_is_case_insensitive() -> None:
    exit_code, output = _invoke(_clients(), "--provider", " YFinance ")

    assert exit_code == 0
    assert output.strip().startswith("yfinance: ok")


def test_unknown_provider_is_a_usage_error_listing_the_valid_ids() -> None:
    exit_code, output = _invoke(_clients(), "--provider", "massive")

    assert exit_code == 2
    assert "yfinance, sec_edgar" in normalize_cli_output(output)


def test_missing_sec_identity_fails_the_sec_check_with_the_not_configured_wording() -> None:
    with patch.object(settings, "sec_user_agent", None):
        clients = cli_health.build_provider_clients()
        with patch.object(cli_health, "build_provider_clients", return_value=clients):
            result = runner.invoke(app, ["health", "--provider", "sec_edgar"])

    output = normalize_cli_output(result.output)
    assert isinstance(clients.sec, SecUnavailable)
    assert result.exit_code == 1
    assert "sec_edgar: failed" in output
    assert "SEC EDGAR access is not configured" in output


def test_configured_sec_identity_composes_a_transport_with_the_stripped_identity() -> None:
    with patch.object(settings, "sec_user_agent", f"  {_SEC_AGENT}  "):
        clients = cli_health.build_provider_clients()

    assert isinstance(clients.sec, SecTransport)
    assert clients.sec.user_agent == _SEC_AGENT


def test_health_is_listed_among_the_commands_and_has_no_json_option() -> None:
    result = runner.invoke(app, ["health", "--help"])

    help_text = normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "--provider" in help_text
    assert "--json" not in help_text


_HUNG_ADAPTER_SCRIPT = textwrap.dedent(
    """
    import dataclasses
    import threading

    from src import cli_health
    from src.cli import app
    from src.data import provider_checks as checks


    class HungYahoo:
        def fetch_data(self, ticker, start_date, end_date=None):
            threading.Event().wait()

        def fetch_current_quote(self, ticker):
            threading.Event().wait()


    spec = dataclasses.replace(checks.YAHOO_SPEC, timeout_seconds=0.3)
    entry = checks.ProviderCheckEntry(
        provider_id="yfinance",
        probe=checks.yahoo_probe_description(spec),
        run=lambda clients: checks.check_yfinance(clients.yahoo, spec=spec, connect=clients.connect),
    )
    cli_health.PROVIDER_CHECKS = (entry,)
    cli_health.build_provider_clients = lambda: checks.ProviderClients(
        yahoo=HungYahoo(), sec=checks.SecUnavailable("not used"), connect=lambda host, port, timeout: None
    )
    app(["health"])
    """
)


def test_process_exits_with_status_one_after_a_check_whose_adapter_never_returns() -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _HUNG_ADAPTER_SCRIPT],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=_TIMED_OUT_PROCESS_LIMIT_SECONDS,
        check=False,
    )

    assert completed.returncode == 1, completed.stderr
    assert "yfinance: unreachable" in completed.stdout
    assert "timed out after 0.3 s" in completed.stdout
