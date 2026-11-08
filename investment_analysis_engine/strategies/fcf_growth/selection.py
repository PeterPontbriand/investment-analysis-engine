"""Free Cash Flow & Earnings Growth's immutable workspace selection snapshot."""

from datetime import datetime

from pydantic import AwareDatetime, Field, field_validator, model_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.selection_base import FrozenSelection, SelectionRuleError
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthPolicy
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    METHOD_ID,
    AnalysisId,
    ConfigSchemaVersion,
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
    MethodId,
)


class FCFPolicySnapshot(FrozenSelection):
    """Validated immutable copy of the existing FCF policy and its native enums."""

    historical_horizon: HistoricalHorizon = Field(
        default=HistoricalHorizon.LONGEST_AVAILABLE,
        description="How many elapsed years of history to require; the default picks the longest available up to five.",
        json_schema_extra={"x-term": "historical-horizon"},
    )
    classification_basis: FCFClassificationBasis = Field(
        default=FCFClassificationBasis.TOTAL_FCF,
        description="Whether growth is classified on total free cash flow or on free cash flow per share.",
        json_schema_extra={"x-term": "classification-basis"},
    )
    forward_policy: ForwardPolicy = Field(
        default=ForwardPolicy.DISPLAY_ONLY,
        description="How forward-looking evidence affects the result: shown only, required to confirm, or a hard gate.",
        json_schema_extra={"x-term": "forward-policy"},
    )

    @model_validator(mode="before")
    @classmethod
    def _copy_existing_policy(cls, value: object) -> object:
        if isinstance(value, FCFEarningsGrowthPolicy):
            return {
                "historical_horizon": value.historical_horizon,
                "classification_basis": value.classification_basis,
                "forward_policy": value.forward_policy,
            }
        return value

    def to_policy(self) -> FCFEarningsGrowthPolicy:
        """Return a fresh instance of the analyzer's existing policy dataclass."""
        return FCFEarningsGrowthPolicy(
            historical_horizon=self.historical_horizon,
            classification_basis=self.classification_basis,
            forward_policy=self.forward_policy,
        )


class FCFGrowthSelection(FrozenSelection):
    """Historical FCF/Earnings Growth request options, independent of Graham configs."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: ConfigSchemaVersion = CONFIG_SCHEMA_VERSION
    policy: FCFPolicySnapshot = Field(
        default_factory=FCFPolicySnapshot,
        description="The growth horizon, classification and forward-evidence rules.",
        json_schema_extra={"x-term": "fcf-growth-strategy"},
    )
    currency: str = Field(
        default="USD",
        description="Three-letter ISO 4217 code of the reporting currency the annual facts must use.",
        json_schema_extra={"x-term": "reporting-currency"},
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

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise SelectionRuleError(
                "{currency} must be a three-letter ISO 4217 code.",
                fields=("currency",),
                rule="fcf-growth.currency_format",
            )
        return normalized

    def to_fcf_policy(self) -> FCFEarningsGrowthPolicy:
        """Return the existing policy type for explicit analyzer invocation."""
        return self.policy.to_policy()

    def to_fcf_config(self) -> FCFEarningsGrowthConfig:
        """Return the analyzer's complete per-call configuration for this snapshot."""
        return FCFEarningsGrowthConfig(policy=self.to_fcf_policy(), currency=self.currency)

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
