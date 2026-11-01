"""The cache choice every strategy's tool arguments share is declared once, on the base model."""

import inspect

import pytest

from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda descriptor: descriptor.alias)
def test_each_strategy_inherits_use_cache_and_does_not_redeclare_it(descriptor: StrategyDescriptor) -> None:
    model = descriptor.tool_arguments

    assert issubclass(model, AnalysisToolArguments)
    assert "use_cache" not in inspect.get_annotations(model)
    assert model.model_fields["use_cache"].annotation is bool
    assert model.model_fields["use_cache"].default is True


def test_use_cache_defaults_to_true_on_the_base_model() -> None:
    assert AnalysisToolArguments(ticker="KO").use_cache is True
    assert AnalysisToolArguments(ticker="KO", use_cache=False).use_cache is False
