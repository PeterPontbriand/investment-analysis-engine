"""Unit tests for validating the Typer CLI controller commands and option routing."""

import json
import re
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.analysis.momentum.momentum_analyzer import MomentumMetrics, MomentumRun
from src.cli import GrahamCliMethod, _build_graham_resolver, _quote_provider_id, app
from src.config import settings
from src.core.constants import TrendStatus
from src.data.base_client import DataFetchError
from src.data.market_data import MarketDataContext
from src.data.valuation.facts import ProviderFact, ValuationFactRequest, ValuationField
from tests._cli_helpers import normalize_cli_output
from tests.analysis.graham_value.fixture_valuation_provider import (
    NOW,
    PROVIDER_ID,
    SECURITY_ID,
    SUBJECT_MISSING,
    FixtureValuationProvider,
)

runner = CliRunner()


def test_normalize_cli_output_strips_ansi_and_box_characters() -> None:
    """Prove the helper removes ANSI escape codes and normalizes Rich box/border layout."""
    styled = "\x1b[1m--expected-growth\x1b[0m is required\n╭─╮\n│  use --data-provider massive for TTM EPS  │\n╰─╯"
    normalized = normalize_cli_output(styled)
    assert "--expected-growth is required" in normalized
    assert "use --data-provider massive for TTM EPS" in normalized
    assert "\x1b" not in normalized
    for ch in "─│┌┐└┘╭╮╰╯":
        assert ch not in normalized


class QuoteUnavailableProvider:
    """Delegate fixture fundamentals while making only the optional quote unavailable."""

    def __init__(self) -> None:
        """Initialize the deterministic fixture delegate."""
        self._delegate = FixtureValuationProvider()

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        if request.field_name is ValuationField.CURRENT_PRICE:
            return ()
        return self._delegate.fetch_facts(request)


@pytest.fixture
def mock_metrics() -> MomentumMetrics:
    """Generate static mock momentum results."""
    return MomentumMetrics(
        ticker="BTC-USD",
        status=TrendStatus.BULLISH,
        current_price=100.0,
        short_sma_val=98.0,
        long_sma_val=95.0,
        crossover_signal=1.0,
        timestamp=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )


@pytest.fixture
def fixture_resolver() -> GrahamInputResolver:
    """Return the deterministic Slice-D resolver used by CLI tests."""
    return GrahamInputResolver(FixtureValuationProvider(), clock=lambda: NOW)


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "momentum" in result.output.lower()
    assert "graham" in result.output.lower()
    assert "financial" in result.output.lower()


def test_cli_main_callback() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)


