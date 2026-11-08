"""The Piotroski F-Score strategy's immutable workspace selection snapshot."""

from datetime import datetime

from pydantic import AwareDatetime, Field

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.strategies.piotroski.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    MethodId,
)


class PiotroskiSelection(FrozenSelection):
    """The Piotroski F-Score selection: the shared point-in-time and cache fields."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
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
