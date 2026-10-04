"""Momentum's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field, model_validator

from src.analysis.base_analyzer import AnalysisContext
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun

_MOMENTUM_DEFAULTS = MomentumConfig()


class MomentumToolArguments(AnalysisToolArguments):
    """Validated arguments for Momentum analysis."""

    short_window: int = Field(default=_MOMENTUM_DEFAULTS.short_window, gt=0)
    long_window: int = Field(default=_MOMENTUM_DEFAULTS.long_window, gt=0)
    rsi_period: int = Field(default=_MOMENTUM_DEFAULTS.rsi_period, gt=0)
    use_cache: bool = True

    @model_validator(mode="after")
    def require_ordered_windows(self) -> MomentumToolArguments:
        """Require the short window to precede the long window."""
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self


@dataclass(frozen=True)
class MomentumToolDependencies:
    """Injected Momentum analyzer."""

    analyzer: MomentumAnalyzer


class MomentumToolHandler:
    """Bind Momentum's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: MomentumToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> MomentumRun:
        """Validate, resolve, and calculate one Momentum run."""
        arguments = MomentumToolArguments.model_validate(raw_arguments)
        config = MomentumConfig(
            short_window=arguments.short_window,
            long_window=arguments.long_window,
            rsi_period=arguments.rsi_period,
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
