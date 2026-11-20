"""Fake providers and stored profiles for the tests of the instrument profile operations.

The lookup builds its providers inside the operation, so a test replaces them with :func:`use_providers`; no test
reaches a real provider. :func:`store_profile` stores a profile the way an earlier analysis would have.
"""

from datetime import UTC, datetime, timedelta

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfileCandidate,
    QuoteCurrencyRequest,
)
from investment_analysis_engine.data.instrument_profile_cache import CachedInstrumentProfileResolver
from investment_analysis_engine.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from investment_analysis_engine.data.repositories.schema import instrument_profiles
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.security_identity import SecurityIdentity, SecurityIdentityRequest

OLD = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
"""A refresh time far older than the freshness window."""

ANCHOR = "0000021344"
"""The issuer identifier the fake SEC adapter reports."""


class FakeSec:
    """The SEC adapter's identity capability: an anchored identity, nothing, or a failure."""

    def __init__(self, *, identity: bool = True, failure: ProviderFailureKind | None = None) -> None:
        self.identity = identity
        self.failure = failure
        self.calls = 0

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        if self.failure is not None:
            raise DataFetchError("down", kind=self.failure, provider_id=request.provider_id)
        if not self.identity:
            return None
        return SecurityIdentity(
            ticker=request.ticker,
            provider_id=request.provider_id,
            resolved_at=datetime.now(UTC),
            instrument_name="Coca-Cola Co",
            issuer_identifier=ANCHOR,
        )


class FakeYahoo:
    """The Yahoo client: an unanchored identity, the kind and the quote currency."""

    def __init__(self, *, identity: bool = True, failure: ProviderFailureKind | None = None) -> None:
        self.identity = identity
        self.failure = failure
        self.calls = 0

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        if self.failure is not None:
            raise DataFetchError("down", kind=self.failure, provider_id=request.provider_id)
        if not self.identity:
            return None
        return SecurityIdentity(
            ticker=request.ticker,
            provider_id=request.provider_id,
            resolved_at=datetime.now(UTC),
            instrument_name="The Coca-Cola Company",
            listing_venue="NYSE",
        )

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        return InstrumentKindEvidence(
            ticker=request.ticker,
            kind=InstrumentKind.EQUITY,
            provider_value="EQUITY",
            provider_id=request.provider_id,
            resolved_at=datetime.now(UTC),
        )

    def resolve_quote_currency(self, _request: QuoteCurrencyRequest) -> str | None:
        return "USD"


def profile_context(settings: ProjectSettings, *, sec_identity: bool = True) -> ApplicationContext:
    """Return a context over ``settings`` with an SEC identity set up, or with none when ``sec_identity`` is false."""
    agent = "Someone someone@example.com" if sec_identity else None
    return ApplicationContext(settings=ProjectSettings(**(settings.model_dump() | {"sec_user_agent": agent})))


def use_providers(monkeypatch: pytest.MonkeyPatch, sec: FakeSec, yahoo: FakeYahoo) -> None:
    """Make the lookup use ``sec`` and ``yahoo`` as its providers."""
    monkeypatch.setattr(
        "investment_analysis_engine.application.instrument_profiles.build_sec_production_provider", lambda _context: sec
    )
    monkeypatch.setattr("investment_analysis_engine.application.instrument_profiles.YFinanceClient", lambda: yahoo)


def store_profile(
    context: ApplicationContext, *, refreshed_at: datetime, anchor: str = ANCHOR, ticker: str = "KO"
) -> None:
    """Store the fake providers' profile of ``ticker``, refreshed at ``refreshed_at``, under ``anchor``."""
    database = SQLiteDatabase(context.settings)
    try:
        resolver = CachedInstrumentProfileResolver(
            SQLiteInstrumentProfileRepository(database, clock=lambda: refreshed_at),
            ttl=timedelta(days=30),
            clock=lambda: refreshed_at,
        )
        yahoo = InstrumentProfileCandidate("yfinance", FakeYahoo())
        resolver.resolve(
            ticker,
            identity_candidates=(InstrumentProfileCandidate("sec_edgar", FakeSec()), yahoo),
            kind_candidate=yahoo,
        )
        if anchor != ANCHOR:
            with database.transaction() as connection:
                connection.execute(instrument_profiles.update().values(identity_anchor=anchor))
    finally:
        database.close()


def set_profile_version(context: ApplicationContext, version: int) -> None:
    """Write ``version`` as the payload version of every stored profile."""
    database = SQLiteDatabase(context.settings)
    try:
        with database.transaction() as connection:
            connection.execute(instrument_profiles.update().values(schema_version=version))
    finally:
        database.close()
