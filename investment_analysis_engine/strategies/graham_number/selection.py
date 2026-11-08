"""Graham Number's immutable workspace selection snapshot."""

import math
from datetime import datetime

from pydantic import AwareDatetime, Field, StrictFloat, ValidationInfo, field_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection, SelectionRuleError
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
    eps_override: StrictFloat | None = Field(
        default=None,
        description="Earnings per share to use instead of the reported figure; leave empty to use it.",
        json_schema_extra={"x-term": "override"},
    )
    quote_override: StrictFloat | None = Field(
        default=None,
        description="Share price to use instead of the current quote; leave empty to use the quote.",
        json_schema_extra={"x-term": "override"},
    )
    bvps_override: StrictFloat | None = Field(
        default=None,
        description="Book value per share to use instead of the reported figure; leave empty to use it.",
        json_schema_extra={"x-term": "override"},
    )
    as_of: AwareDatetime | None = Field(
        default=None,
        description=(
            "Run the analysis as of this date (the end of that day, UTC) or this moment, "
            "which needs a timezone offset; leave empty for the latest data."
        ),
        json_schema_extra={"x-term": "as-of-date"},
    )
    use_cache: bool = Field(
        default=True,
        strict=True,
        description="Whether the analysis may read and write the local cache of fetched data.",
        json_schema_extra={"x-term": "cache"},
    )

    @field_validator("eps_override", "quote_override", "bvps_override")
    @classmethod
    def _require_finite_overrides(cls, value: float | None, info: ValidationInfo) -> float | None:
        """Reject NaN/Inf financial overrides at the workspace boundary."""
        if value is not None and not math.isfinite(value):
            raise SelectionRuleError(
                f"Invalid {{{info.field_name}}}: Financial override must be a finite number.",
                fields=(str(info.field_name),),
                rule="graham-number.override_not_finite",
            )
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
