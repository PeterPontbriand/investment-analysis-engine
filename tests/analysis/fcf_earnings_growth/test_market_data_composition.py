"""The sites that build FCF-Growth's analyzer each compose the market data once per run, and none reaches a service."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from typer.testing import CliRunner

import investment_analysis_engine.cli
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.instrument_profile import InstrumentKind
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureMarketCapProvider,
    FixtureSplitHistoryProvider,
)
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from investment_analysis_engine.strategies.fcf_growth import cli as fcf_cli
from investment_analysis_engine.strategies.fcf_growth.analyzer import MarketCapDependencies
from investment_analysis_engine.strategies.fcf_growth.execution import FCFGrowthCapture
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from tests._fcf_market_data import CLOCK, fcf_result


class Composition:
    """The composition the command and refresh built, as the patched collaborators recorded it."""

    def __init__(self) -> None:
        """Build the fixture provider and historical client, with nothing recorded yet."""
        self.provider = ProductionFinancialFactsProvider(
            sec_edgar=FixtureMarketCapProvider(CLOCK, with_data=True),
            yfinance=FixtureMarketCapProvider(CLOCK, with_data=True),
        )
        self.historical = FixtureSplitHistoryProvider(CLOCK, with_data=True)
        self.cache_calls: list[bool] = []
        self.historical_calls: list[bool] = []
        self.yahoo_clients: list[object] = []
        self.executions: list[dict[str, Any]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace the collaborators of the CLI module with the recording fixtures."""
        composition = self

        @contextmanager
        def financial_cache(*, use_cache: bool, clock: Any) -> Iterator[None]:  # noqa: ARG001
            composition.cache_calls.append(use_cache)
            yield None

        @contextmanager
        def historical_client(
            provider: object,
            *,
            use_cache: bool,
            clock: Any,  # noqa: ARG001
        ) -> Iterator[FixtureSplitHistoryProvider]:
            composition.yahoo_clients.append(provider)
            composition.historical_calls.append(use_cache)
            yield composition.historical

        def execute(*args: Any, **kwargs: Any) -> FCFGrowthCapture:
            composition.executions.append({"args": args, **kwargs})
            profile = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
            return FCFGrowthCapture(result=fcf_result(), profile=profile)

        monkeypatch.setattr(fcf_cli, "_production_financial_cache", financial_cache)
        monkeypatch.setattr(fcf_cli, "_production_historical_client", historical_client)
        monkeypatch.setattr(fcf_cli, "build_sec_production_provider", lambda: composition.provider)
        monkeypatch.setattr(fcf_cli, "YFinanceClient", object)
        monkeypatch.setattr(fcf_cli, "execute_fcf_growth", execute)

    def market_data(self) -> MarketCapDependencies:
        """Return the one set of market-data dependencies the single execution received."""
        assert len(self.executions) == 1
        market_data = self.executions[0]["market_data"]
        assert isinstance(market_data, MarketCapDependencies)
        return market_data


@pytest.fixture
def composition(monkeypatch: pytest.MonkeyPatch) -> Composition:
    built = Composition()
    built.install(monkeypatch)
    return built


def _assert_composed(composition: Composition, *, use_cache: bool) -> None:
    market_data = composition.market_data()
    assert market_data.listing is composition.provider
    assert market_data.resolver.provider is composition.provider
    assert market_data.split_history is composition.historical
    assert composition.historical_calls == [use_cache]
    assert composition.cache_calls == [use_cache]
    assert len(composition.yahoo_clients) == 1
    assert composition.executions[0]["use_cache"] is use_cache


@pytest.mark.parametrize("use_cache", [True, False])
def test_refresh_composes_the_market_data_once(composition: Composition, use_cache: bool) -> None:
    selection = FCFGrowthSelection(use_cache=use_cache)

    fcf_cli.refresh("ACME", selection, profile_cache=None)

    _assert_composed(composition, use_cache=use_cache)
    assert isinstance(composition.executions[0]["args"][0], ProductionAnnualGrowthSeriesResolver)


@pytest.mark.parametrize(("arguments", "use_cache"), [([], True), (["--no-cache"], False)])
def test_the_command_composes_the_market_data_once(
    composition: Composition, arguments: list[str], use_cache: bool
) -> None:
    result = CliRunner().invoke(investment_analysis_engine.cli.app, ["fcf-growth", "ACME", *arguments])

    assert result.exit_code == 0, result.output
    _assert_composed(composition, use_cache=use_cache)
    assert "FCF yield: +10.00%" in result.output
