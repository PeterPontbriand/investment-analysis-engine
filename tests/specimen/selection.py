"""The specimen's immutable workspace selection snapshot."""

import math
from datetime import datetime

from pydantic import AwareDatetime, Field, StrictFloat, field_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection
from tests.specimen.analyzer import SpecimenConfig
from tests.specimen.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    MethodId,
)


class SpecimenSelection(FrozenSelection):
    """The specimen's selection: the input value and the shared point-in-time and cache fields."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    value: StrictFloat
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @field_validator("value")
    @classmethod
    def _require_finite_value(cls, value: float) -> float:
        """Reject NaN and infinity at the workspace boundary."""
        if not math.isfinite(value):
            raise ValueError("The input value must be a finite number.")
        return value

    def to_specimen_config(self) -> SpecimenConfig:
        """Return the calculation's configuration."""
        return SpecimenConfig(value=self.value)

    def to_analysis_context(self, executed_at: datetime) -> AnalysisContext:
        """Return the run context for this snapshot's persisted ``as_of`` and ``use_cache``."""
        return AnalysisContext(as_of=self.as_of, executed_at=executed_at, use_cache=self.use_cache)
