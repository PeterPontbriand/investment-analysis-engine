"""Verify production Momentum historical-cache composition without network access."""

import json
from collections.abc import Iterator
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.cli import app
from src.cli_support import _production_historical_client
from src.config import ProjectSettings
from src.data.base_client import DataFetchError
from src.data.instrument_profile import InstrumentProfile
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.repositories import SQLiteDatabase, SQLiteMarketDataRepository
from src.data.yfinance import YFinanceClient
from src.evaluation.fixtures.market_data import FixtureDataClient, momentum_success_frame

NOW = datetime(2026, 9, 6, tzinfo=UTC)


@pytest.fixture(params=["ready", "missing"])
def configured_settings(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[ProjectSettings]:
    settings = ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    if request.param == "ready":
        command.upgrade(config, "head")
    with patch("src.cli_support.settings", settings):
        yield settings


@pytest.fixture
def history() -> HistoricalMarketData:
    frame = momentum_success_frame()
    return HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="yfinance",
            observation_interval="1d",
            price_adjustment="adjusted",
            data_as_of=frame.index[-1].date(),
            observation_count=len(frame),
            currency="USD",
        ),
    )


def test_momentum_cli_reuses_history_and_preserves_profile_provider(
    configured_settings: ProjectSettings,
    history: HistoricalMarketData,
) -> None:
    assert configured_settings.historical_cache_ttl_seconds == 3600
    provider = YFinanceClient()
    databases: list[SQLiteDatabase] = []

    def database(settings: ProjectSettings) -> SQLiteDatabase:
        instance = SQLiteDatabase(settings)
        databases.append(instance)
        return instance

    profile = InstrumentProfile(ticker="ACME", identity=None, kind_evidence=None, diagnostics=())
    args = ["momentum", "ACME", "--short-window", "2", "--long-window", "3", "--rsi-period", "3", "--json"]
    with (
        patch("src.cli.YFinanceClient", return_value=provider),
        patch.object(
            provider, "fetch_historical_data", side_effect=[history, AssertionError("Unexpected refetch")]
        ) as fetch,
        patch.object(provider, "fetch_current_price", side_effect=AssertionError("Historical analysis needs no quote")),
        patch("src.cli.compose_instrument_profile", return_value=profile) as compose,
        patch("src.cli_support.SQLiteDatabase", side_effect=database),
    ):
        first = CliRunner().invoke(app, args)
        with patch(
            "src.data.repositories.readiness.upgrade_fresh_database", side_effect=AssertionError("Unexpected migration")
        ):
            second = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    fetch.assert_called_once()
    left, right = json.loads(first.output), json.loads(second.output)
    left.pop("analysis_timestamp")
    right.pop("analysis_timestamp")
    provider_resolution = left.pop("data_resolution")
    cache_resolution = right.pop("data_resolution")
    assert provider_resolution["source_kind"] == "provider"
    assert cache_resolution["source_kind"] == "cache"
    assert provider_resolution["retrieved_at"] == cache_resolution["retrieved_at"]
    provider_trace = left.pop("diagnostics")
    cache_trace = right.pop("diagnostics")
    assert any(item.get("stage") == "provider" for item in provider_trace)
    assert any(item.get("stage") == "cache" for item in cache_trace)
    assert left == right
    assert not first.stderr
    assert not second.stderr
    assert len(databases) == 2
    for instance in databases:
        with pytest.raises(RuntimeError, match="closed"), instance.read():
            pass
    for call in compose.call_args_list:
        assert call.kwargs["identity_candidates"][0].provider is provider
        assert call.kwargs["kind_candidate"].provider is provider


@pytest.mark.parametrize(
    ("ttl", "age", "calls"), [(3600, 3600, 1), (3600, 3601, 2), (None, 9000, 1), (0, 0, 1), (0, 1, 2)]
)
def test_settings_control_reuse_age(
    configured_settings: ProjectSettings,
    history: HistoricalMarketData,
    ttl: float | None,
    age: int,
    calls: int,
) -> None:
    configured_settings.historical_cache_ttl_seconds = ttl
    provider = YFinanceClient()
    with (
        patch("src.data.cached_client.datetime", wraps=datetime) as clock,
        patch(
            "src.cli_support.SQLiteMarketDataRepository",
            side_effect=lambda db: SQLiteMarketDataRepository(db, clock=lambda: NOW),
        ),
        patch.object(provider, "fetch_historical_data", return_value=history) as fetch,
    ):
        clock.now.return_value = NOW
        with _production_historical_client(provider, use_cache=True, clock=clock.now) as client:
            client.fetch_historical_data("ACME", "2025-01-01", use_cache=True)
        clock.now.return_value = NOW + timedelta(seconds=age)
        with _production_historical_client(provider, use_cache=True, clock=clock.now) as client:
            client.fetch_historical_data("ACME", "2025-01-01", use_cache=True)
    assert fetch.call_count == calls


