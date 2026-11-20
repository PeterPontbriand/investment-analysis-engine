"""The instrument profile operations: read the stored profile of a ticker, and look it up with the data providers.

Both operations return the same :class:`StoredInstrumentProfile`. The read never contacts a data provider; the
lookup resolves the profile exactly as an analysis does, through the durable profile cache.
"""

from typing import ClassVar

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.providers import (
    build_sec_production_provider,
    production_instrument_profile_cache,
)
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError, InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.instrument_profile import (
    InstrumentProfile,
    InstrumentProfileCapability,
    profile_identity_resolution,
)
from investment_analysis_engine.data.instrument_profile_cache import StoredInstrumentProfile, read_stored_profile
from investment_analysis_engine.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.presentation import provider_display_name
from investment_analysis_engine.strategies._shared.profile import compose_production_profile

_LOOKUP_MESSAGES = {
    ProviderFailureKind.UNREACHABLE: "Unable to look up {ticker}: {provider} did not serve the request.",
    ProviderFailureKind.RATE_LIMITED: "Unable to look up {ticker}: {provider} is limiting requests.",
    ProviderFailureKind.UNEXPECTED_RESPONSE: (
        "Unable to look up {ticker}: {provider} answered in a form the application does not read."
    ),
    ProviderFailureKind.NO_DATA: "Unable to look up {ticker}: {provider} returned no data for it.",
}
"""One message for each kind of provider failure a lookup reports; the same wording as an analysis, for a lookup."""

_NOT_CONFIGURED_MESSAGE = "Looking up an instrument profile needs an SEC identity, and none is set up."
"""The message of a lookup attempted before an SEC identity is set up."""


class InstrumentProfileNotFoundError(ValueError):
    """No current instrument profile is stored for the ticker."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.INSTRUMENT_PROFILE_NOT_FOUND


def _ticker(value: str) -> str:
    """Return ``value`` as a ticker, trimmed and upper-cased.

    Raises:
        InvalidParameterError: If ``value`` is blank.
    """
    try:
        return normalize_ticker(value)
    except ValueError:
        raise InvalidParameterError("ticker must not be empty.", parameters=("ticker",)) from None


def get_instrument_profile(context: ApplicationContext, ticker: str) -> StoredInstrumentProfile:
    """Return the ticker's current stored instrument profile, however old it is; no provider is contacted.

    A profile stored under another payload version counts as absent, and a profile retired by a ticker reuse is
    never returned.

    Args:
        context: What the operation needs from its caller.
        ticker: The ticker as the caller has it; it is trimmed and upper-cased.

    Raises:
        InvalidParameterError: If ``ticker`` is blank.
        InstrumentProfileNotFoundError: If no current profile is stored for the ticker.
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision.
    """
    normalized = _ticker(ticker)
    with open_database(context) as database:
        stored = read_stored_profile(SQLiteInstrumentProfileRepository(database), normalized)
    if stored is None:
        raise InstrumentProfileNotFoundError(f"No instrument profile is stored for {normalized}.")
    return stored


def _no_identity(ticker: str, profile: InstrumentProfile) -> DataFetchError:
    """Return the failure of a lookup in which no provider identified the ticker.

    The failure is the highest-precedence provider failure the lookup observed; when every provider answered with
    nothing, it is ``no_data``, recorded against the last provider asked.
    """
    failure = profile_identity_resolution(profile).provider_failure
    if failure is not None:
        kind, provider_id = failure.kind, failure.provider_id
    else:
        asked = [
            item for item in profile.diagnostics if item.capability is InstrumentProfileCapability.SECURITY_IDENTITY
        ]
        kind, provider_id = ProviderFailureKind.NO_DATA, asked[-1].provider_id
    message = _LOOKUP_MESSAGES[kind].format(ticker=ticker, provider=provider_display_name(provider_id))
    return DataFetchError(message, kind=kind, provider_id=provider_id)


def lookup_instrument_profile(context: ApplicationContext, ticker: str) -> StoredInstrumentProfile:
    """Resolve the ticker's instrument profile as an analysis does, and return it.

    The profile comes from the durable cache when it is within the freshness window and otherwise from the data
    providers. A result is stored only when it has an identity anchor, as the cache stores it for an analysis; one
    without an anchor is returned with the time its identity was resolved and is not stored. When a provider cannot
    confirm an anchor and a profile is already stored, the stored profile is returned, as an analysis uses it.

    Args:
        context: What the operation needs from its caller.
        ticker: The ticker as the caller has it; it is trimmed and upper-cased.

    Raises:
        InvalidParameterError: If ``ticker`` is blank.
        AnalysisConfigurationError: If no SEC identity is set up.
        DataFetchError: If no provider identified the ticker; its kind is the provider failure observed, or
            ``no_data`` when every provider answered with nothing.
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision.
    """
    normalized = _ticker(ticker)
    try:
        primary = build_sec_production_provider(context)
    except AnalysisConfigurationError:
        raise AnalysisConfigurationError(_NOT_CONFIGURED_MESSAGE) from None
    with open_database(context) as database:
        profile = compose_production_profile(
            normalized,
            primary_provider=primary,
            yahoo_provider=YFinanceClient(),
            profile_cache=production_instrument_profile_cache(context, database, clock=utc_now),
        )
        stored = read_stored_profile(SQLiteInstrumentProfileRepository(database), normalized)
    identity = profile.identity
    if identity is None:
        raise _no_identity(normalized, profile)
    if stored is not None:
        return StoredInstrumentProfile(profile, stored.refreshed_at)
    return StoredInstrumentProfile(profile, identity.resolved_at)


__all__ = [
    "InstrumentProfileNotFoundError",
    "get_instrument_profile",
    "lookup_instrument_profile",
]
