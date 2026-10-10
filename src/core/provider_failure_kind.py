"""The three kinds of provider failure.

This is a leaf module: it imports nothing from the application, so the data adapters, the classifier and the
failure documents can all depend on it without a cycle.
"""

from dataclasses import dataclass, replace
from enum import StrEnum


class ProviderFailureKind(StrEnum):
    """What a provider failure was, as observed by the adapter.

    ``UNREACHABLE``: the service did not serve the request (DNS, connection, timeout, throttling or blocking,
    server errors). ``UNEXPECTED_RESPONSE``: the service answered, but not in the form the adapter reads.
    ``NO_DATA``: the service answered correctly and has nothing for this request.
    """

    UNREACHABLE = "unreachable"
    UNEXPECTED_RESPONSE = "unexpected_response"
    NO_DATA = "no_data"


def require_provider_identity(kind: ProviderFailureKind | None, provider_id: str | None) -> None:
    """Reject a kind without the provider that failed, and a provider identity that is blank."""
    if provider_id is not None and not provider_id.strip():
        raise ValueError("provider_id must not be blank.")
    if kind is not None and provider_id is None:
        raise ValueError("A provider failure kind requires the provider_id that failed.")


@dataclass(frozen=True)
class ProviderFailureRecord:
    """A provider failure as stored beside a ``PROVIDER_ERROR`` outcome: what was observed and which provider.

    ``input`` names the strategy input the failure was recorded against; it is ``None`` until a strategy's input
    assembly records it, and for a failure of an optional capability such as the instrument profile.
    """

    kind: ProviderFailureKind
    provider_id: str
    input: str | None = None

    def __post_init__(self) -> None:
        """Reject a blank provider or input name."""
        require_provider_identity(self.kind, self.provider_id)
        if self.input is not None and not self.input.strip():
            raise ValueError("input must not be blank.")

    def for_input(self, input_name: str) -> "ProviderFailureRecord":
        """Return this failure recorded against the strategy input ``input_name``."""
        return replace(self, input=input_name)


__all__ = ["ProviderFailureKind", "ProviderFailureRecord", "require_provider_identity"]
