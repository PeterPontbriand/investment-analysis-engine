"""The two analyzer forms and the shared readers of their generic arguments.

``BaseAnalyzer[ConfigT, ResultT]`` is the form of a strategy with a tunable choice and ``ConfigFreeAnalyzer[ResultT]``
the form of one with none. ``analyzer_result_type`` and ``analyzer_config_type`` are the only readers of either form,
and the conformance script and the documented-conventions test call them instead of reading ``__orig_bases__``.
"""

import inspect
from typing import get_args, get_origin, get_type_hints

import pytest

from investment_analysis_engine.analysis.base_analyzer import (
    AnalysisContext,
    BaseAnalyzer,
    ConfigFreeAnalyzer,
    analyzer_config_type,
    analyzer_result_type,
)
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthResult
from investment_analysis_engine.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer, PiotroskiResult
from investment_analysis_engine.strategies.piotroski.tool import PiotroskiToolDependencies
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyBehavior
from scripts import strategy_conformance as conformance
from tests.test_documented_conventions import _config_type_of

EXISTING: tuple[tuple[type, type, type], ...] = (
    (MomentumAnalyzer, MomentumConfig, MomentumRun),
    (GrahamNumberAnalyzer, GrahamNumberConfig, GrahamNumberAnalysis),
    (GrahamGrowthAnalyzer, GrahamGrowthConfig, GrahamGrowthAnalysis),
    (FCFEarningsGrowthAnalyzer, FCFEarningsGrowthConfig, FCFEarningsGrowthResult),
)
"""The four analyzers of the base form, their config types and their result types, written out."""


def _unspecialized() -> type:
    """Return a concrete subclass of the config-free base that does not say what it returns."""

    def run_analysis(self: object, ticker: str, context: AnalysisContext) -> object:
        raise NotImplementedError

    return type("Unspecialized", (ConfigFreeAnalyzer,), {"run_analysis": run_analysis})


def _declared_by_the_old_reading(analyzer: type) -> tuple[object, object]:
    """Return ``(ConfigT, ResultT)`` as the checks read them before the shared readers: from ``__orig_bases__``."""
    for base in getattr(analyzer, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            config, result = get_args(base)
            return config, result
    raise AssertionError(f"{analyzer.__name__} does not subclass BaseAnalyzer[ConfigT, ResultT].")


@pytest.mark.parametrize(("analyzer", "config", "result"), EXISTING, ids=lambda item: getattr(item, "__name__", ""))
def test_the_four_existing_analyzers_give_the_same_arguments_as_the_old_reading(
    analyzer: type, config: type, result: type
) -> None:
    assert (analyzer_config_type(analyzer), analyzer_result_type(analyzer)) == (config, result)
    assert _declared_by_the_old_reading(analyzer) == (config, result)


def test_the_config_free_form_has_a_result_type_and_no_config_type() -> None:
    assert analyzer_result_type(PiotroskiAnalyzer) is PiotroskiResult
    assert analyzer_config_type(PiotroskiAnalyzer) is None


def test_the_config_free_form_is_invoked_with_the_ticker_and_the_context_only() -> None:
    parameters = inspect.signature(PiotroskiAnalyzer.run_analysis, eval_str=True)
    assert list(parameters.parameters) == ["self", "ticker", "context"]
    hints = get_type_hints(ConfigFreeAnalyzer.run_analysis)
    assert hints["ticker"] is str
    assert hints["context"] is AnalysisContext
    assert (
        tuple(inspect.signature(ConfigFreeAnalyzer.run_analysis).parameters)
        == conformance.CONFIG_FREE_ENVELOPE_PARAMETERS
    )
    assert not issubclass(PiotroskiAnalyzer, BaseAnalyzer)


def test_a_class_of_neither_form_has_no_result_type_and_no_readable_config_type() -> None:
    class Bare:
        pass

    unspecialized = _unspecialized()

    assert analyzer_result_type(Bare) is None
    assert analyzer_result_type(unspecialized) is None
    with pytest.raises(TypeError, match="specializes neither"):
        analyzer_config_type(Bare)


def test_a_config_argument_that_is_not_a_concrete_type_is_refused() -> None:
    class Generic[ConfigArgument](BaseAnalyzer[ConfigArgument, int]):
        def run_analysis(self, ticker: str, config: ConfigArgument, context: AnalysisContext) -> int:
            raise NotImplementedError

    with pytest.raises(TypeError, match="no concrete config type"):
        analyzer_config_type(Generic)
    assert analyzer_result_type(Generic) is int


def test_the_conformance_check_finds_the_piotroski_analyzer_and_reads_its_result_type() -> None:
    conformance._import_strategy_modules()
    found = conformance._concrete_analyzers()
    assert PiotroskiAnalyzer in found
    assert all(analyzer in found for analyzer, _, _ in EXISTING)
    assert conformance._analyzer_result_type(PiotroskiAnalyzer) is PiotroskiResult
    assert conformance.analyzer_generics_gaps(STRATEGIES) == []


def test_the_conformance_check_still_reports_an_analyzer_of_neither_form(monkeypatch: pytest.MonkeyPatch) -> None:
    imaginary = type("Imaginary", (), {"__module__": "investment_analysis_engine.strategies.imaginary.analyzer"})
    real = conformance._concrete_analyzers
    monkeypatch.setattr(conformance, "_concrete_analyzers", lambda: [*real(), imaginary])
    assert conformance.analyzer_generics_gaps(STRATEGIES) == [
        "analyzer investment_analysis_engine.strategies.imaginary.analyzer.Imaginary "
        "does not specialize BaseAnalyzer[ConfigT, ResultT] or ConfigFreeAnalyzer[ResultT]"
    ]


def test_the_conformance_check_reports_a_changed_config_free_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    assert conformance.analyzer_envelope_gaps() == []
    monkeypatch.setattr(conformance, "CONFIG_FREE_ENVELOPE_PARAMETERS", ("self", "ticker", "config", "context"))
    gaps = conformance.analyzer_envelope_gaps()
    assert len(gaps) == 1
    assert gaps[0].startswith("config-free run_analysis parameters changed")


def test_the_documented_conventions_check_reads_a_config_free_analyzer_as_having_no_config_type() -> None:
    assert _config_type_of(PiotroskiToolDependencies) is None
    for descriptor in STRATEGIES:
        behavior = descriptor.behavior
        assert isinstance(behavior, StrategyBehavior)
        config = _config_type_of(behavior.deps_type)
        assert (config is None) == (descriptor.alias == "piotroski")