def test_quote_delegation_survives_closed_storage(configured_settings: ProjectSettings) -> None:
    assert configured_settings.database_url.startswith("sqlite:")
    provider = YFinanceClient()
    with _production_historical_client(provider, use_cache=True, clock=lambda: NOW) as client:
        pass
    with patch.object(provider, "fetch_current_price", return_value=87.5) as quote:
        assert client.fetch_current_price("ACME") == 87.5
    quote.assert_called_once_with("ACME")


def test_storage_closes_after_provider_error(configured_settings: ProjectSettings) -> None:
    database = SQLiteDatabase(configured_settings)
    provider = YFinanceClient()
    with (
        patch("src.cli_support.SQLiteDatabase", return_value=database),
        patch.object(provider, "fetch_historical_data", side_effect=DataFetchError("offline")),
        pytest.raises(DataFetchError, match="offline"),
        _production_historical_client(provider, use_cache=True, clock=lambda: NOW) as client,
    ):
        client.fetch_data("ACME", "2025-01-01")
    with pytest.raises(RuntimeError, match="closed"), database.read():
        pass


def test_disabled_cache_never_checks_readiness(tmp_path: Path) -> None:
    """``use_cache=False`` must never call ``ensure_database_ready``, mirroring the financial cache."""
    settings = ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'absent.sqlite3').as_posix()}")
    provider = YFinanceClient()
    with (
        patch("src.cli_support.settings", settings),
        patch("src.cli_support.ensure_database_ready", side_effect=AssertionError("must not check readiness")),
        _production_historical_client(provider, use_cache=False, clock=lambda: NOW),
    ):
        pass
    assert not Path(settings.database_url.removeprefix("sqlite:///")).exists()


def test_custom_analyzer_client_remains_direct(history: HistoricalMarketData) -> None:
    custom = FixtureDataClient()
    with (
        patch(
            "src.cli_support.SQLiteDatabase", side_effect=AssertionError("Custom clients do not use production storage")
        ),
        patch.object(custom, "fetch_data_with_context", return_value=history) as fetch,
    ):
        analyzer = MomentumAnalyzer(market_data_provider=custom, start_date="2026-01-01")
        context = AnalysisContext(as_of=None, executed_at=datetime.now(UTC), use_cache=True)
        run = analyzer.run_analysis("ACME", MomentumConfig(short_window=2, long_window=3, rsi_period=3), context)
    fetch.assert_called_once_with("ACME", "2026-01-01", None, use_cache=True)
    assert run.metrics.current_price > 0


def _momentum_options_run(
    tmp_path: Path, extra_args: list[str], history: HistoricalMarketData, *, guard_readiness: bool
) -> tuple[Path, dict[str, Any], MagicMock]:
    """Invoke the momentum command against a not-yet-created database and a fixture provider."""
    path = tmp_path / "absent.sqlite3"
    provider = YFinanceClient()
    profile = InstrumentProfile(ticker="ACME", identity=None, kind_evidence=None, diagnostics=())
    with ExitStack() as stack:
        stack.enter_context(
            patch("src.cli_support.settings", ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
        )
        stack.enter_context(patch("src.cli.YFinanceClient", return_value=provider))
        fetch = stack.enter_context(patch.object(provider, "fetch_historical_data", return_value=history))
        stack.enter_context(patch("src.cli.compose_instrument_profile", return_value=profile))
        if guard_readiness:
            stack.enter_context(
                patch(
                    "src.cli_support.ensure_database_ready", side_effect=AssertionError("Database must not be migrated")
                )
            )
        result = CliRunner().invoke(
            app,
            ["momentum", "ACME", "--short-window", "2", "--long-window", "3", "--rsi-period", "3", "--json"]
            + extra_args,
        )
    assert result.exit_code == 0, result.output
    return path, json.loads(result.output), fetch


def test_momentum_no_cache_does_not_create_the_database(tmp_path: Path, history: HistoricalMarketData) -> None:
    path, _payload, fetch = _momentum_options_run(tmp_path, ["--no-cache"], history, guard_readiness=True)
    assert not path.exists()
    assert not Path(str(path) + ".readiness.lock").exists()
    assert fetch.call_args.kwargs["use_cache"] is False


def test_momentum_without_no_cache_still_creates_the_database(tmp_path: Path, history: HistoricalMarketData) -> None:
    path, _payload, fetch = _momentum_options_run(tmp_path, [], history, guard_readiness=False)
    assert path.exists()
    assert fetch.call_args.kwargs["use_cache"] is True


def test_momentum_as_of_truncates_the_series_at_the_requested_boundary(
    tmp_path: Path, history: HistoricalMarketData
) -> None:
    latest = history.frame.index[-1].date()
    boundary = history.frame.index[2].date()
    assert boundary < latest
    _path, payload, _fetch = _momentum_options_run(
        tmp_path, ["--no-cache", "--as-of", boundary.isoformat()], history, guard_readiness=True
    )
    assert payload["as_of"] == boundary.isoformat()
