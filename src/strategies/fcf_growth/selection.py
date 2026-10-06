"""Free Cash Flow & Earnings Growth's immutable workspace selection snapshot."""

from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from src.analysis.base_analyzer import AnalysisContext
from src.data.instrument_profile import InstrumentProfile
from src.strategies.fcf_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
)
from src.workspace.selection_base import FrozenSelection


class FCFPolicySnapshot(FrozenSelection):
    """Validated immutable copy of the existing FCF policy and its native enums."""

    historical_horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE
    classification_basis: FCFClassificationBasis = FCFClassificationBasis.TOTAL_FCF
    forward_policy: ForwardPolicy = ForwardPolicy.DISPLAY_ONLY
    include_fcf_yield: bool = Field(default=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def _copy_existing_policy(cls, value: object) -> object:
        if isinstance(value, FCFEarningsGrowthPolicy):
            return {
                "historical_horizon": value.historical_horizon,
                "classification_basis": value.classification_basis,
                "forward_policy": value.forward_policy,
                "include_fcf_yield": value.include_fcf_yield,
            }
        return value

    def to_policy(self) -> FCFEarningsGrowthPolicy:
        """Return a fresh instance of the analyzer's existing policy dataclass."""
        return FCFEarningsGrowthPolicy(
            historical_horizon=self.historical_horizon,
            classification_basis=self.classification_basis,
            forward_policy=self.forward_policy,
            include_fcf_yield=self.include_fcf_yield,
        )


class FCFGrowthSelection(FrozenSelection):
    """Historical FCF/Earnings Growth request options, independent of Graham configs."""

    analysis_id: Literal["fcf_earnings_growth"] = "fcf_earnings_growth"
    method_id: Literal["reported_fcf_eps_cagr"] = "reported_fcf_eps_cagr"
    config_schema_version: Literal[1] = 1
    policy: FCFPolicySnapshot = Field(default_factory=FCFPolicySnapshot)
    currency: str = "USD"
    provider_id: Literal["sec_edgar"] = "sec_edgar"
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @field_validator("provider_id", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code.")
        return normalized

    def to_fcf_policy(self) -> FCFEarningsGrowthPolicy:
        """Return the existing policy type for explicit analyzer invocation."""
        return self.policy.to_policy()

    def to_fcf_config(self) -> FCFEarningsGrowthConfig:
        """Return the analyzer's complete per-call configuration for this snapshot."""
        return FCFEarningsGrowthConfig(
            policy=self.to_fcf_policy(), currency=self.currency, provider_id=self.provider_id
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


def parse_fcf_growth_selection(body: Mapping[str, object]) -> FCFGrowthSelection:
    """Parse a decoded FCF configuration body: policy, currency, provider, as_of and cache options."""
    if body.keys() - {"policy", "currency", "provider_id", "as_of", "use_cache"}:
        raise ValueError("FCF configuration contains unknown or reserved fields.")
    return FCFGrowthSelection.model_validate(body)
