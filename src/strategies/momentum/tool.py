"""Momentum's production analysis-tool arguments."""

from __future__ import annotations

from pydantic import Field, model_validator

from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.strategies.momentum.analyzer import MomentumConfig

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
