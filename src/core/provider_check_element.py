"""The ``provider_check`` element: what a test request found for each provider a failure implicates.

The element sits beside the ``provider_failure`` element in the failure envelope and in every strategy document, and
ends the refresh summary. It is null when there is nothing to report and otherwise one entry per provider. The
verdict is never stored: a document carries it only when a command ran the check, and a replay writes null.

This is a leaf module: it imports only ``src.core``, the standard library and pydantic. The probe that produces the
verdicts lives in ``src.data``, which this package may not import, so the six values are declared here and a test
pins them equal to the probe's.
"""

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.core.provider_failure_element import ProviderFailure


class ProviderCheckVerdict(StrEnum):
    """What a test request to a provider found: five provider conditions, or that nothing was checked."""

    HEALTHY = "healthy"
    UNREACHABLE = "unreachable"
    RATE_LIMITED = "rate_limited"
    UNEXPECTED_RESPONSE = "unexpected_response"
    NO_DATA = "no_data"
    NOT_CHECKED = "not_checked"


class ProviderCheckItem(BaseModel):
    """The verdict for one provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(description="The provider the test request went to.")
    verdict: ProviderCheckVerdict


def require_unique_providers(items: Iterable[ProviderCheckItem] | None) -> None:
    """Raise ``ValueError`` when two entries name the same provider."""
    if items is None:
        return
    names = [item.provider_id for item in items]
    if len(names) != len(set(names)):
        raise ValueError("provider_check names a provider more than once.")


def require_check_matches_failure(
    provider_failure: ProviderFailure | None, provider_check: tuple[ProviderCheckItem, ...] | None
) -> None:
    """Raise ``ValueError`` unless ``provider_check`` is null or names exactly the providers ``provider_failure`` names.

    A check is non-null only beside a non-null ``provider_failure``, and then it has one entry per provider that
    element names, no more and no fewer.
    """
    if provider_check is None:
        return
    if provider_failure is None:
        raise ValueError("provider_check is set only when provider_failure is set.")
    require_unique_providers(provider_check)
    implicated = {item.provider_id for item in provider_failure.inputs}
    checked = {item.provider_id for item in provider_check}
    if implicated != checked:
        raise ValueError("provider_check must name exactly the providers provider_failure names.")


__all__ = [
    "ProviderCheckItem",
    "ProviderCheckVerdict",
    "require_check_matches_failure",
    "require_unique_providers",
]
