"""The ``ian health --json`` document: one entry per checked provider.

It is a report, as the maintenance report of ``db status`` is: it is written whether or not every check passed, and
it is not the failure envelope. The exit status says whether every check passed; the document says what each check
found. It carries facts and no instructions.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HealthVerdict = Literal[
    "ok", "unreachable", "rate_limited", "unexpected_response", "no_data", "not_configured", "failed"
]
"""The seven outcomes of a provider check."""


class ProviderHealthEntry(BaseModel):
    """The outcome of the check of one provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(description="The provider's stable identity, as `--provider` names it.")
    verdict: HealthVerdict = Field(
        description=(
            "ok: every request answered in the shape the adapter reads. unreachable, rate_limited, "
            "unexpected_response and no_data: the provider failed in that way. not_configured: SEC access is not "
            "set up, so the check could not run. failed: an unexpected error inside the check."
        )
    )
    probe: str = Field(description="What the check requests; a sentence for people, not stable.")
    elapsed_seconds: float = Field(description="Wall-clock seconds the check took, rounded to hundredths.")
    detail: str | None = Field(
        description="The failure detail, a sentence for people that is not stable; null when the check passed."
    )


class ProviderHealthDocument(BaseModel):
    """The whole ``health --json`` output, in the order the providers were checked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    providers: tuple[ProviderHealthEntry, ...]
