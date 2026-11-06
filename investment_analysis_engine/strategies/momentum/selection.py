"""Momentum's immutable workspace selection snapshot."""

from collections.abc import Mapping
from datetime import datetime

from pydantic import AwareDatetime, Field, model_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection, SelectionRuleError
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.strategies.momentum.analyzer import MomentumConfig
from investment_analysis_engine.strategies.momentum.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    MethodId,
)


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

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    short_window: int = Field(gt=0, strict=True, description="Number of trading days in the short moving average.")
    long_window: int = Field(
        gt=0,
        strict=True,
        description="Number of trading days in the long moving average; it must be larger than the short one.",
    )
    rsi_period: int = Field(
        gt=0, strict=True, description="Number of trading days the relative strength index looks back over."
    )
    as_of: AwareDatetime | None = Field(
        default=None,
        description=(
            "Run the analysis as of this date (the end of that day, UTC) or this moment, "
            "which needs a timezone offset; leave empty for the latest data."
        ),
    )
    use_cache: bool = Field(
        default=True,
        strict=True,
        description="Whether the analysis may read and write the local cache of fetched data.",
    )

    @model_validator(mode="before")
    @classmethod
    def _require_positive_periods(cls, data: object) -> object:
        """Reject a window or period that is not positive, with a message that names the field and its value."""
        if not isinstance(data, Mapping):
            return data
        rules = (
            ("short_window", "window", "momentum.short_window_not_positive"),
            ("long_window", "window", "momentum.long_window_not_positive"),
            ("rsi_period", "period", "momentum.rsi_period_not_positive"),
        )
        for field, noun, rule in rules:
            value = data.get(field)
            if type(value) is int and value <= 0:
                raise SelectionRuleError(
                    f"Invalid momentum {noun}: {{{field}}} must be positive (received {{{field}_value}}).",
                    fields=(field,),
                    rule=rule,
                    arguments={f"{field}_value": value},
                )
        return data

    @model_validator(mode="after")
    def _validate_windows(self) -> "MomentumSelection":
        """Require a short window smaller than the long window, as the analyzer does."""
        if self.short_window >= self.long_window:
            raise SelectionRuleError(
                "Invalid momentum windows: {short_window} ({short_window_value}) "
                "must be smaller than {long_window} ({long_window_value}).",
                fields=("short_window", "long_window"),
                rule="momentum.window_order",
                arguments={"short_window_value": self.short_window, "long_window_value": self.long_window},
            )
        return self

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
