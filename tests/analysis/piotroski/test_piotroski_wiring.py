"""The Piotroski strategy's gate against its documented row, its tool, its selection and its production composition."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.shared.applicability import IndustryClass
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.evaluation.fixture_context import FixtureContext
from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import (
    STATEMENTS_APPLE_FIXTURE_ID,
    STATEMENTS_MONSTER_FIXTURE_ID,
)
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies.piotroski import application as piotroski_application
from investment_analysis_engine.strategies.piotroski.analyzer import PIOTROSKI_SECTOR_GATE, PiotroskiAnalyzer
from investment_analysis_engine.strategies.piotroski.evaluation import compose
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategies.piotroski.tool import PiotroskiToolArguments, PiotroskiToolHandler
from investment_analysis_engine.strategy_wiring import BY_ALIAS
from scripts.repository_root import REPOSITORY_ROOT
from tests.analysis.piotroski._statements_rig import CLOCK

SHARED_DEFINITIONS = (
    REPOSITORY_ROOT / "docs" / "project" / "milestones" / "v0.2" / "step-3.5" / "STEP_3_5_SHARED_DEFINITIONS.md"
)
AS_OF = datetime(2025, 1, 15, tzinfo=UTC)


def _matrix_row(strategy: str) -> list[str]:
    """Return the cells of a strategy's row in the applicability matrix of Shared definitions §1."""
    text = SHARED_DEFINITIONS.read_text(encoding="utf-8")
    section = text.split("## 1. Applicability", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == strategy:
            return cells
    raise AssertionError(f"{strategy} has no row in the applicability matrix.")


def test_the_sector_gate_is_pinned_to_the_piotroski_row_of_the_applicability_matrix() -> None:
    _, financial, utility, _notes = _matrix_row("Piotroski")
    assert financial == "Applicable, with a warning"
    assert utility == "Applicable"
    refused = {
        industry_class
        for industry_class, cell in ((IndustryClass.FINANCIAL, financial), (IndustryClass.UTILITY, utility))
        if cell.lower().startswith("not applicable")
    }
    warned = {
        industry_class
        for industry_class, cell in ((IndustryClass.FINANCIAL, financial), (IndustryClass.UTILITY, utility))
        if "with a warning" in cell.lower()
    }
    assert PIOTROSKI_SECTOR_GATE.not_applicable == refused == frozenset()
    assert PIOTROSKI_SECTOR_GATE.warn == warned == {IndustryClass.FINANCIAL}
    # Shared definitions §2: "Piotroski is not sector-gated, runs, and states the class is unknown."
    assert "Piotroski is not sector-gated, runs, and states the class is unknown" in SHARED_DEFINITIONS.read_text(
        encoding="utf-8"
    )
    assert PIOTROSKI_SECTOR_GATE.gated is False


def test_the_matrix_has_no_other_strategy_that_the_gate_could_be_confused_with() -> None:
    assert _matrix_row("Altman")[1] == "Not applicable"
    assert _matrix_row("Piotroski") != _matrix_row("Altman")


def test_the_descriptor_declares_the_strategy_without_a_config_or_settings() -> None:
    descriptor = BY_ALIAS["piotroski"]
    assert descriptor.label == "Piotroski F-Score"
    assert descriptor.settings_type is None
    assert (descriptor.method_version, descriptor.result_schema_version, descriptor.evidence_codec_version) == (2, 2, 1)
    assert descriptor.config_schema_version == 1


def test_the_tool_arguments_have_no_option_that_holds_only_one_value() -> None:
    assert set(PiotroskiToolArguments.model_fields) == {"ticker", "as_of", "use_cache"}
    with pytest.raises(ValidationError):
        PiotroskiToolArguments.model_validate({"ticker": "AAPL", "window": 3})


def test_the_tool_runs_the_analyzer_with_the_tickers_context_and_no_config() -> None:
    context = FixtureContext(frozenset({STATEMENTS_APPLE_FIXTURE_ID}), CLOCK, None)
    handler = PiotroskiToolHandler(compose(context), ToolRuntime(clock=lambda: CLOCK))
    result = handler(ticker=" aapl ", as_of=AS_OF)
    assert result.ticker == "AAPL"
    assert result.execution_status is CalculationStatus.OK
    assert result.f_score is not None
    assert result.f_score.score.value == 7.0
    assert result.effective_as_of == AS_OF
    with pytest.raises(ValueError, match="timezone-aware"):
        PiotroskiToolHandler(compose(context), ToolRuntime(clock=lambda: datetime(2026, 1, 1)))(ticker="AAPL")


def test_the_evaluation_composition_serves_the_issuer_the_case_selected() -> None:
    monster = compose(FixtureContext(frozenset({STATEMENTS_MONSTER_FIXTURE_ID}), CLOCK, None))
    result = monster.analyzer.run_analysis(
        "MNST", AnalysisContext(as_of=datetime(2026, 3, 31, tzinfo=UTC), executed_at=CLOCK, use_cache=True)
    )
    assert result.f_score is not None
    assert result.f_score.score.value == 5.0


def test_the_selection_holds_only_the_boundary_and_the_cache_choice_and_makes_a_context() -> None:
    assert set(PiotroskiSelection.model_fields) == {
        "analysis_id",
        "method_id",
        "config_schema_version",
        "as_of",
        "use_cache",
    }
    selection = PiotroskiSelection(as_of=AS_OF, use_cache=False)
    context = selection.to_analysis_context(CLOCK)
    assert (context.as_of, context.executed_at, context.use_cache, context.instrument_profile) == (
        AS_OF,
        CLOCK,
        False,
        None,
    )
    assert PiotroskiSelection.model_validate_json(selection.model_dump_json()) == selection
    with pytest.raises(ValidationError):
        PiotroskiSelection.model_validate({"as_of": "2025-01-15T00:00:00"})


def test_production_composes_one_adapter_that_serves_the_resolver_and_the_industry_class() -> None:
    adapter = SecEdgarFinancialFactsAdapter(user_agent="Synthetic test")
    context = ApplicationContext(settings=ProjectSettings())
    with patch.object(piotroski_application, "build_sec_edgar_adapter", return_value=adapter) as build:
        analyzer, provider = piotroski_application.compose_piotroski(context, CLOCK)
    build.assert_called_once_with(context)
    assert isinstance(analyzer, PiotroskiAnalyzer)
    assert isinstance(provider, ProductionFinancialFactsProvider)
    assert analyzer._industry_classes is adapter
    assert analyzer._resolver.provider.__class__ is ProductionFinancialFactsProvider
    assert provider._providers["sec_edgar"] is adapter
