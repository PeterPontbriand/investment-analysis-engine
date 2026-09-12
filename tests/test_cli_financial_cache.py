"""Verify CLI financial-cache ownership, durable reuse, and truthful provenance."""

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.cli import _build_graham_resolver, app
from src.cli_support import _production_financial_cache
from src.config import ProjectSettings
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.financial.resolver import InputResolver
from src.data.instrument_profile import InstrumentProfile
from src.data.repositories import SQLiteDatabase
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import NOW, PROVIDER_ID, FixtureFinancialFactsProvider


class GrahamProvider:
    """Adapt synthetic facts to the selected provider identity without network calls."""

    def __init__(self) -> None:
        """Track fact calls and allow unexpected refetches to fail loudly."""
        self.calls = 0
        self.fail = False

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Return original fixture provenance with the requested provider identity."""
        self.calls += 1
        if self.fail:
            raise AssertionError("Unexpected provider access")
        facts = FixtureFinancialFactsProvider().fetch_facts(replace(request, provider_id=PROVIDER_ID))
        return tuple(replace(fact, provider_id=request.provider_id) for fact in facts)


@pytest.fixture(params=["ready", "missing"])
def configured_database(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Path]:
    path = tmp_path / "financial.sqlite3"
    settings = ProjectSettings(database_url=f"sqlite:///{path.as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    if request.param == "ready":
        command.upgrade(config, "head")
    with patch("src.cli_support.settings", settings):
        yield path


def _nodes(value: Any) -> Iterator[dict[str, Any]]:
    """Walk serialized results to compare provenance and traces across methods."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


@pytest.mark.parametrize("strategy", ["graham-number", "graham-growth", "fcf-growth"])
def test_cli_reopens_cache_without_refetch(configured_database: Path, strategy: str) -> None:
    graham = GrahamProvider()
    annual = FixtureAnnualFinancialFactsProvider(
        tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    )
    provider = graham if strategy.startswith("graham-") else ProductionFinancialFactsProvider(sec_edgar=annual)
    ticker = "SYNTH" if strategy.startswith("graham-") else "ACME"
    arguments = [strategy, ticker, "--json"]
    if strategy == "graham-growth":
        arguments += ["--expected-growth", "5", "--aaa-yield", "4.5"]
    profile = InstrumentProfile(ticker=ticker, identity=None, kind_evidence=None, diagnostics=())
    databases: list[SQLiteDatabase] = []

    def database(settings: ProjectSettings) -> SQLiteDatabase:
        instance = SQLiteDatabase(settings)
        databases.append(instance)
        return instance

    with (
        patch("src.cli._build_sec_production_provider", return_value=provider),
        patch("src.cli._compose_analysis_profile", return_value=profile),
        patch("src.cli_support.SQLiteDatabase", side_effect=database),
        patch.object(InputResolver, "_DEFAULT_CLOCK", staticmethod(lambda: NOW)),
    ):
        first = CliRunner().invoke(app, arguments)
        assert first.exit_code == 0, first.output
        assert configured_database.exists()
        calls = graham.calls if strategy.startswith("graham-") else len(annual.requests)
        assert calls > 0
        graham.fail = True
        with (
            patch.object(annual, "fetch_facts", side_effect=AssertionError("Unexpected provider access")),
            patch(
                "src.data.repositories.readiness.upgrade_fresh_database",
                side_effect=AssertionError("Unexpected migration"),
            ),
        ):
            second = CliRunner().invoke(app, arguments)
        assert second.exit_code == 0, second.output
    assert not first.stderr
    assert not second.stderr
    assert len(databases) == 2
    for instance in databases:
        with pytest.raises(RuntimeError, match="closed"), instance.read():
            pass
    first_nodes = list(_nodes(json.loads(first.output)))
    second_nodes = list(_nodes(json.loads(second.output)))
    cached = [node for node in second_nodes if node.get("source_kind") == "cache"]
    assert cached
    for fact in cached:
        assert fact["origin_source_kind"] in ("provider", "derived")
        assert fact["cache_schema_version"] == (1 if strategy.startswith("graham-") else 2)
        original = next(
            node
            for node in first_nodes
            if node.get("field_name") == fact["field_name"]
            and node.get("observation_period_end") == fact.get("observation_period_end")
            and "source_kind" in node
        )
        for field in (
            "value",
            "provider_id",
            "provider_field",
            "available_at",
            "retrieved_at",
            "observation_period_start",
            "observation_period_end",
            "notes",
            "lineage",
        ):
            assert fact.get(field) == original.get(field), field
    assert any(node.get("stage") == "cache" and node.get("outcome") == "hit" for node in second_nodes)
    assert not any(node.get("stage") == "provider" and node.get("outcome") == "attempted" for node in second_nodes)


@pytest.mark.parametrize("strategy", ["graham-number", "graham-growth", "fcf-growth"])
def test_no_cache_does_not_open_database(tmp_path: Path, strategy: str) -> None:
    path = tmp_path / "absent.sqlite3"
    annual = FixtureAnnualFinancialFactsProvider(
        tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    )
    provider = (
        GrahamProvider() if strategy.startswith("graham-") else ProductionFinancialFactsProvider(sec_edgar=annual)
    )
    ticker = "SYNTH" if strategy.startswith("graham-") else "ACME"
    arguments = [strategy, ticker, "--no-cache", "--json"]
    if strategy == "graham-growth":
        arguments += ["--expected-growth", "5", "--aaa-yield", "4.5"]
    profile = InstrumentProfile(ticker=ticker, identity=None, kind_evidence=None, diagnostics=())
    with (
        patch("src.cli_support.settings", ProjectSettings(database_url=f"sqlite:///{path.as_posix()}")),
        patch("src.cli._build_sec_production_provider", return_value=provider),
        patch("src.cli._compose_analysis_profile", return_value=profile),
        patch("src.cli_support.SQLiteDatabase", side_effect=AssertionError("Database must not open")),
    ):
        result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 0, result.output
    assert not path.exists()
    assert not Path(str(path) + ".readiness.lock").exists()
    nodes = list(_nodes(json.loads(result.output)))
    assert not any(node.get("source_kind") == "cache" for node in nodes)
    assert provider.calls > 0 if isinstance(provider, GrahamProvider) else len(annual.requests) > 0


def test_cache_scope_closes_on_error(configured_database: Path) -> None:
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{configured_database.as_posix()}"))
    with (
        patch("src.cli_support.SQLiteDatabase", return_value=database),
        pytest.raises(ValueError, match="analysis failed"),
        _production_financial_cache(enabled=True),
    ):
        raise ValueError("analysis failed")
    with pytest.raises(RuntimeError, match="closed"), database.read():
        pass


def test_explicit_memory_cache_is_retained() -> None:
    cache = InMemoryResolvedInputCache()
    with patch("src.cli._build_sec_production_provider", return_value=GrahamProvider()):
        resolver = _build_graham_resolver(resolver_type=GrahamNumberInputResolver, data_provider=None, cache=cache)
    assert resolver._cache is cache
