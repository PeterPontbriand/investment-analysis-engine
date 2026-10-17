"""The ``provider_failure`` element: which inputs a provider failed and the single code that reports them.

The same element is carried by the failure envelope and by every document that reports an analysis outcome.
This is a leaf module: it imports only ``investment_analysis_engine.core``, the standard library and pydantic.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.core.failure_codes import PROVIDER_FAILURE_CODES, FailureReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind


class ProviderFailureInput(BaseModel):
    """One failed input: which provider failed it and what the adapter observed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: str | None = Field(
        description="The strategy input the failure was recorded against; null when the failure was raised."
    )
    provider_id: str = Field(description="The provider that failed.")
    kind: ProviderFailureKind


class ProviderFailure(BaseModel):
    """Why an analysis outcome is a provider failure: one of four codes and the inputs that caused it.

    The same element is carried by the failure envelope and by every document that reports an analysis
    outcome. ``reason_code`` is the single code derived from the kinds in ``inputs``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_code: FailureReasonCode
    inputs: tuple[ProviderFailureInput, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _provider_code(self) -> Self:
        """Require one of the four provider failure codes."""
        if self.reason_code not in PROVIDER_FAILURE_CODES:
            raise ValueError(f"reason_code {self.reason_code.value!r} is not a provider failure code.")
        return self


__all__ = ["ProviderFailure", "ProviderFailureInput"]
