"""The specimen's tool name, arguments, dependencies and handler.

``ToolName`` is a closed production enumeration that no test may extend, so the specimen names its tool with an
enumeration of its own. The generator's end-to-end test covers a real ``ToolName`` member.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments, FiniteFloat
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from tests.specimen.analyzer import SpecimenAnalyzer, SpecimenConfig, SpecimenResult


class SpecimenTool(StrEnum):
    """The specimen's analysis-tool identifier."""

    ANALYZE_SPECIMEN = "analyze_specimen"


class SpecimenToolArguments(AnalysisToolArguments):
    """Validated arguments for the specimen analysis."""

    value: FiniteFloat
    use_cache: bool = True


@dataclass(frozen=True)
class SpecimenToolDependencies:
    """The injected specimen analyzer."""

    analyzer: SpecimenAnalyzer


class SpecimenToolHandler:
    """Bind the specimen's injected analyzer and the shared runtime to the analysis tool."""

    def __init__(self, dependencies: SpecimenToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> SpecimenResult:
        """Validate the arguments and run one specimen analysis."""
        arguments = SpecimenToolArguments.model_validate(raw_arguments)
        context = AnalysisContext(
            as_of=arguments.as_of, executed_at=self._runtime.validated_clock_value(), use_cache=arguments.use_cache
        )
        return self._dependencies.analyzer.run_analysis(
            arguments.ticker, SpecimenConfig(value=arguments.value), context
        )