@pytest.fixture
def mock_momentum_run(mock_metrics: MomentumMetrics) -> MomentumRun:
    """Pair mock Momentum metrics with retained daily market context."""
    return MomentumRun(
        metrics=mock_metrics,
        market_data=MarketDataContext(
            provider_id="fixture-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="USD",
            observation_count=500,
        ),
    )


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_success_uses_investor_presenter(mock_run: MagicMock, mock_momentum_run: MomentumRun) -> None:
    mock_run.return_value = mock_momentum_run

    result = runner.invoke(app, ["momentum", "BTC-USD"])

    assert result.exit_code == 0
    assert "BTC-USD — Momentum" in result.output
    assert "Status: Bullish Trend" in result.output
    assert "Price used (Close): 100.00 USD" in result.output
    assert "50-day SMA: 98.00 USD" in result.output
    assert "200-day SMA: 95.00 USD" in result.output
    assert "SMA spread:" in result.output
    assert "Data: fixture-market-source · daily · through 2026-08-21" in result.output
    assert "Limitation:" in result.output
    assert "Analysis Complete" not in result.output
    assert "cli_runtime" not in result.output


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_legacy_ticker_option_still_routes(mock_run: MagicMock, mock_momentum_run: MomentumRun) -> None:
    mock_run.return_value = mock_momentum_run

    result = runner.invoke(app, ["momentum", "--ticker", "BTC-USD"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["ticker"] == "BTC-USD"


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_with_options(mock_run: MagicMock, mock_momentum_run: MomentumRun) -> None:
    mock_run.return_value = mock_momentum_run

    result = runner.invoke(app, ["momentum", "AAPL", "-s", "10", "-l", "30"])

    assert result.exit_code == 0
    config_passed = mock_run.call_args.kwargs["config"]
    assert config_passed.short_window == 10
    assert config_passed.long_window == 30


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_reports_identity_from_retained_market_context(
    mock_run: MagicMock,
    mock_metrics: MomentumMetrics,
) -> None:
    mock_run.return_value = MomentumRun(
        metrics=mock_metrics,
        market_data=MarketDataContext(
            provider_id="alternate-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="CAD",
            observation_count=300,
        ),
    )

    result = runner.invoke(app, ["momentum", "BTC-USD", "--details"])

    assert result.exit_code == 0
    assert "Data provider: alternate-market-source" in result.output
    assert "Data provider: yfinance" not in result.output
    assert "Currency: CAD" in result.output


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_insufficient_history_is_unknown_without_nan(mock_run: MagicMock) -> None:
    metrics = MomentumMetrics(
        ticker="SHORT",
        status=TrendStatus.UNKNOWN,
        current_price=12.0,
        short_sma_val=None,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
    mock_run.return_value = MomentumRun(
        metrics=metrics,
        market_data=MarketDataContext(
            provider_id="fixture-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="USD",
            observation_count=3,
        ),
    )

    result = runner.invoke(app, ["momentum", "SHORT"])

    assert result.exit_code == 0
    assert "Unknown State" in result.output
    assert "insufficient history" in result.output.lower()
    assert "3 observations available; 50 required for the short SMA and 200 required for the long SMA." in result.output
    assert re.search(r"\bnan\b", result.output, flags=re.IGNORECASE) is None


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_json_uses_null_not_nan_and_semantic_state(mock_run: MagicMock) -> None:
    metrics = MomentumMetrics(
        ticker="SHORT",
        status=TrendStatus.UNKNOWN,
        current_price=12.0,
        short_sma_val=None,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
    mock_run.return_value = MomentumRun(
        metrics=metrics,
        market_data=MarketDataContext(
            provider_id="fixture-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="USD",
            observation_count=3,
        ),
    )

    result = runner.invoke(app, ["momentum", "SHORT", "--json"])

    assert result.exit_code == 0
    assert "NaN" not in result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["result"]["short_sma"] is None
    assert payload["result"]["long_sma"] is None
    assert payload["result"]["crossover_signal"] is None
    assert payload["result"]["crossover_state"] is None
    assert payload["result"]["price_basis"] == "latest_historical_close"
    assert payload["source"]["interval"] == "1d"
    assert payload["source"]["observation_count"] == 3


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_diagnostics_are_retained_and_useful(mock_run: MagicMock, mock_momentum_run: MomentumRun) -> None:
    mock_run.return_value = mock_momentum_run

    result = runner.invoke(app, ["momentum", "BTC-USD", "--diagnostics"])

    assert result.exit_code == 0
    assert "Raw crossover signal: 1" in result.output
    assert "Trend relationship: short_above_long" in result.output
    assert "provider=fixture-market-source" in result.output
    assert "No execution trace was retained" not in result.output


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_data_fetch_failure_is_one_clean_message(mock_run: MagicMock) -> None:
    mock_run.side_effect = DataFetchError("provider-library key currentTradingPeriod leaked here")

    result = runner.invoke(app, ["momentum", "FCIM"])

    assert result.exit_code == 1
    assert "Unable to analyze FCIM" in result.output
    assert "verify the ticker symbol" in result.output.lower()
    assert "currentTradingPeriod" not in result.output
    assert "Traceback" not in result.output


@patch("src.cli.MomentumAnalyzer.run_with_context")
def test_cli_momentum_analysis_failure_does_not_expose_internal_text(mock_run: MagicMock) -> None:
    mock_run.side_effect = ValueError("Validation error. See https://errors.pydantic.dev/2.0/v/value_error")

    result = runner.invoke(app, ["momentum", "AAPL"])

    assert result.exit_code == 1
    assert "returned price history could not be analyzed" in result.output
    assert "pydantic.dev" not in result.output


def test_cli_momentum_rejects_reversed_windows_specifically() -> None:
    result = runner.invoke(app, ["momentum", "AAPL", "--short-window", "30", "--long-window", "10"])

    assert result.exit_code == 2
    assert "short window (30) must be smaller than long window (10)" in result.output
    assert "available price history" not in result.output


def test_cli_momentum_rejects_non_positive_window_specifically() -> None:
    result = runner.invoke(app, ["momentum", "AAPL", "--short-window", "0", "--long-window", "30"])

    assert result.exit_code == 2
    assert "short window must be positive (received 0)" in result.output


def test_cli_momentum_help_explains_daily_windows_and_defaults() -> None:
    result = runner.invoke(app, ["momentum", "--help"])

    assert result.exit_code == 0
    normalized_output = normalize_cli_output(result.output)
    assert "Short SMA window in daily market observations" in normalized_output
    assert "Long SMA window in daily market observations" in normalized_output
    assert "[default: 50]" in normalized_output
    assert "[default: 200]" in normalized_output


def test_cli_presentation_modes_are_mutually_exclusive() -> None:
    result = runner.invoke(app, ["momentum", "AAPL", "--details", "--json"])

    assert result.exit_code == 2
    assert "Choose only one" in result.output


def test_cli_graham_missing_sec_user_agent_is_clean_configuration_error() -> None:
    with patch.object(settings, "sec_user_agent", None):
        result = runner.invoke(app, ["graham", "AAPL"])

    assert result.exit_code == 1
    assert "SEC EDGAR access is not configured" in result.output
    assert "SEC_USER_AGENT" in result.output
    assert "Your Name your-email@example.com" in result.output
    assert "Pass user_agent" not in result.output
    assert "Traceback" not in result.output


@patch("src.cli.SecEdgarValuationAdapter")
def test_graham_resolver_passes_configured_sec_identity_explicitly(mock_sec_adapter: MagicMock) -> None:
    declared_identity = "financial-data-agents-test test@example.invalid"

    with patch.object(settings, "sec_user_agent", declared_identity):
        _build_graham_resolver(method=GrahamCliMethod.NUMBER, data_provider=None)

    mock_sec_adapter.assert_called_once_with(user_agent=declared_identity)


@patch("src.cli.SecEdgarValuationAdapter")
def test_graham_growth_default_uses_configured_sec_identity(mock_sec_adapter: MagicMock) -> None:
    declared_identity = "financial-data-agents-test test@example.invalid"

    with patch.object(settings, "sec_user_agent", declared_identity):
        _build_graham_resolver(method=GrahamCliMethod.GROWTH, data_provider=None)

    mock_sec_adapter.assert_called_once_with(user_agent=declared_identity)


def test_cli_graham_number_is_default_ticker_analysis(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(app, ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID])

    assert result.exit_code == 0
    assert f"{SECURITY_ID} — Graham Number" in result.output
    assert "Graham Number (maximum indicated price):" in result.output
    assert "screening ceiling" in result.output
    assert "Intrinsic Value" not in result.output
    assert "USER ASSUMPTION" not in result.output


def test_cli_graham_legacy_ticker_option_still_routes(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(app, ["graham", "--ticker", SECURITY_ID, "--data-provider", PROVIDER_ID])

    assert result.exit_code == 0
    assert f"{SECURITY_ID} — Graham Number" in result.output


def test_cli_graham_number_json_has_schema_and_provenance(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(app, ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID, "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["analysis"] == "graham"
    assert payload["method"] == "graham_number"
    assert payload["ticker"] == SECURITY_ID
    assert payload["status"] == "ok"
    assert payload["result"]["maximum_indicated_price"] is not None
    assert payload["inputs"]["eps"]["basis"] == "three_year_average"
    assert payload["inputs"]["eps"]["source_kind"] == "derived"


def test_cli_graham_number_eps_override_inherits_default_basis(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(
            app,
            ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID, "--eps", "4.0", "--json"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["inputs"]["eps"]["source_kind"] == "override"
    assert payload["inputs"]["eps"]["basis"] == "three_year_average"
    assert any("EPS is a user override" in warning for warning in payload["warnings"])


def test_cli_graham_number_optional_quote_failure_preserves_value() -> None:
    resolver = GrahamInputResolver(QuoteUnavailableProvider(), clock=lambda: NOW)

    with patch("src.cli._build_graham_resolver", return_value=resolver):
        result = runner.invoke(app, ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID])

    assert result.exit_code == 0
    assert "Graham Number (maximum indicated price):" in result.output
    assert "Current price: unavailable" in result.output
    assert "Price comparison: unavailable" in result.output
    assert "Current quote unavailable" in result.output
    assert "Provider returned no data for the requested field" not in result.output


def test_cli_graham_growth_requires_expected_growth() -> None:
    result = runner.invoke(app, ["graham", "AAPL", "--method", "growth", "--aaa-yield", "4.2"])

    assert result.exit_code == 2
    assert "--expected-growth is required" in normalize_cli_output(result.output)


def test_cli_graham_growth_requires_aaa_override_until_series_is_approved() -> None:
    result = runner.invoke(app, ["graham", "AAPL", "--method", "growth", "--expected-growth", "6.0"])

    assert result.exit_code == 2
    assert "no production AAA-yield series is approved" in normalize_cli_output(result.output)


def test_cli_graham_number_rejects_growth_only_flags() -> None:
    result = runner.invoke(app, ["graham", "AAPL", "--expected-growth", "6.0"])

    assert result.exit_code == 2
    assert "valid only with --method growth" in normalize_cli_output(result.output)


def test_cli_graham_growth_rejects_bvps() -> None:
    result = runner.invoke(
        app,
        [
            "graham",
            "AAPL",
            "--method",
            "growth",
            "--expected-growth",
            "6.0",
            "--aaa-yield",
            "4.2",
            "--bvps",
            "20",
        ],
    )

    assert result.exit_code == 2
    assert "--bvps is valid only with --method number" in normalize_cli_output(result.output)


def test_cli_graham_growth_override_heavy_analysis_is_conspicuous(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(
            app,
            [
                "graham",
                SECURITY_ID,
                "--method",
                "growth",
                "--data-provider",
                PROVIDER_ID,
                "--eps",
                "4.8",
                "--expected-growth",
                "6.5",
                "--aaa-yield",
                "4.15",
            ],
        )

    assert result.exit_code == 0
    assert "Expected growth assumption: 6.50 percentage points" in result.output
    assert "Graham Growth Value:" in result.output
    assert "EPS is a user override, not provider-verified data" in result.output
    assert "Warning: AAA yield is user-supplied rather than provider-verified." in result.output
    assert "expected_growth is a user override" not in result.output
    assert "current_aaa_yield is a user override" not in result.output


def test_cli_graham_fully_override_driven_unverified_ticker_is_rejected(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(
            app,
            [
                "graham",
                "NOTREAL",
                "--method",
                "growth",
                "--data-provider",
                PROVIDER_ID,
                "--eps",
                "4.8",
                "--expected-growth",
                "6.5",
                "--aaa-yield",
                "4.15",
                "--current-price",
                "50.0",
            ],
        )

    assert result.exit_code == 1
    assert "Unable to verify ticker NOTREAL" in result.output
    assert "no provider-backed security fact or quote was resolved" in result.output
    assert "Graham Growth Value:" not in result.output


def test_cli_graham_invalid_or_unavailable_ticker_has_one_clean_failure(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(app, ["graham", SUBJECT_MISSING, "--data-provider", PROVIDER_ID])

    assert result.exit_code == 1
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1
    assert f"Unable to analyze {SUBJECT_MISSING}" in lines[0]
    assert "required financial data is unavailable" in lines[0]
    assert "Traceback" not in result.output
    assert "pydantic.dev" not in result.output


def test_cli_graham_diagnostics_exposes_trace_only_when_requested(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        concise = runner.invoke(app, ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID])
        diagnostics = runner.invoke(
            app,
            ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID, "--diagnostics"],
        )

    assert concise.exit_code == 0
    assert diagnostics.exit_code == 0
    assert "Diagnostics" not in concise.output
    assert "Diagnostics" in diagnostics.output
    assert "cache" in diagnostics.output.lower()
    assert "provider" in diagnostics.output.lower()


def test_cli_graham_details_shows_financial_provenance(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(app, ["graham", SECURITY_ID, "--data-provider", PROVIDER_ID, "--details"])

    assert result.exit_code == 0
    assert "Details" in result.output
    assert "basis: 3-year average" in result.output
    assert "provider:" in result.output
    assert "derivation: arithmetic_mean" in result.output


def test_cli_graham_conflicting_positional_and_option_tickers_are_usage_error() -> None:
    result = runner.invoke(app, ["graham", "AAPL", "--ticker", "MSFT"])

    assert result.exit_code == 2
    assert "refer to different symbols" in result.output


def test_cli_graham_unsupported_provider_fails_before_network_setup() -> None:
    result = runner.invoke(app, ["graham", "AAPL", "--data-provider", "not-a-provider"])

    assert result.exit_code == 1
    assert "Unsupported valuation data provider" in result.output
    assert "sec_edgar" in result.output
    assert "massive" in result.output


def test_cli_graham_unexpected_failure_does_not_leak_exception_text() -> None:
    resolver = MagicMock(spec=GrahamInputResolver)
    resolver.assemble_graham_number.side_effect = RuntimeError("secret provider implementation detail")

    with patch("src.cli._build_graham_resolver", return_value=resolver):
        result = runner.invoke(app, ["graham", "AAPL"])

    assert result.exit_code == 1
    assert "Graham analysis failed unexpectedly for AAPL" in result.output
    assert "secret provider implementation detail" not in result.output
    assert "Traceback" not in result.output


def test_cli_graham_transitional_growth_flag_aliases_remain_supported(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(
            app,
            [
                "graham",
                SECURITY_ID,
                "--method",
                "growth",
                "--data-provider",
                PROVIDER_ID,
                "--expected-growth-rate",
                "6.5",
                "--current-aaa-yield",
                "4.15",
            ],
        )

    assert result.exit_code == 0
    assert "Graham Growth Value" in result.output


def test_cli_graham_growth_eps_override_inherits_ttm_basis(fixture_resolver: GrahamInputResolver) -> None:
    with patch("src.cli._build_graham_resolver", return_value=fixture_resolver):
        result = runner.invoke(
            app,
            [
                "graham",
                SECURITY_ID,
                "--method",
                "growth",
                "--data-provider",
                PROVIDER_ID,
                "--eps",
                "4.8",
                "--expected-growth",
                "6.5",
                "--aaa-yield",
                "4.15",
                "--json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["inputs"]["eps"]["source_kind"] == "override"
    assert payload["inputs"]["eps"]["basis"] == "ttm"


def test_graham_quote_provider_routing_is_method_aware() -> None:
    assert _quote_provider_id(GrahamCliMethod.NUMBER, None) == "yfinance"
    assert _quote_provider_id(GrahamCliMethod.NUMBER, "sec_edgar") == "yfinance"
    assert _quote_provider_id(GrahamCliMethod.NUMBER, "massive") == "massive"
    assert _quote_provider_id(GrahamCliMethod.GROWTH, None) == "yfinance"
    assert _quote_provider_id(GrahamCliMethod.GROWTH, "sec_edgar") == "yfinance"
    assert _quote_provider_id(GrahamCliMethod.NUMBER, PROVIDER_ID) == PROVIDER_ID
