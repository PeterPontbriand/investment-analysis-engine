"""Direct-command `--save-run` (F3) tests: opt-in Analysis Run persistence.

Isolation note: `src.cli`'s own `settings` binding is deliberately NOT
covered by the shared `isolated_cli_database` fixture (see
`tests/_cli_helpers.py`'s docstring) because that name is shared for
configuration well beyond database access, and other already-accepted tests
rely on mutating the real shared settings singleton directly. This module
isolates `src.cli.settings` locally instead, preserving every other field
from the real settings (built the same way `src.cli_database`'s own
maintenance commands already do: `ProjectSettings(**(settings.model_dump() |
{"database_url": ...}))`) so only the run-storage database target changes.
"""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from typer.testing import CliRunner

import src.cli
from alembic import command
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.momentum.momentum_analyzer import MomentumMetrics, MomentumRun
from src.cli import app
from src.config import ProjectSettings
from src.config import settings as real_settings
from src.core.constants import TrendStatus
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.market_data import MarketDataContext
from src.data.repositories.analysis_runs import AnalysisRunConflictError, SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import NOW, FixtureFinancialFactsProvider
from src.evaluation.fixtures.instrument_profiles import fixture_known_etf_profile
from src.workspace.models import RunOutcome
from src.workspace.requests import GrahamGrowthSelection
from src.workspace.runs import RunQuery
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_save_run_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `src.cli.settings`'s run-storage database at a disposable, migrated file.

    Every other field (SEC identity, etc.) is preserved from the real settings,
    so this module's tests do not disturb unrelated already-accepted behavior.
    """
    url = f"sqlite:///{(tmp_path / 'save_run.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    isolated = ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))
    monkeypatch.setattr("src.cli.settings", isolated)


@pytest.fixture(autouse=True)
def disable_live_yfinance_identity_resolution() -> Iterator[None]:
    """Keep these CLI tests deterministic, matching test_cli.py's own convention."""
    with (
        patch("src.cli.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.cli.YFinanceClient.resolve_instrument_kind", return_value=None),
    ):
        yield


def _cli_settings() -> ProjectSettings:
    """Read `src.cli`'s current (possibly monkeypatched) settings binding.

    `getattr` avoids requiring `cli.py` (a large, heavily-used entry-point
    module with no existing `__all__`) to declare a broader public export
    contract than it already has, purely for this test module's own need to
    reach the live attribute after `isolated_save_run_database` patches it.
    """
    return cast(ProjectSettings, getattr(src.cli, "settings"))  # noqa: B009


def _repository() -> SQLiteAnalysisRunRepository:
    return SQLiteAnalysisRunRepository(SQLiteDatabase(_cli_settings()))


def _mock_momentum_run(ticker: str = "BTC-USD") -> MomentumRun:
    return MomentumRun(
        metrics=MomentumMetrics(
            ticker=ticker,
            status=TrendStatus.BULLISH,
            current_price=100.0,
            short_sma_val=98.0,
            long_sma_val=95.0,
            crossover_signal=1.0,
            timestamp=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        ),
        market_data=MarketDataContext(
            provider_id="fixture-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="USD",
            observation_count=500,
        ),
    )


class _SecLabeledGrahamProvider:
    """Wraps the Graham fixture provider, relabeling facts as `sec_edgar`.

    The fixture provider natively tags its facts `fixture-synth` (matching
    the `--data-provider` value every other Graham CLI test uses); the
    workspace `AnalysisSelection` types restrict `security_provider_id` to
    `sec_edgar`/`massive` only (B1), so `--save-run` tests need the resolved
    facts' own `provider_id` to agree with the `sec_edgar` value requested
    on the command line, or the resolver's own provider-identity check
    rejects every candidate before composition.
    """

    def __init__(self) -> None:
        self._delegate = FixtureFinancialFactsProvider()

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        return tuple(replace(fact, provider_id="sec_edgar") for fact in self._delegate.fetch_facts(request))


def _graham_resolver() -> GrahamNumberInputResolver:
    return GrahamNumberInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)


def _graham_growth_resolver() -> GrahamGrowthInputResolver:
    return GrahamGrowthInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)


