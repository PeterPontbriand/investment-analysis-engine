"""Momentum's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field, model_validator

from src.analysis.base_analyzer import AnalysisContext
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from src.strategies.momentum.settings import MomentumSettings

_OMIT_TO_USE_CONFIGURED = "Omit to use the configured value."


class MomentumToolArguments(AnalysisToolArguments):
    """Validated arguments for Momentum analysis."""

    short_window: int | None = Field(default=None, gt=0, description=_OMIT_TO_USE_CONFIGURED)
    long_window: int | None = Field(default=None, gt=0, description=_OMIT_TO_USE_CONFIGURED)
    rsi_period: int | None = Field(default=None, gt=0, description=_OMIT_TO_USE_CONFIGURED)
    use_cache: bool = True

    @model_validator(mode="after")
    def require_ordered_windows(self) -> MomentumToolArguments:
        """Require the short window to precede the long window when both are given."""
        if self.short_window is not None and self.long_window is not None and self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self


@dataclass(frozen=True)
class MomentumToolDependencies:
    """Injected Momentum analyzer and the configured values that fill omitted arguments."""

    analyzer: MomentumAnalyzer
    settings: MomentumSettings


class MomentumToolHandler:
    """Bind Momentum's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: MomentumToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> MomentumRun:
        """Validate, resolve, and calculate one Momentum run."""
        arguments = MomentumToolArguments.model_validate(raw_arguments)
        configured = self._dependencies.settings
        config = MomentumConfig(
            short_window=configured.short_window if arguments.short_window is None else arguments.short_window,
            long_window=configured.long_window if arguments.long_window is None else arguments.long_window,
            rsi_period=configured.rsi_period if arguments.rsi_period is None else arguments.rsi_period,
        )
        executed_at = self._runtime.validated_clock_value()
        profile = self._runtime.resolve_profile(arguments.ticker)
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)
