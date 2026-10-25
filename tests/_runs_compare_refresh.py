"""Run a real offline refresh over the four strategies, for the ``runs compare`` tests.

Three tickers cover every outcome the table shows. ``SYNTH`` completes for all four strategies. ``MISSING`` has a
Momentum history of four bars against a five-bar long average, a Graham Number whose inputs are missing, no Graham
Growth entry at all, and an FCF-Growth run with no annual facts. ``ERROR`` has a Momentum provider failure,
a Graham Number provider failure, a completed Graham Growth value and a completed FCF-Growth run on the per-share
basis. Nothing leaves the process: Momentum's history, the Graham resolvers and the FCF provider are fixtures,
and the provider check is off.
"""

import json
import re
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pandas as pd
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.market_data import HistoricalMarketData, MarketDataContext
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthPolicy
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection, FCFPolicySnapshot
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
)
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.repositories.watchlists import SQLiteWatchlistRepository
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from tests._sec_labeled_graham import sec_labeled_growth_resolver, sec_labeled_number_resolver
from tests._wiring import alias_for

runner = CliRunner()
_REAL_RUN_ANALYSIS = MomentumAnalyzer.run_analysis
"""The analyzer's own method, kept before a test patches it on the class."""
MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=3)
LONG_AVERAGE = MomentumSelection(short_window=2, long_window=5, rsi_period=3)
GROWTH = GrahamGrowthSelection(expected_growth=6.0, aaa_yield_override=4.4)
PER_SHARE = FCFGrowthSelection(
    policy=FCFPolicySnapshot.model_validate(
        FCFEarningsGrowthPolicy(
            historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE,
            classification_basis=FCFClassificationBasis.FCF_PER_SHARE,
            forward_policy=ForwardPolicy.DISPLAY_ONLY,
        )
    )
)
ENTRIES: list[tuple[str, AnalysisSelection]] = [
    ("SYNTH", MOMENTUM),
    ("SYNTH", GrahamNumberSelection()),
    ("SYNTH", GROWTH),
    ("SYNTH", FCFGrowthSelection()),
    ("MISSING", LONG_AVERAGE),
    ("MISSING", GrahamNumberSelection()),
    ("MISSING", FCFGrowthSelection()),
    ("ERROR", MOMENTUM),
    ("ERROR", GrahamNumberSelection()),
    ("ERROR", GROWTH),
    ("ERROR", PER_SHARE),
]


def momentum_run_for(**kwargs: Any) -> MomentumRun:
    """Run Momentum's real analyzer over a fixture history: a rising series, a short one, or a provider failure."""
    ticker = str(kwargs["ticker"])
    closes = [1.0, 2.0, 3.0, 4.0] if ticker == "MISSING" else [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    provider = MagicMock()
    provider.provider_id = "fixture"
    if ticker == "ERROR":
        provider.fetch_historical_data.side_effect = DataFetchError(
            "library detail", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance"
        )
    else:
        frame = pd.DataFrame({"Close": closes}, index=pd.date_range("2026-01-01", periods=len(closes), tz=UTC))
        provider.fetch_historical_data.return_value = HistoricalMarketData(
            frame, MarketDataContext(provider_id="fixture", observation_interval="1d", currency="USD")
        )
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    config = kwargs["config"]
    assert isinstance(config, MomentumConfig)
    return _REAL_RUN_ANALYSIS(analyzer, ticker, config, kwargs["context"])


def _fcf_provider() -> ProductionFinancialFactsProvider:
    from dataclasses import replace  # noqa: PLC0415

    facts = tuple(
        replace(
            fact,
            subject_id=ticker,
            provider_id=SEC_PROVIDER_ID,
            provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}",
        )
        for ticker in ("SYNTH", "ERROR")
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


def _resolver_for(kind: str) -> Callable[..., object]:
    """Return the Graham resolver factory for a strategy; ``ERROR`` and ``MISSING`` subjects use the fixtures' own."""
    build = sec_labeled_number_resolver if kind == "number" else sec_labeled_growth_resolver
    return lambda **_kwargs: build()


def seed(settings: ProjectSettings, name: str, entries: list[tuple[str, AnalysisSelection]]) -> None:
    """Create a watchlist and add the entries directly through the repository."""
    created = runner.invoke(app, ["watchlist", "create", name])
    assert created.exit_code == 0, created.output
    database = SQLiteDatabase(settings)
    try:
        SQLiteWatchlistRepository(database, alias_for=alias_for).add_entries(name, entries)
    finally:
        database.close()


def refresh_document(
    settings: ProjectSettings,
    name: str = "Core",
    entries: list[tuple[str, AnalysisSelection]] | None = None,
    *extra: str,
) -> dict[str, Any]:
    """Seed a watchlist with the entries, run a real refresh offline and return its ``--json`` summary."""
    seed(settings, name, ENTRIES if entries is None else entries)
    with (
        patch(
            "investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis",
            side_effect=momentum_run_for,
        ),
        patch(
            "investment_analysis_engine.strategies.graham_number.cli.build_graham_resolver",
            side_effect=_resolver_for("number"),
        ),
        patch(
            "investment_analysis_engine.strategies.graham_growth.cli.build_graham_resolver",
            side_effect=_resolver_for("growth"),
        ),
        patch(
            "investment_analysis_engine.strategies.fcf_growth.cli.build_sec_production_provider",
            return_value=_fcf_provider(),
        ),
    ):
        result = runner.invoke(app, ["refresh", name, "--workers", "1", "--json", "--no-provider-check", *extra])
    document: dict[str, Any] = json.loads(result.stdout)
    return document


def refresh(
    settings: ProjectSettings, name: str = "Core", entries: list[tuple[str, AnalysisSelection]] | None = None
) -> UUID:
    """Seed a watchlist, refresh it offline and return the refresh ID."""
    return UUID(refresh_document(settings, name, entries)["refresh_id"])


def alter_row(
    settings: ProjectSettings, run_id: str, columns: dict[str, object], envelope: Callable[[dict[str, Any]], None]
) -> None:
    """Change a stored run's indexed columns and its envelope together, keeping the row consistent."""
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        ((text,),) = connection.execute(
            "SELECT envelope_json FROM analysis_runs WHERE analysis_run_id = ?", (run_id,)
        ).fetchall()
        document = json.loads(text)
        envelope(document)
        updated = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        sets = "".join(f"{column} = ?, " for column in columns)
        connection.execute(
            f"UPDATE analysis_runs SET {sets}envelope_json = ? WHERE analysis_run_id = ?",  # noqa: S608
            (*columns.values(), updated, run_id),
        )
        connection.commit()


def run_ids(settings: ProjectSettings, refresh_id: UUID) -> dict[tuple[str, str], str]:
    """Return the stored run ID of each (ticker, method id) of a refresh."""
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute(
            "SELECT ticker, method_id, analysis_run_id FROM analysis_runs WHERE refresh_id = ?", (str(refresh_id),)
        ).fetchall()
    return {(ticker, method): run_id for ticker, method, run_id in rows}


UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NOW = datetime(2026, 1, 1, tzinfo=UTC)
