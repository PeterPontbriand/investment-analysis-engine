"""Graham Number's immutable workspace selection snapshot."""

import math
from datetime import datetime

from pydantic import AwareDatetime, Field, StrictFloat, field_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    MethodId,
)


class GrahamNumberSelection(FrozenSelection):
    """Immutable Graham Number selection with an optional book-value override."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    bvps_override: StrictFloat | None = None
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @field_validator("eps_override", "quote_override", "bvps_override")
    @classmethod
    def _require_finite_overrides(cls, value: float | None) -> float | None:
        """Reject NaN/Inf financial overrides at the workspace boundary."""
        if value is not None and not math.isfinite(value):
            raise ValueError("Financial override must be a finite number.")
        return value

    def to_graham_number_config(self) -> GrahamNumberConfig:
        """Return the existing analyzer config carrying this snapshot's values."""
        return GrahamNumberConfig(
            eps_override=self.eps_override,
            bvps_override=self.bvps_override,
            quote_override=self.quote_override,
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
