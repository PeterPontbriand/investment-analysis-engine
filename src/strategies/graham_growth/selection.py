"""Graham growth-value's immutable workspace selection snapshot."""

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, StrictFloat, field_validator, model_validator

from src.analysis.base_analyzer import AnalysisContext
from src.data.instrument_profile import InstrumentProfile
from src.strategies.graham_growth.config import GrahamGrowthConfig, GrahamGrowthEPSBasis
from src.strategies.graham_growth.vocabulary import ANALYSIS_ID, METHOD_ID, AnalysisId, MethodId
from src.workspace.selection_base import (
    CLI_QUOTE_PROVIDERS,
    CLI_SECURITY_PROVIDERS,
    FrozenSelection,
    config_object,
)


class GrahamGrowthSelection(FrozenSelection):
    """Graham growth-value selection requiring explicit growth and AAA yield percentages."""

    analysis_id: AnalysisId = ANALYSIS_ID
    method_id: MethodId = METHOD_ID
    config_schema_version: Literal[1] = 1
    security_provider_id: str = "sec_edgar"
    quote_provider_id: str | None = None
    eps_basis: GrahamGrowthEPSBasis | None = None
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    expected_growth: StrictFloat
    aaa_yield_override: StrictFloat
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    @field_validator("security_provider_id")
    @classmethod
    def _restrict_security_provider(cls, value: str) -> str:
        """Normalize and restrict the security-fact provider to CLI-supported choices."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Provider identifier must not be blank.")
        if normalized not in CLI_SECURITY_PROVIDERS:
            raise ValueError(
                f"Unsupported security provider {normalized!r}; supported providers are 'sec_edgar' and 'massive'."
            )
        return normalized

    @field_validator("quote_provider_id")
    @classmethod
    def _restrict_quote_provider(cls, value: str | None) -> str | None:
        """Normalize and restrict an explicit quote provider to CLI-supported choices."""
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Provider identifier must not be blank.")
        if normalized not in CLI_QUOTE_PROVIDERS:
            raise ValueError(
                f"Unsupported quote provider {normalized!r}; supported providers are 'yfinance' and 'massive'."
            )
        return normalized

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
        """Resolve the effective EPS basis/quote provider by constructing this method's own config.

        ``GrahamGrowthConfig.validate_method`` is the single definition of Graham Growth's
        entire accept/default rule; this Selection validates by delegating to it rather than
        reimplementing the rule, so the CLI-direct and ``--save-run``/workspace entry points
        cannot silently diverge.
        """
        config = self.to_graham_growth_config()
        object.__setattr__(self, "eps_basis", config.eps_basis)
        object.__setattr__(self, "quote_provider_id", config.quote_provider_id)
        return self

    def to_graham_growth_config(self) -> GrahamGrowthConfig:
        """Return the existing config without deriving assumptions or calculation policy."""
        return GrahamGrowthConfig(
            security_provider_id=self.security_provider_id,
            quote_provider_id=self.quote_provider_id,
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


def parse_graham_growth_selection(body: Mapping[str, object]) -> GrahamGrowthSelection:
    """Parse a decoded configuration body that holds only an optional ``config`` object."""
    return GrahamGrowthSelection.model_validate(config_object(body))
