"""Graham growth-value's immutable workspace selection snapshot."""

import math
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, StrictFloat, ValidationInfo, field_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection, SelectionRuleError
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

type GrahamGrowthSelectionEPSBasis = Literal["three_year_average", "fiscal_year"]
"""The EPS bases a stored selection accepts: the ones SEC EDGAR supplies for Graham Growth."""


class GrahamGrowthSelection(FrozenSelection):
    """Graham growth-value selection requiring explicit growth and AAA yield percentages."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    eps_basis: GrahamGrowthSelectionEPSBasis = Field(
        default="three_year_average",
        description="Which earnings figure to use: the three-year average, or one completed fiscal year.",
        json_schema_extra={"x-term": "eps-basis"},
    )
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
    expected_growth: StrictFloat = Field(
        description="Expected annual earnings growth, in percentage points.",
        json_schema_extra={"x-term": "expected-growth-rate"},
    )
    aaa_yield_override: StrictFloat = Field(
        description="Current AAA corporate-bond yield, in percentage points.", json_schema_extra={"x-term": "override"}
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

    @field_validator("eps_override", "quote_override", "expected_growth", "aaa_yield_override")
    @classmethod
    def _require_finite_overrides(cls, value: float | None, info: ValidationInfo) -> float | None:
        """Reject NaN/Inf financial overrides at the workspace boundary."""
        if value is not None and not math.isfinite(value):
            raise SelectionRuleError(
                f"Invalid {{{info.field_name}}}: Financial override must be a finite number.",
                fields=(str(info.field_name),),
                rule="graham-growth.override_not_finite",
            )
        return value

    @field_validator("quote_override")
    @classmethod
    def _require_positive_quote(cls, value: float | None) -> float | None:
        """Reject a zero or negative price override at the workspace boundary."""
        if value is not None and value <= 0:
            raise SelectionRuleError(
                "Invalid {quote_override}: Share price override must be greater than zero.",
                fields=("quote_override",),
                rule="graham-growth.quote_override_not_positive",
            )
        return value

    @field_validator("aaa_yield_override")
    @classmethod
    def _require_positive_aaa_yield(cls, value: float) -> float:
        """Reject a zero or negative AAA yield at the workspace boundary."""
        if value <= 0:
            raise SelectionRuleError(
                "Invalid {aaa_yield_override}: AAA yield must be greater than zero.",
                fields=("aaa_yield_override",),
                rule="graham-growth.aaa_yield_override_not_positive",
            )
        return value

    @field_validator("eps_basis", mode="before")
    @classmethod
    def _normalize_basis(cls, value: object) -> object:
        """Normalize explicit basis strings before validating supported literals."""
        return value.strip().lower() if isinstance(value, str) else value

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
