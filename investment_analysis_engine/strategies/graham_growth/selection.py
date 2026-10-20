"""Graham growth-value's immutable workspace selection snapshot."""

import math
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, StrictFloat, field_validator, model_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig
from investment_analysis_engine.strategies.graham_growth.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    MethodId,
)

GrahamGrowthSelectionEPSBasis = Literal["three_year_average", "fiscal_year"]
"""The EPS bases a stored selection accepts: the ones SEC EDGAR supplies for Graham Growth."""


class GrahamGrowthSelection(FrozenSelection):
    """Graham growth-value selection requiring explicit growth and AAA yield percentages."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    eps_basis: GrahamGrowthSelectionEPSBasis | None = None
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    expected_growth: StrictFloat
    aaa_yield_override: StrictFloat
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @field_validator("eps_override", "quote_override", "expected_growth", "aaa_yield_override")
    @classmethod
    def _require_finite_overrides(cls, value: float | None) -> float | None:
        """Reject NaN/Inf financial overrides at the workspace boundary."""
        if value is not None and not math.isfinite(value):
            raise ValueError("Financial override must be a finite number.")
        return value

    @field_validator("eps_basis", mode="before")
    @classmethod
    def _normalize_basis(cls, value: object) -> object:
        """Normalize explicit basis strings before validating supported literals."""
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _resolve_configuration(self) -> "GrahamGrowthSelection":
        """Resolve the effective EPS basis by constructing this method's own config.

        ``GrahamGrowthConfig.validate_method`` is the single definition of Graham Growth's
        entire accept/default rule; this Selection validates by delegating to it rather than
        reimplementing the rule, so the CLI-direct and ``--save-run``/workspace entry points
        cannot silently diverge.
        """
        config = self.to_graham_growth_config()
        object.__setattr__(self, "eps_basis", config.eps_basis)
        return self

    def to_graham_growth_config(self) -> GrahamGrowthConfig:
        """Return the existing config without deriving assumptions or calculation policy."""
        return GrahamGrowthConfig(
            eps_basis=self.eps_basis,
            eps_override=self.eps_override,
            quote_override=self.quote_override,
            expected_growth=self.expected_growth,
            aaa_yield_override=self.aaa_yield_override,
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