def _fcf_provider() -> ProductionFinancialFactsProvider:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_with_context")
def test_momentum_default_call_saves_nothing(mock_run: MagicMock) -> None:
    mock_run.return_value = _mock_momentum_run()

    result = runner.invoke(app, ["momentum", "BTC-USD"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output
    assert _repository().list(RunQuery()) == ()


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_with_context")
def test_momentum_save_run_persists_and_reports_id_on_stderr(mock_run: MagicMock) -> None:
    mock_run.return_value = _mock_momentum_run()

    concise = runner.invoke(app, ["momentum", "BTC-USD", "--save-run"])
    assert concise.exit_code == 0
    assert "Saved Analysis Run:" in concise.output
    assert "BTC-USD — Momentum" in concise.output  # stdout content is unaffected

    json_result = runner.invoke(app, ["momentum", "BTC-USD", "--save-run", "--json"])
    assert json_result.exit_code == 0
    # JSON stdout must remain byte-parseable; the run-ID line goes to stderr only,
    # which CliRunner captures separately.
    payload = json.loads(json_result.stdout)
    assert payload["ticker"] == "BTC-USD"
    assert "Saved Analysis Run:" in json_result.stderr
    assert "Saved Analysis Run:" not in json_result.stdout

    saved = _repository().list(RunQuery())
    assert len(saved) == 2
    assert {item.ticker for item in saved} == {"BTC-USD"}
    assert all(item.method_id == "sma_crossover" for item in saved)


def test_momentum_save_run_without_explicit_ticker_is_a_usage_error() -> None:
    result = runner.invoke(app, ["momentum", "--save-run"])
    assert result.exit_code == 2
    assert "requires an explicit ticker" in normalize_cli_output(result.output)


# ---------------------------------------------------------------------------
# Graham Number
# ---------------------------------------------------------------------------


def test_graham_number_save_run_persists_a_completed_run() -> None:
    with patch("src.cli.build_graham_resolver", return_value=_graham_resolver()):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--save-run"])

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository().list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1
    assert saved[0].method_id == "graham_number"


def test_graham_number_save_run_persists_a_not_applicable_etf_outcome() -> None:
    """A typed not_applicable/unavailable outcome must still be persisted, not skipped."""
    profile = fixture_known_etf_profile()
    with (
        patch("src.cli.build_graham_resolver", return_value=_graham_resolver()),
        patch("src.workspace.graham_number_execution.compose_graham_profile", return_value=profile),
    ):
        result = runner.invoke(
            app,
            ["graham-number", "FLSW", "--data-provider", "sec_edgar", "--save-run"],
        )

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository().list(RunQuery(ticker="FLSW"))
    assert len(saved) == 1
    assert saved[0].status is RunOutcome.NOT_APPLICABLE


def test_graham_number_no_cache_plus_save_run_still_saves() -> None:
    with patch("src.cli.build_graham_resolver", return_value=_graham_resolver()):
        result = runner.invoke(
            app,
            ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--no-cache", "--save-run"],
        )

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository().list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1


def test_graham_number_default_call_saves_nothing() -> None:
    with patch("src.cli.build_graham_resolver", return_value=_graham_resolver()):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output

    assert _repository().list(RunQuery(ticker="SYNTH")) == ()


def test_graham_number_save_run_storage_failure_is_visible_and_nonzero_exit() -> None:
    with (
        patch("src.cli.build_graham_resolver", return_value=_graham_resolver()),
        patch.object(SQLiteAnalysisRunRepository, "insert", side_effect=AnalysisRunConflictError("duplicate")),
    ):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--save-run"])

    assert result.exit_code != 0
    assert "Saved Analysis Run" not in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Graham Growth
# ---------------------------------------------------------------------------


def test_graham_growth_save_run_persists_with_stored_assumptions() -> None:
    with patch("src.cli.build_graham_resolver", return_value=_graham_growth_resolver()):
        result = runner.invoke(
            app,
            [
                "graham-growth",
                "SYNTH",
                "--data-provider",
                "sec_edgar",
                "--expected-growth",
                "6.0",
                "--aaa-yield",
                "4.4",
                "--save-run",
            ],
        )

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository().list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1
    full = SQLiteAnalysisRunRepository(SQLiteDatabase(_cli_settings())).get(saved[0].analysis_run_id)
    assert full is not None
    assert isinstance(full.requested_config, GrahamGrowthSelection)
    assert full.requested_config.expected_growth == 6.0
    assert full.requested_config.aaa_yield_override == 4.4


# ---------------------------------------------------------------------------
# FCF / Earnings Growth
# ---------------------------------------------------------------------------


def test_fcf_growth_save_run_persists() -> None:
    with patch("src.cli.build_sec_production_provider", return_value=_fcf_provider()):
        result = runner.invoke(app, ["fcf-growth", "ACME", "--save-run"])

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository().list(RunQuery(ticker="ACME"))
    assert len(saved) == 1
    assert saved[0].method_id == "reported_fcf_eps_cagr"


def test_fcf_growth_default_call_saves_nothing() -> None:
    with patch("src.cli.build_sec_production_provider", return_value=_fcf_provider()):
        result = runner.invoke(app, ["fcf-growth", "ACME"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output

    assert _repository().list(RunQuery(ticker="ACME")) == ()
