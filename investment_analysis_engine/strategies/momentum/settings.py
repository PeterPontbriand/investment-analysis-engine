"""Momentum's settings file: the values a user may tune without changing what the method is."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MomentumSettings(BaseModel):
    """The validated settings of the strategy.

    The model has no defaults: the ``settings.toml`` beside this module gives every key its shipped value, and the
    user's settings file may override any of them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    short_window: int = Field(gt=0, strict=True)
    """``short_window``: the short SMA window, in daily market observations."""

    long_window: int = Field(gt=0, strict=True)
    """``long_window``: the long SMA window, in daily market observations; larger than ``short_window``."""

    rsi_period: int = Field(gt=0, strict=True)
    """``rsi_period``: the RSI lookback period, in daily market observations."""

    history_start_date: date = Field(strict=False)
    """``history_start_date``: the first day of the historical price series, written as ``YYYY-MM-DD``."""

    @model_validator(mode="after")
    def _require_ordered_windows(self) -> Self:
        """Require the short window to be smaller than the long window."""
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self
