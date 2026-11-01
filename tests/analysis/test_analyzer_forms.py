"""The one analyzer base and the shared readers of its generic arguments.

``BaseAnalyzer[ResultT]`` is the form of a strategy with no tunable choice and ``BaseAnalyzer[ResultT, ConfigT]`` the
form of one with a typed configuration. ``analyzer_result_type`` and ``analyzer_config_type`` are the only readers of
either specialization, and the conformance script and the documented-conventions test call them instead of reading
``__orig_bases__``.
"""

import inspect
from typing import get_type_hints

import pytest

from investment_analysis_engine.analysis.base_analyzer import (
    AnalysisContext,
    BaseAnalyzer,
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
from tests.specimen.analyzer import SpecimenAnalyzer, SpecimenConfig, SpecimenResult
from tests.test_documented_conventions import _config_type_of

WRITTEN_OUT: tuple[tuple[type, type, type | None], ...] = (
    (MomentumAnalyzer, MomentumRun, MomentumConfig),
    (GrahamNumberAnalyzer, GrahamNumberAnalysis, GrahamNumberConfig),
    (GrahamGrowthAnalyzer, GrahamGrowthAnalysis, GrahamGrowthConfig),
    (FCFEarningsGrowthAnalyzer, FCFEarningsGrowthResult, FCFEarningsGrowthConfig),
    (PiotroskiAnalyzer, PiotroskiResult, None),
    (SpecimenAnalyzer, SpecimenResult, SpecimenConfig),
)
"""The five strategies' analyzers and the specimen, with their result types and config types, written out."""


class _Result:
    """A result type for the classes below."""


class _NoConfig(BaseAnalyzer[_Result]):
    def run_analysis(self, ticker: str, context: AnalysisContext) -> _Result:
        raise NotImplementedError


class _OneConfig(BaseAnalyzer[_Result, int]):
    def run_analysis(self, ticker: str, context: AnalysisContext, config: int) -> _Result:
        raise NotImplementedError


class _TwoConfigs(BaseAnalyzer[_Result, int, str]):
    def run_analysis(self, ticker: str, context: AnalysisContext, *config: int | str) -> _Result:
        raise NotImplementedError


def _unspecialized() -> type:
    """Return a concrete subclass of the base that does not say what it returns."""

    def run_analysis(self: object, ticker: str, context: AnalysisContext, *config: object) -> object:
        raise NotImplementedError

    return type("Unspecialized", (BaseAnalyzer,), {"run_analysis": run_analysis})


@pytest.mark.parametrize(("analyzer", "result", "config"), WRITTEN_OUT, ids=lambda item: getattr(item, "__name__", ""))
def test_the_five_strategies_and_the_specimen_give_their_result_and_config_types(
    analyzer: type, result: type, config: type | None
) -> None:
    assert analyzer_result_type(analyzer) is result
    assert analyzer_config_type(analyzer) is config


def test_both_specializations_are_read_correctly() -> None:
    assert (analyzer_result_type(_NoConfig), analyzer_config_type(_NoConfig)) == (_Result, None)
    assert (analyzer_result_type(_OneConfig), analyzer_config_type(_OneConfig)) == (_Result, int)


def test_the_run_analysis_signature_puts_the_context_before_the_config() -> None:
    assert list(inspect.signature(BaseAnalyzer.run_analysis).parameters) == ["self", "ticker", "context", "config"]
    assert list(inspect.signature(PiotroskiAnalyzer.run_analysis).parameters) == ["self", "ticker", "context"]
    assert list(inspect.signature(MomentumAnalyzer.run_analysis).parameters) == ["self", "ticker", "context", "config"]
    hints = get_type_hints(BaseAnalyzer.run_analysis)
    assert hints["ticker"] is str
    assert hints["context"] is AnalysisContext


def test_a_class_with_two_config_arguments_is_refused_naming_the_class() -> None:
    with pytest.raises(TypeError, match="_TwoConfigs declares 2 config types"):
        analyzer_config_type(_TwoConfigs)
    assert analyzer_result_type(_TwoConfigs) is _Result


def test_an_unspecialized_subclass_has_no_result_type_and_no_readable_config_type() -> None:
    class Bare:
        pass

    unspecialized = _unspecialized()

    assert analyzer_result_type(Bare) is None
    assert analyzer_result_type(unspecialized) is None
    with pytest.raises(TypeError, match="does not specialize BaseAnalyzer"):
        analyzer_config_type(Bare)
    with pytest.raises(TypeError, match="does not specialize BaseAnalyzer"):
        analyzer_config_type(unspecialized)


def test_a_config_argument_that_is_not_a_concrete_type_is_refused() -> None:
    class Generic[ConfigArgument](BaseAnalyzer[int, ConfigArgument]):
        def run_analysis(self, ticker: str, context: AnalysisContext, config: ConfigArgument) -> int:
            raise NotImplementedError

    with pytest.raises(TypeError, match="no concrete config type"):
        analyzer_config_type(Generic)
    assert analyzer_result_type(Generic) is int


def test_the_conformance_check_finds_every_analyzer_and_reads_the_result_types() -> None:
    conformance._import_strategy_modules()
    found = conformance._concrete_analyzers()
    for analyzer, result, _ in WRITTEN_OUT:
        if analyzer is not SpecimenAnalyzer:
            assert analyzer in found
            assert conformance._analyzer_result_type(analyzer) is result
    assert conformance.analyzer_generics_gaps(STRATEGIES) == []


def test_the_conformance_check_reports_an_analyzer_that_does_not_specialize_the_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imaginary = type("Imaginary", (), {"__module__": "investment_analysis_engine.strategies.imaginary.analyzer"})
    real = conformance._concrete_analyzers
    monkeypatch.setattr(conformance, "_concrete_analyzers", lambda: [*real(), imaginary])
    assert conformance.analyzer_generics_gaps(STRATEGIES) == [
        "analyzer investment_analysis_engine.strategies.imaginary.analyzer.Imaginary "
        "does not specialize BaseAnalyzer[ResultT] or BaseAnalyzer[ResultT, ConfigT]"
    ]


def test_the_conformance_check_reports_an_analyzer_that_declares_two_config_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_TwoConfigs, "__module__", "investment_analysis_engine.strategies.imaginary.analyzer")
    gaps = conformance.analyzer_generics_gaps(STRATEGIES)
    assert [gap for gap in gaps if "declares 2 config types" in gap] == [
        "analyzer investment_analysis_engine.strategies.imaginary.analyzer._TwoConfigs: "
        "_TwoConfigs declares 2 config types; at most one is allowed."
    ]


def test_the_conformance_check_reports_a_changed_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    assert conformance.analyzer_envelope_gaps() == []
    monkeypatch.setattr(conformance, "ANALYZER_ENVELOPE_PARAMETERS", ("self", "ticker", "config", "context"))
    gaps = conformance.analyzer_envelope_gaps()
    assert len(gaps) == 1
    assert gaps[0].startswith("run_analysis parameters changed")


def test_the_documented_conventions_check_reads_a_config_free_analyzer_as_having_no_config_type() -> None:
    assert _config_type_of(PiotroskiToolDependencies) is None
    for descriptor in STRATEGIES:
        behavior = descriptor.behavior
        assert isinstance(behavior, StrategyBehavior)
        config = _config_type_of(behavior.deps_type)
        assert (config is None) == (descriptor.alias == "piotroski")
