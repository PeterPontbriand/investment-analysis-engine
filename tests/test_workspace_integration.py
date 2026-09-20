"""H/I1-I2 (acceptance): one multi-command offline scenario chaining the whole local research workspace.

Every individual command and dispatch branch already has its own focused
unit/CLI test (F1-F3, G1-G3, I1, I2). This file's job is different: it
proves a full workflow — create (seeded), add entries, show, refresh, then
browse — works end to end in one coherent sequence, entirely offline, and
that a run produced by `refresh` (not a direct `--save-run` command) replays
correctly through `runs show` in every presentation mode. Nothing here makes
a network call; all provider/resolver composition is mocked exactly as the
existing focused test suites already do.

Amendment A1's I2 checkpoint (docs/project/milestones/v0.2/step-3.4/
STEP_3_4_CONTRACT_AND_SLICE_PLAN.md, section 12) restored watchlist entry
creation under new command names (`create --analysis`, `add-selection`).
This test drives every entry through those real CLI commands rather than
seeding the repository directly, so the scenario exercises the same surface
a user actually types.
"""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.momentum.momentum_analyzer import MomentumMetrics, MomentumRun
from src.cli import app
from src.core.constants import TrendStatus
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.market_data import MarketDataContext
from src.evaluation.fixtures.graham import NOW, FixtureFinancialFactsProvider
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401

runner = CliRunner()


class _SecLabeledGrahamProvider:
    """Wraps the Graham fixture provider, relabeling facts as `sec_edgar` (matches B1's restriction)."""

    def __init__(self) -> None:
        self._delegate = FixtureFinancialFactsProvider()

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        return tuple(replace(fact, provider_id="sec_edgar") for fact in self._delegate.fetch_facts(request))


def _resolver_side_effect(*, resolver_type: type, data_provider: str | None = None, cache: object = None) -> object:
    del data_provider, cache
    if resolver_type is GrahamNumberInputResolver:
        return GrahamNumberInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)
    return GrahamGrowthInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)


def _mock_momentum_run(ticker: str) -> MomentumRun:
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


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_with_context")
def test_full_offline_workflow_create_seed_refresh_and_browse(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(str(kwargs["ticker"]))

    # 1. Create a watchlist seeded with one Momentum entry for one ticker.
    result = runner.invoke(
        app,
        [
            "watchlist",
            "create",
            "Core Holdings",
            "--analysis",
            "momentum",
            "--short-window",
            "2",
            "--long-window",
            "3",
            "SYNTH",
        ],
    )
    assert result.exit_code == 0, result.output

    # 2. Add two more entries for the same ticker: Graham Number, and Graham
    #    Growth Value with explicit assumptions — the fan-out `add-selection`
    #    command, one method at a time.
    result = runner.invoke(app, ["watchlist", "add-selection", "Core Holdings", "SYNTH", "--analysis", "graham-number"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "watchlist",
            "add-selection",
            "Core Holdings",
            "SYNTH",
            "--analysis",
            "graham-growth",
            "--expected-growth",
            "6.0",
            "--aaa-yield",
            "4.4",
        ],
    )
    assert result.exit_code == 0, result.output

    # 3. Show confirms exactly the three seeded entries.
    result = runner.invoke(app, ["watchlist", "show", "Core Holdings"])
    assert result.exit_code == 0, result.output
    shown = normalize_cli_output(result.output)
    assert "sma_crossover" in shown
    assert "graham_number" in shown
    assert "graham_growth_value" in shown
    assert "Entries (3)" in shown

    # 4. Refresh the whole watchlist in one command.
    with patch("src.cli_workspace.build_graham_resolver", side_effect=_resolver_side_effect):
        result = runner.invoke(app, ["refresh", "Core Holdings", "--workers", "1"])
    assert result.exit_code == 0, result.output
    refreshed = normalize_cli_output(result.output)
    assert "completed=3" in refreshed

    # 5. Browse the saved runs for this ticker.
    result = runner.invoke(app, ["runs", "list", "--ticker", "SYNTH", "--json"])
    assert result.exit_code == 0, result.output
    summaries = json.loads(result.output)
    assert len(summaries) == 3
    method_ids = {item["method_id"] for item in summaries}
    assert method_ids == {"sma_crossover", "graham_number", "graham_growth_value"}
    assert {item["status"] for item in summaries} == {"completed"}
    refresh_ids = {item["refresh_id"] for item in summaries}
    assert len(refresh_ids) == 1  # all three came from the same refresh batch

    # 6. Replay each refresh-produced run through every presentation mode — no
    #    recalculation, no live provider/resolver, exactly as E1-E4 already
    #    prove for directly-saved runs. This is the one place that specifically
    #    proves it also holds for a run that refresh (not --save-run) produced.
    for summary in summaries:
        run_id = summary["analysis_run_id"]
        concise = runner.invoke(app, ["runs", "show", run_id])
        assert concise.exit_code == 0, concise.output
        assert "SYNTH" in concise.output

        details = runner.invoke(app, ["runs", "show", run_id, "--details"])
        assert details.exit_code == 0, details.output

        diagnostics = runner.invoke(app, ["runs", "show", run_id, "--diagnostics"])
        assert diagnostics.exit_code == 0, diagnostics.output

        as_json = runner.invoke(app, ["runs", "show", run_id, "--json"])
        assert as_json.exit_code == 0, as_json.output
        payload = json.loads(as_json.output)
        assert payload["ticker"] == "SYNTH"
