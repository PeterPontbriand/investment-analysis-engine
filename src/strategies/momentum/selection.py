"""Momentum's immutable workspace selection snapshot."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from src.analysis.base_analyzer import AnalysisContext
from src.config import settings
from src.core.constants import ConfigKeys
from src.data.instrument_profile import InstrumentProfile
from src.strategies.momentum.analyzer import MomentumConfig
from src.workspace.selection_base import FrozenSelection


class MomentumSelection(FrozenSelection):
    """Immutable snapshot of the effective Momentum configuration.

    The canonical analysis/method identifiers are fixed to the contract matrix values
    (``momentum`` / ``sma_crossover``) and cannot be overridden or made to disagree
    with one another. Window and RSI values are materialized from explicit inputs or
    the current configured policy at creation time; later settings changes do not
    affect an existing selection. ``as_of`` and ``use_cache`` are persisted with the
    selection, so a saved or refreshed run reuses the boundary and cache choice it was
    created with.
    """

    analysis_id: Literal["momentum"] = "momentum"
    method_id: Literal["sma_crossover"] = "sma_crossover"
    config_schema_version: Literal[2] = 2
    short_window: int = Field(gt=0, strict=True)
    long_window: int = Field(gt=0, strict=True)
    rsi_period: int = Field(default=14, gt=0, strict=True)
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def _validate_windows(self) -> "MomentumSelection":
        """Require a short window smaller than the long window, as the analyzer does."""
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self

    @classmethod
    def from_settings(
        cls,
        *,
        short_window: int | None = None,
        long_window: int | None = None,
        rsi_period: int | None = None,
        **overrides: object,
    ) -> "MomentumSelection":
        """Create a selection, materializing omitted values from configured policy.

        Window defaults follow the same ``window_sizes`` configuration table used by
        :class:`MomentumConfig`; the RSI period keeps that config's fixed 14 default
        because it is not part of the momentum settings file. Unknown keyword arguments
        are forwarded to validation so they are rejected with a standard extra-field
        error rather than a constructor TypeError.
        """
        values: dict[str, object] = {**overrides}
        window_sizes = (
            settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES]
            if short_window is None or long_window is None
            else {}
        )
        if short_window is not None:
            values["short_window"] = short_window
        else:
            values["short_window"] = int(window_sizes[ConfigKeys.SHORT_WINDOW])
        if long_window is not None:
            values["long_window"] = long_window
        else:
            values["long_window"] = int(window_sizes[ConfigKeys.LONG_WINDOW])
        if rsi_period is not None:
            values["rsi_period"] = rsi_period
        return cls.model_validate(values)

    def to_momentum_config(self) -> MomentumConfig:
        """Return the existing analyzer config carrying this snapshot's values."""
        return MomentumConfig(
            short_window=self.short_window,
            long_window=self.long_window,
            rsi_period=self.rsi_period,
        )

    def to_analysis_context(
        self, executed_at: datetime, instrument_profile: InstrumentProfile | None = None
    ) -> AnalysisContext:
        """Return the run context for this snapshot's persisted ``as_of``/``use_cache``."""
        return AnalysisContext(
            as_of=self.as_of,
            executed_at=executed_at,
            use_cache=self.use_cache,
            instrument_profile=instrument_profile,
        )
