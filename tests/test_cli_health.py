"""Offline tests of the ``health`` command: injected fake adapters, no call to a real service."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from collections.abc import Mapping
from dataclasses import replace
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src import cli_health
from src.cli import app
from src.config import settings
from src.core.provider_failure_kind import ProviderFailureKind
from src.core.repository_root import REPOSITORY_ROOT
from src.data.base_client import DataFetchError
from src.data.provider_checks import (
    CheckVerdict,
    ConnectionStep,
    ProviderCheckResult,
    ProviderClients,
    SecTransport,
    SecUnavailable,
)
from src.data.yfinance.client import YFinanceQuote
from src.reporting.documents.health import ProviderHealthDocument, ProviderLibrary
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()
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


def _no_proxy(host: str) -> str | None:  # noqa: ARG001
    """Stand in for proxy detection on a machine with no proxy."""
    return None


def _clients(yahoo: _FakeYahoo | None = None, *, facts: object | None = None) -> ProviderClients:
    transport = SecTransport(_sec_fetcher(facts=facts), _SEC_AGENT)  # type: ignore[arg-type]
    return ProviderClients(
        yahoo=yahoo or _FakeYahoo(), sec=transport, connection=ConnectionStep(connect=_connected, https_proxy=_no_proxy)
    )


def _invoke(clients: ProviderClients, *arguments: str) -> tuple[int, str]:
    with patch.object(cli_health, "build_provider_clients", return_value=clients):
        result = runner.invoke(app, ["health", *arguments])
    return result.exit_code, result.output


def _invoke_json(clients: ProviderClients, *arguments: str) -> tuple[int, str, ProviderHealthDocument]:
    """Run ``health --json``; return the exit code, standard output exactly, and the document it holds."""
    with patch.object(cli_health, "build_provider_clients", return_value=clients):
        result = runner.invoke(app, ["health", "--json", *arguments])
    return result.exit_code, result.stdout, ProviderHealthDocument.model_validate_json(result.stdout)


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
        (DataFetchError("slow", kind=ProviderFailureKind.RATE_LIMITED, provider_id="yfinance"), "rate limited"),
        (
            DataFetchError("odd", kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id="yfinance"),
            "unexpected response",
        ),
        (DataFetchError("none", kind=ProviderFailureKind.NO_DATA, provider_id="yfinance"), "no data"),
        (RuntimeError("defect"), "failed"),
    ],
    ids=["unreachable", "rate limited", "unexpected response", "no data", "no kind"],
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


def test_unknown_provider_is_an_invalid_parameter_listing_the_valid_ids() -> None:
    exit_code, output = _invoke(_clients(), "--provider", "unknown")

    assert exit_code == 1
    assert "yfinance, sec_edgar" in normalize_cli_output(output)


def test_missing_sec_identity_is_reported_as_not_configured_and_exits_one() -> None:
    with patch.object(settings, "sec_user_agent", None):
        clients = cli_health.build_provider_clients()
        with patch.object(cli_health, "build_provider_clients", return_value=clients):
            result = runner.invoke(app, ["health", "--provider", "sec_edgar"])

    output = normalize_cli_output(result.output)
    assert isinstance(clients.sec, SecUnavailable)
    assert result.exit_code == 1
    assert output.startswith("sec_edgar: not configured (probe: AAPL ticker map and company facts, ")
    assert "SEC EDGAR access is not configured" in output
    assert "failed" not in output


def test_configured_sec_identity_composes_a_transport_with_the_stripped_identity() -> None:
    with patch.object(settings, "sec_user_agent", f"  {_SEC_AGENT}  "):
        clients = cli_health.build_provider_clients()

    assert isinstance(clients.sec, SecTransport)
    assert clients.sec.user_agent == _SEC_AGENT


def test_health_help_lists_the_provider_and_json_options() -> None:
    result = runner.invoke(app, ["health", "--help"])

    help_text = normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "--provider" in help_text
    assert "--json" in help_text


_NOT_CONFIGURED = SecUnavailable("SEC EDGAR access is not configured.")
_UNEXPECTED_ERROR = RuntimeError("defect")


def _outcome_clients(verdict: CheckVerdict) -> tuple[ProviderClients, str]:
    """Return fake clients that produce *verdict* for the provider named by the second value."""
    if verdict is CheckVerdict.OK:
        return _clients(), "yfinance"
    if verdict is CheckVerdict.NOT_CONFIGURED:
        return replace(_clients(), sec=_NOT_CONFIGURED), "sec_edgar"
    failures: dict[CheckVerdict, Exception] = {
        CheckVerdict.UNREACHABLE: DataFetchError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance"),
        CheckVerdict.RATE_LIMITED: DataFetchError(
            "slow", kind=ProviderFailureKind.RATE_LIMITED, provider_id="yfinance"
        ),
        CheckVerdict.UNEXPECTED_RESPONSE: DataFetchError(
            "odd", kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id="yfinance"
        ),
        CheckVerdict.NO_DATA: DataFetchError("none", kind=ProviderFailureKind.NO_DATA, provider_id="yfinance"),
        CheckVerdict.FAILED: _UNEXPECTED_ERROR,
    }
    return _clients(_FailingYahoo(failures[verdict])), "yfinance"


_TEXT_WORDS = {
    CheckVerdict.OK: "ok",
    CheckVerdict.UNREACHABLE: "unreachable",
    CheckVerdict.RATE_LIMITED: "rate limited",
    CheckVerdict.UNEXPECTED_RESPONSE: "unexpected response",
    CheckVerdict.NO_DATA: "no data",
    CheckVerdict.NOT_CONFIGURED: "not configured",
    CheckVerdict.FAILED: "failed",
}


@pytest.mark.parametrize("verdict", list(CheckVerdict), ids=lambda verdict: verdict.value)
def test_each_of_the_seven_outcomes_is_printed_in_text_with_the_matching_exit_code(verdict: CheckVerdict) -> None:
    clients, provider = _outcome_clients(verdict)

    exit_code, output = _invoke(clients, "--provider", provider)

    assert exit_code == (0 if verdict is CheckVerdict.OK else 1)
    assert output.startswith(f"{provider}: {_TEXT_WORDS[verdict]} (probe: ")
    assert len(output.strip().splitlines()) == 1


@pytest.mark.parametrize("verdict", list(CheckVerdict), ids=lambda verdict: verdict.value)
def test_each_of_the_seven_outcomes_is_written_in_json_with_the_matching_exit_code(verdict: CheckVerdict) -> None:
    clients, provider = _outcome_clients(verdict)

    exit_code, stdout, document = _invoke_json(clients, "--provider", provider)

    assert exit_code == (0 if verdict is CheckVerdict.OK else 1)
    (entry,) = document.providers
    assert entry.provider_id == provider
    assert entry.verdict == verdict.value
    assert (entry.detail is None) is (verdict is CheckVerdict.OK)
    assert document.schema_version == 3
    assert stdout.endswith("\n")
    assert len(stdout.strip().splitlines()) == 1


def test_json_standard_output_holds_only_the_document_for_a_mixed_result() -> None:
    clients = replace(_clients(_FailingYahoo(_UNEXPECTED_ERROR)), sec=_NOT_CONFIGURED)

    exit_code, stdout, document = _invoke_json(clients)

    assert exit_code == 1
    assert json.loads(stdout) == document.model_dump(mode="json")
    assert [(entry.provider_id, entry.verdict) for entry in document.providers] == [
        ("yfinance", "failed"),
        ("sec_edgar", "not_configured"),
    ]
    yahoo, sec = document.providers
    assert yahoo.detail == "RuntimeError: defect"
    assert sec.detail == "SEC EDGAR access is not configured."
    assert yahoo.probe.startswith("connection to query2.finance.yahoo.com")
    assert sec.probe == "AAPL ticker map and company facts"


def test_json_with_every_check_passing_exits_zero_and_lists_both_providers_with_null_details() -> None:
    exit_code, _stdout, document = _invoke_json(_clients())

    assert exit_code == 0
    assert [(entry.provider_id, entry.verdict, entry.detail) for entry in document.providers] == [
        ("yfinance", "ok", None),
        ("sec_edgar", "ok", None),
    ]
    assert all(entry.elapsed_seconds >= 0 for entry in document.providers)


def test_json_provider_option_runs_only_the_named_provider() -> None:
    yahoo = _FakeYahoo()

    exit_code, _stdout, document = _invoke_json(_clients(yahoo), "--provider", " SEC_EDGAR ")

    assert exit_code == 0
    assert [entry.provider_id for entry in document.providers] == ["sec_edgar"]
    assert yahoo.calls == 0


def test_json_with_an_unknown_provider_writes_the_failure_envelope_and_no_health_document() -> None:
    with patch.object(cli_health, "build_provider_clients", return_value=_clients()):
        result = runner.invoke(app, ["health", "--json", "--provider", "unknown"])

    assert result.exit_code == 1
    assert result.stderr == ""
    document = json.loads(result.stdout)
    assert document["reason_code"] == "invalid_parameter"
    assert document["parameters"] == ["--provider"]
    assert "providers" not in document


def test_the_document_is_a_report_and_not_the_failure_envelope() -> None:
    _exit_code, stdout, _document = _invoke_json(_clients(_FailingYahoo(_UNEXPECTED_ERROR)))

    assert set(json.loads(stdout)) == {"schema_version", "providers"}


def test_the_checked_in_schema_lists_the_seven_verdicts_in_order() -> None:
    schema = json.loads((REPOSITORY_ROOT / "schemas" / "provider-health.schema.json").read_text(encoding="utf-8"))

    verdicts = schema["$defs"]["ProviderHealthEntry"]["properties"]["verdict"]["enum"]
    assert verdicts == [verdict.value for verdict in CheckVerdict]


def test_each_provider_names_its_library_where_it_has_one() -> None:
    from importlib.metadata import version  # noqa: PLC0415 - the installed version is what the document must carry

    _exit_code, _stdout, document = _invoke_json(_clients())

    yahoo, sec = document.providers
    assert (yahoo.provider_id, sec.provider_id) == ("yfinance", "sec_edgar")
    assert yahoo.library is not None
    assert (yahoo.library.name, yahoo.library.version) == ("yfinance", version("yfinance"))
    assert sec.library is None


def test_the_library_version_is_read_from_package_metadata() -> None:
    results = [
        ProviderCheckResult("yfinance", "probe", True, 0.0),
        ProviderCheckResult("sec_edgar", "probe", True, 0.0),
    ]
    seen: list[str] = []

    def fake_version(name: str) -> str:
        seen.append(name)
        return "9.8.7"

    document = cli_health.health_document(results, library_version=fake_version)

    assert seen == ["yfinance"]
    assert document.providers[0].library == ProviderLibrary(name="yfinance", version="9.8.7")
    assert document.providers[1].library is None


def test_a_library_that_is_not_installed_is_reported_as_null_and_not_as_a_failure() -> None:
    def missing(name: str) -> str:
        raise PackageNotFoundError(name)

    document = cli_health.health_document(
        [ProviderCheckResult("yfinance", "probe", True, 0.0)], library_version=missing
    )

    assert document.providers[0].library is None


def test_the_library_is_in_json_only_and_text_output_is_unchanged() -> None:
    exit_code, output = _invoke(_clients(), "--provider", "yfinance")

    assert exit_code == 0
    assert "yfinance" in output
    assert "library" not in output.lower()
    assert len(output.strip().splitlines()) == 1


def test_the_checked_in_schema_requires_a_nullable_library_and_is_version_three() -> None:
    schema = json.loads((REPOSITORY_ROOT / "schemas" / "provider-health.schema.json").read_text(encoding="utf-8"))

    entry = schema["$defs"]["ProviderHealthEntry"]
    assert "library" in entry["required"]
    assert {"type": "null"} in entry["properties"]["library"]["anyOf"]
    library = schema["$defs"]["ProviderLibrary"]
    assert sorted(library["properties"]) == ["name", "version"]
    assert schema["properties"]["schema_version"]["const"] == 3
    assert ProviderHealthDocument.model_validate({"schema_version": 3, "providers": []}).schema_version == 3


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
        run=lambda clients: checks.check_yfinance(clients.yahoo, spec=spec, connection=clients.connection),
    )
    cli_health.PROVIDER_CHECKS = (entry,)
    cli_health.build_provider_clients = lambda: checks.ProviderClients(
        yahoo=HungYahoo(), sec=checks.SecUnavailable("not used"), connection=checks.ConnectionStep(
            connect=lambda host, port, timeout: None, https_proxy=lambda host: None
        )
    )
    app(["health"])
    """
)


def test_process_exits_with_status_one_after_a_check_whose_adapter_never_returns() -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _HUNG_ADAPTER_SCRIPT],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=_TIMED_OUT_PROCESS_LIMIT_SECONDS,
        check=False,
    )

    assert completed.returncode == 1, completed.stderr
    assert "yfinance: unreachable" in completed.stdout
    assert "timed out after 0.3 s" in completed.stdout
