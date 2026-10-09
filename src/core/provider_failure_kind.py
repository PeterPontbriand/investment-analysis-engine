"""The three kinds of provider failure.

This is a leaf module: it imports nothing from the application, so the data adapters, the classifier and the
failure documents can all depend on it without a cycle.
"""

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


__all__ = ["ProviderFailureKind", "require_provider_identity"]
