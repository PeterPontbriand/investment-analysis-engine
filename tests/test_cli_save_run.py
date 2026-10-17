"""Direct-command `--save-run` (F3) tests: opt-in Analysis Run persistence.

Isolation note: the `settings` bindings of `investment_analysis_engine.cli_run_support` and Momentum's `cli` module are
deliberately NOT covered by the shared `isolated_cli_database` fixture (see `tests/_cli_helpers.py`'s docstring) because
that name is shared for configuration well beyond database access, and other already-accepted tests rely on mutating the
real shared settings singleton directly. This module isolates them locally instead, preserving every other field from
the real settings (built the same way `investment_analysis_engine.cli_database`'s own maintenance commands already do:
`ProjectSettings(**(settings.model_dump() | {"database_url": ...}))`) so only the run-storage database target changes.
"""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config import settings as real_settings
from investment_analysis_engine.core.constants import TrendStatus
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.market_data import MarketDataContext
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_known_etf_profile
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.momentum.analyzer import MomentumMetrics, MomentumRun
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.repositories.analysis_runs import (
    AnalysisRunConflictError,
    SQLiteAnalysisRunRepository,
)
from investment_analysis_engine.workspace.runs import RunQuery
from scripts.repository_root import REPOSITORY_ROOT
from tests._cli_helpers import carry_profile, isolated_cli_database, normalize_cli_output  # noqa: F401
from tests._sec_labeled_graham import sec_labeled_growth_resolver, sec_labeled_number_resolver

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_save_run_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProjectSettings:
    """Point the run helpers' and Momentum's `settings` run-storage database at a disposable, migrated file.

    Every other field (SEC identity, etc.) is preserved from the real settings,
    so this module's tests do not disturb unrelated already-accepted behavior.
    """
    url = f"sqlite:///{(tmp_path / 'save_run.sqlite3').as_posix()}"
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    isolated = ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))
    monkeypatch.setattr("investment_analysis_engine.cli_run_support.settings", isolated)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", isolated)
    return isolated


@pytest.fixture(autouse=True)
def disable_live_yfinance_identity_resolution() -> Iterator[None]:
    """Keep these CLI tests deterministic, matching test_cli.py's own convention."""
    with (
        patch(
            "investment_analysis_engine.data.yfinance.client.YFinanceClient.resolve_security_identity",
            return_value=None,
        ),
        patch(
            "investment_analysis_engine.data.yfinance.client.YFinanceClient.resolve_instrument_kind", return_value=None
        ),
    ):
        yield


def _repository(settings: ProjectSettings) -> SQLiteAnalysisRunRepository:
    return SQLiteAnalysisRunRepository(SQLiteDatabase(settings))


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


def _fcf_provider() -> ProductionFinancialFactsProvider:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


@patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
def test_momentum_default_call_saves_nothing(mock_run: MagicMock, isolated_save_run_database: ProjectSettings) -> None:
    mock_run.return_value = _mock_momentum_run()
    carry_profile(mock_run)

    result = runner.invoke(app, ["momentum", "BTC-USD"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output
    assert _repository(isolated_save_run_database).list(RunQuery()) == ()


@patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
def test_momentum_save_run_persists_and_reports_id_on_stderr(
    mock_run: MagicMock, isolated_save_run_database: ProjectSettings
) -> None:
    mock_run.return_value = _mock_momentum_run()
    carry_profile(mock_run)

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

    saved = _repository(isolated_save_run_database).list(RunQuery())
    assert len(saved) == 2
    assert {item.ticker for item in saved} == {"BTC-USD"}
    assert all(item.method_id == "sma_crossover" for item in saved)


@patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
def test_momentum_save_run_persists_as_of_and_no_cache_on_the_selection(
    mock_run: MagicMock, isolated_save_run_database: ProjectSettings
) -> None:
    mock_run.return_value = _mock_momentum_run()
    carry_profile(mock_run)

    result = runner.invoke(app, ["momentum", "BTC-USD", "--save-run", "--as-of", "2026-08-01", "--no-cache"])

    assert result.exit_code == 0, result.output
    context = mock_run.call_args.kwargs["context"]
    assert context.as_of == datetime(2026, 8, 1, 23, 59, 59, 999999, tzinfo=UTC)
    assert context.use_cache is False
    (summary,) = _repository(isolated_save_run_database).list(RunQuery())
    run = _repository(isolated_save_run_database).get(summary.analysis_run_id)
    assert run is not None
    selection = run.requested_config
    assert isinstance(selection, MomentumSelection)
    assert selection.as_of == context.as_of
    assert selection.use_cache is False


# ---------------------------------------------------------------------------
# Graham Number
# ---------------------------------------------------------------------------


def test_graham_number_save_run_persists_a_completed_run(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
        return_value=sec_labeled_number_resolver(),
    ):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--save-run"])

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository(isolated_save_run_database).list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1
    assert saved[0].method_id == "graham_number"


def test_graham_number_save_run_persists_a_not_applicable_etf_outcome(
    isolated_save_run_database: ProjectSettings,
) -> None:
    """A typed not_applicable/unavailable outcome must still be persisted, not skipped."""
    profile = fixture_known_etf_profile()
    with (
        patch(
            "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
            return_value=sec_labeled_number_resolver(),
        ),
        patch(
            "investment_analysis_engine.strategies.graham_number.execution.compose_graham_profile", return_value=profile
        ),
    ):
        result = runner.invoke(
            app,
            ["graham-number", "FLSW", "--data-provider", "sec_edgar", "--save-run"],
        )

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository(isolated_save_run_database).list(RunQuery(ticker="FLSW"))
    assert len(saved) == 1
    assert saved[0].status is RunOutcome.NOT_APPLICABLE


def test_graham_number_no_cache_plus_save_run_still_saves(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
        return_value=sec_labeled_number_resolver(),
    ):
        result = runner.invoke(
            app,
            ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--no-cache", "--save-run"],
        )

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository(isolated_save_run_database).list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1


def test_graham_number_default_call_saves_nothing(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
        return_value=sec_labeled_number_resolver(),
    ):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output

    assert _repository(isolated_save_run_database).list(RunQuery(ticker="SYNTH")) == ()


def test_graham_number_save_run_storage_failure_is_visible_and_nonzero_exit() -> None:
    with (
        patch(
            "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
            return_value=sec_labeled_number_resolver(),
        ),
        patch.object(SQLiteAnalysisRunRepository, "insert", side_effect=AnalysisRunConflictError("duplicate")),
    ):
        result = runner.invoke(app, ["graham-number", "SYNTH", "--data-provider", "sec_edgar", "--save-run"])

    assert result.exit_code != 0
    assert "Saved Analysis Run" not in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Graham Growth
# ---------------------------------------------------------------------------


def test_graham_growth_save_run_persists_with_stored_assumptions(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.graham_growth.cli.build_graham_resolver",
        return_value=sec_labeled_growth_resolver(),
    ):
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

    saved = _repository(isolated_save_run_database).list(RunQuery(ticker="SYNTH"))
    assert len(saved) == 1
    full = SQLiteAnalysisRunRepository(SQLiteDatabase(isolated_save_run_database)).get(saved[0].analysis_run_id)
    assert full is not None
    assert isinstance(full.requested_config, GrahamGrowthSelection)
    assert full.requested_config.expected_growth == 6.0
    assert full.requested_config.aaa_yield_override == 4.4


# ---------------------------------------------------------------------------
# FCF / Earnings Growth
# ---------------------------------------------------------------------------


def test_fcf_growth_save_run_persists(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.fcf_growth.cli.build_sec_production_provider",
        return_value=_fcf_provider(),
    ):
        result = runner.invoke(app, ["fcf-growth", "ACME", "--save-run"])

    assert result.exit_code == 0
    assert "Saved Analysis Run:" in result.output

    saved = _repository(isolated_save_run_database).list(RunQuery(ticker="ACME"))
    assert len(saved) == 1
    assert saved[0].method_id == "reported_fcf_eps_cagr"


def test_fcf_growth_default_call_saves_nothing(isolated_save_run_database: ProjectSettings) -> None:
    with patch(
        "investment_analysis_engine.strategies.fcf_growth.cli.build_sec_production_provider",
        return_value=_fcf_provider(),
    ):
        result = runner.invoke(app, ["fcf-growth", "ACME"])

    assert result.exit_code == 0
    assert "Saved Analysis Run" not in result.output

    assert _repository(isolated_save_run_database).list(RunQuery(ticker="ACME")) == ()


# ---------------------------------------------------------------------------
# Interruption
# ---------------------------------------------------------------------------


@patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
def test_interrupt_during_analysis_stores_no_run(
    mock_run: MagicMock, isolated_save_run_database: ProjectSettings
) -> None:
    """Ctrl-C before the run is captured leaves nothing stored and reports no saved run.

    The exit status of an interrupt is Typer's (130), not the application's, so it is not asserted.
    """
    mock_run.side_effect = KeyboardInterrupt

    result = runner.invoke(app, ["momentum", "BTC-USD", "--save-run"])

    assert "Saved Analysis Run" not in result.output
    assert _repository(isolated_save_run_database).list(RunQuery()) == ()


@patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
def test_interrupt_while_storing_leaves_no_partial_run(
    mock_run: MagicMock, isolated_save_run_database: ProjectSettings
) -> None:
    """Ctrl-C inside the insert transaction rolls the transaction back; no row, no saved-run line."""
    mock_run.return_value = _mock_momentum_run()
    carry_profile(mock_run)

    with patch("investment_analysis_engine.workspace.repositories.analysis_runs._row", side_effect=KeyboardInterrupt):
        result = runner.invoke(app, ["momentum", "BTC-USD", "--save-run"])

    assert "Saved Analysis Run" not in result.output
    assert _repository(isolated_save_run_database).list(RunQuery()) == ()
