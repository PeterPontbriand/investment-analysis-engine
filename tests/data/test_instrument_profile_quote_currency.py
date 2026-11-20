"""The quote currency of an instrument profile: where it comes from, how it is stored and when it is absent."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfileCandidate,
    QuoteCurrencyRequest,
    compose_instrument_profile,
)
from investment_analysis_engine.data.instrument_profile_cache import (
    CachedInstrumentProfileResolver,
    read_stored_profile,
)
from investment_analysis_engine.data.repositories.instrument_profiles import (
    INSTRUMENT_PROFILE_SCHEMA_VERSION,
    SQLiteInstrumentProfileRepository,
)
from investment_analysis_engine.data.repositories.schema import instrument_profiles
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID, YFinanceClient

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
TTL = timedelta(days=30)


class _Provider:
    """A provider with identity, kind and quote-currency capabilities, each configurable."""

    def __init__(self, currency: str | None, *, fails: bool = False) -> None:
        self.currency = currency
        self.fails = fails
        self.requests: list[QuoteCurrencyRequest] = []

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        return SecurityIdentity(
            ticker=request.ticker,
            provider_id=request.provider_id,
            resolved_at=NOW,
            instrument_name="Coca-Cola",
            issuer_identifier="0000021344",
        )

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        return InstrumentKindEvidence(
            ticker=request.ticker,
            kind=InstrumentKind.EQUITY,
            provider_value="EQUITY",
            provider_id=request.provider_id,
            resolved_at=NOW,
        )

    def resolve_quote_currency(self, request: QuoteCurrencyRequest) -> str | None:
        self.requests.append(request)
        if self.fails:
            raise DataFetchError("offline", provider_id=request.provider_id)
        return self.currency


class _KindOnlyProvider:
    """A provider that offers no quote-currency capability."""

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        return None


@pytest.fixture
def repository(migrated_database: SQLiteDatabase) -> SQLiteInstrumentProfileRepository:
    return SQLiteInstrumentProfileRepository(migrated_database, clock=lambda: NOW)


def _candidates(provider: object) -> tuple[tuple[InstrumentProfileCandidate, ...], InstrumentProfileCandidate]:
    candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, provider)
    return (candidate,), candidate


def test_the_profile_carries_the_currency_the_kind_provider_reports() -> None:
    provider = _Provider("USD")
    identity_candidates, kind_candidate = _candidates(provider)

    profile = compose_instrument_profile("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert profile.quote_currency == "USD"
    assert provider.requests == [QuoteCurrencyRequest("KO", YFINANCE_PROVIDER_ID)]


def test_a_currency_is_kept_as_the_provider_writes_it() -> None:
    identity_candidates, kind_candidate = _candidates(_Provider(" GBp "))

    profile = compose_instrument_profile("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert profile.quote_currency == "GBp"


@pytest.mark.parametrize(
    "provider",
    [_Provider(None), _Provider("USD", fails=True), _KindOnlyProvider()],
    ids=["none", "fails", "no-capability"],
)
def test_the_currency_is_absent_without_a_diagnostic_when_the_provider_gives_none(provider: object) -> None:
    identity_candidates, kind_candidate = _candidates(provider)
    without = compose_instrument_profile("ko", identity_candidates=identity_candidates, kind_candidate=None)

    profile = compose_instrument_profile("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert profile.quote_currency is None
    assert [item.capability for item in profile.diagnostics][: len(without.diagnostics)] == [
        item.capability for item in without.diagnostics
    ]


def test_the_currency_is_stored_with_the_profile_and_read_back(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    identity_candidates, kind_candidate = _candidates(_Provider("USD"))
    CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW).resolve(
        "ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate
    )

    stored = read_stored_profile(repository, "ko")

    assert stored is not None
    assert (stored.profile.quote_currency, stored.refreshed_at) == ("USD", NOW)
    assert read_stored_profile(repository, "KO") == stored


def test_a_profile_stored_under_another_version_counts_as_absent(
    migrated_database: SQLiteDatabase, repository: SQLiteInstrumentProfileRepository
) -> None:
    identity_candidates, kind_candidate = _candidates(_Provider("USD"))
    CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW).resolve(
        "ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate
    )
    with migrated_database.transaction() as connection:
        connection.execute(instrument_profiles.update().values(schema_version=INSTRUMENT_PROFILE_SCHEMA_VERSION - 1))

    assert read_stored_profile(repository, "KO") is None


def test_a_profile_that_was_never_stored_is_absent(repository: SQLiteInstrumentProfileRepository) -> None:
    assert read_stored_profile(repository, "KO") is None


def test_yahoo_reports_the_currency_from_metadata_already_fetched() -> None:
    with patch("investment_analysis_engine.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"quoteType": "EQUITY", "currency": "GBp"}
        client = YFinanceClient(clock=lambda: NOW)
        before = client.resolve_quote_currency(QuoteCurrencyRequest("FLSW", YFINANCE_PROVIDER_ID))
        client.resolve_instrument_kind(InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID))
        after = client.resolve_quote_currency(QuoteCurrencyRequest("FLSW", YFINANCE_PROVIDER_ID))

    assert (before, after) == (None, "GBp")
    assert mock_ticker.call_count == 1


@pytest.mark.parametrize("raw_value", [None, "", "   ", 3])
def test_yahoo_missing_or_malformed_currency_is_absent(raw_value: object) -> None:
    with patch("investment_analysis_engine.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"quoteType": "EQUITY", "currency": raw_value}
        client = YFinanceClient(clock=lambda: NOW)
        client.resolve_instrument_kind(InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID))

        assert client.resolve_quote_currency(QuoteCurrencyRequest("FLSW", YFINANCE_PROVIDER_ID)) is None


def test_yahoo_answers_nothing_for_another_provider_or_a_failed_fetch() -> None:
    with patch("investment_analysis_engine.data.yfinance.client.yf.Ticker", side_effect=RuntimeError("offline")):
        client = YFinanceClient(clock=lambda: NOW)
        with pytest.raises(DataFetchError):
            client.resolve_instrument_kind(InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID))

        assert client.resolve_quote_currency(QuoteCurrencyRequest("FLSW", YFINANCE_PROVIDER_ID)) is None
        assert client.resolve_quote_currency(QuoteCurrencyRequest("FLSW", "sec_edgar")) is None
