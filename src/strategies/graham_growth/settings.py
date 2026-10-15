"""Graham Growth's settings file: the configured constants of the growth-value method."""

import math

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator

from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy


class GrahamGrowthSettings(BaseModel):
    """The validated content of ``config/strategies/graham-growth.toml``.

    The model has no defaults: the shipped file is the single source of every value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_pe: StrictFloat
    """``base_pe``: the price-to-earnings ratio of a no-growth company; positive."""

    growth_multiplier: StrictFloat
    """``growth_multiplier``: the P/E added per percentage point of expected growth; zero or more."""

    baseline_aaa_yield: StrictFloat
    """``baseline_aaa_yield``: the AAA bond yield, in percent, the formula is calibrated to; positive."""

    @field_validator("base_pe")
    @classmethod
    def _require_positive_base_pe(cls, value: float) -> float:
        """Require a finite, positive base P/E."""
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be a finite number greater than zero.")
        return value

    @field_validator("growth_multiplier")
    @classmethod
    def _require_non_negative_growth_multiplier(cls, value: float) -> float:
        """Require a finite growth multiplier that is not negative."""
        if not math.isfinite(value) or value < 0:
            raise ValueError("must be a finite number, zero or more.")
        return value

    @field_validator("baseline_aaa_yield")
    @classmethod
    def _require_positive_baseline_yield(cls, value: float) -> float:
        """Require a finite, positive baseline AAA yield."""
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be a finite number greater than zero.")
        return value

    def to_policy(self) -> GrahamGrowthCalculationPolicy:
        """Return the calculation policy carrying these constants."""
        return GrahamGrowthCalculationPolicy(
            base_pe=self.base_pe,
            growth_multiplier=self.growth_multiplier,
            baseline_aaa_yield=self.baseline_aaa_yield,
        )
