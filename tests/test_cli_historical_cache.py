"""Verify production Momentum historical-cache composition without network access."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
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


@pytest.fixture
def configured_settings(tmp_path: Path) -> Iterator[ProjectSettings]:
    settings = ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
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
        second = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    fetch.assert_called_once()
    left, right = json.loads(first.output), json.loads(second.output)
    left.pop("analysis_timestamp")
    right.pop("analysis_timestamp")
    assert left == right
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
        with _production_historical_client(provider) as client:
            client.fetch_historical_data("ACME", "2025-01-01")
        clock.now.return_value = NOW + timedelta(seconds=age)
        with _production_historical_client(provider) as client:
            client.fetch_historical_data("ACME", "2025-01-01")
    assert fetch.call_count == calls


def test_quote_delegation_survives_closed_storage(configured_settings: ProjectSettings) -> None:
    assert configured_settings.database_url.startswith("sqlite:")
    provider = YFinanceClient()
    with _production_historical_client(provider) as client:
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
        _production_historical_client(provider) as client,
    ):
        client.fetch_data("ACME", "2025-01-01")
    with pytest.raises(RuntimeError, match="closed"), database.read():
        pass


def test_custom_analyzer_client_remains_direct(history: HistoricalMarketData) -> None:
    custom = FixtureDataClient()
    with (
        patch(
            "src.cli_support.SQLiteDatabase", side_effect=AssertionError("Custom clients do not use production storage")
        ),
        patch.object(custom, "fetch_data_with_context", return_value=history),
    ):
        analyzer = MomentumAnalyzer(default_ticker="ACME", data_client=custom)
        run = analyzer.run_with_context(MomentumConfig(short_window=2, long_window=3, rsi_period=3))
    assert analyzer.data_client is custom
    assert run.metrics.current_price > 0
