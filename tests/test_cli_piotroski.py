"""The ``piotroski`` direct command, its refresh executor and its selection builder, over the captured statements."""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.data.yfinance.financial_facts import YFinanceFinancialFactsAdapter
from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import StatementsFetcher
from investment_analysis_engine.strategies.piotroski import application as piotroski_application
from investment_analysis_engine.strategies.piotroski import cli as piotroski_cli
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiResult
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from tests._cli_helpers import normalize_cli_output
from tests._direct_command_output import _FixtureYahoo
from tests.analysis.piotroski._statements_rig import adapter_of

FLAGS = WatchlistFlags(
    short_window=20,
    long_window=50,
    rsi_period=14,
    as_of=None,
    no_cache=False,
    eps=None,
    eps_basis=None,
    bvps=None,
    current_price=None,
    expected_growth=None,
    aaa_yield=None,
    growth_years=None,
    forward_policy="display-only",
    classification_basis="total-fcf",
    currency="USD",
)


def _provider_without_live_yahoo(*, sec_edgar: SecEdgarFinancialFactsAdapter) -> ProductionFinancialFactsProvider:
    """Compose the production provider as the command does, with a fixture in place of the live Yahoo client."""
    yahoo = YFinanceFinancialFactsAdapter(client=cast(YFinanceClient, _FixtureYahoo()))
    return ProductionFinancialFactsProvider(sec_edgar=sec_edgar, yfinance=yahoo)


@contextmanager
def apple_adapter(adapter: SecEdgarFinancialFactsAdapter | None = None) -> Iterator[None]:
    """Make the command build the captured Apple adapter and no live Yahoo client."""
    with (
        patch.object(
            piotroski_application, "build_sec_edgar_adapter", side_effect=lambda _context: adapter or adapter_of("aapl")
        ),
        patch.object(piotroski_application, "ProductionFinancialFactsProvider", _provider_without_live_yahoo),
    ):
        yield


CRLF = "\r\n"


def text_of(output: str) -> str:
    """Return the command's output with Windows line endings translated."""
    return output.replace(CRLF, "\n")


def invoke(*arguments: str) -> Any:
    return CliRunner().invoke(app, ["piotroski", *arguments])


def test_the_command_prints_the_concise_result_and_exits_zero() -> None:
    with apple_adapter():
        result = invoke("AAPL", "--no-cache")
    assert result.exit_code == 0, result.output
    lines = text_of(result.stdout).split("\n")
    assert lines[0] == "Apple Inc. (AAPL) — Piotroski F-Score: 7 of 9 (complete)"
    assert lines[1].startswith("Fiscal year-end: 2024-09-28 · 10-K 0000320193-24-000123 · us-gaap")


def test_details_and_diagnostics_extend_the_concise_output() -> None:
    with apple_adapter():
        concise = text_of(invoke("AAPL").stdout)
        details = text_of(invoke("AAPL", "--details").stdout)
        diagnostics = text_of(invoke("AAPL", "--diagnostics").stdout)
    assert details.startswith(concise)
    assert "Details — operands of each test" in details
    assert "Provenance" not in details
    assert diagnostics.startswith(details)
    assert "Provenance" in diagnostics
    assert "provider field us-gaap:NetIncomeLoss" in diagnostics


def test_json_is_the_versioned_document() -> None:
    with apple_adapter():
        result = invoke("AAPL", "--json")
    document = json.loads(result.stdout)
    assert result.exit_code == 0
    assert (document["analysis"], document["status"], document["completeness"]) == ("piotroski", "ok", "complete")
    assert document["security_identity"]["instrument_name"] == "Apple Inc."


def test_the_presentation_switches_are_mutually_exclusive_and_the_data_provider_option_is_gone() -> None:
    with apple_adapter():
        exclusive = invoke("AAPL", "--details", "--json")
        assert exclusive.exit_code != 0
        assert "Choose only one of --details, --diagnostics, or --json." in exclusive.output
        assert invoke("AAPL", "--data-provider", "sec_edgar").exit_code == 2


def test_a_boundary_before_the_first_filing_is_an_unavailable_run_with_a_nonzero_exit() -> None:
    with apple_adapter():
        result = invoke("AAPL", "--as-of", "2022-06-01")
    assert result.exit_code != 0
    assert "Piotroski F-Score: unavailable" in normalize_cli_output(result.stderr)


def test_a_provider_failure_is_reported_with_a_nonzero_exit_and_no_score() -> None:
    class Down(StatementsFetcher):
        def __call__(
            self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
        ) -> object:
            del url, headers, not_found, provider_id
            raise FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")

    with apple_adapter(adapter_of("aapl", fetcher=Down("aapl"))):
        result = invoke("AAPL", "--json")
    assert result.exit_code != 0
    document = json.loads(result.stdout)
    assert document["status"] == "provider_error"
    assert document["tests"] == []
    assert document["score"] is None
    assert document["input_failure"]["input_name"] == "anchor_year_end"


def test_the_command_without_a_declared_sec_identity_stops_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sec_user_agent", None)
    result = invoke("AAPL")
    assert result.exit_code != 0
    assert "SEC EDGAR access is not configured" in normalize_cli_output(result.output)


def test_the_selection_builder_reads_only_the_boundary_and_the_cache_flag() -> None:
    assert piotroski_cli.build_selection(FLAGS) == PiotroskiSelection()
    built = piotroski_cli.build_selection(
        WatchlistFlags(**{**FLAGS.__dict__, "as_of": "2025-01-15", "no_cache": True, "short_window": 3})
    )
    assert built.use_cache is False
    assert built.as_of == datetime(2025, 1, 15, 23, 59, 59, 999999, tzinfo=UTC)


def test_the_refresh_executor_runs_the_job_and_captures_the_evidence_and_status() -> None:
    selection = PiotroskiSelection(as_of=datetime(2025, 1, 15, tzinfo=UTC))
    with apple_adapter():
        capture = piotroski_application.refresh(
            ApplicationContext(settings=settings), "AAPL", selection, profile_cache=None
        )
    assert capture.native_status is CalculationStatus.OK
    assert capture.outcome is RunOutcome.COMPLETED
    assert isinstance(capture.native_evidence, PiotroskiResult)
    assert capture.native_evidence.f_score is not None
    assert capture.native_evidence.f_score.score.value == 7.0
    assert capture.provider_failure is None
    assert capture.native_evidence.effective_as_of == selection.as_of
