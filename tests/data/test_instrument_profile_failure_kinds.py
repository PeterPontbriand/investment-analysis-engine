"""The provider failure kind is stored on the profile, identity and security-unit carriers and in the profile cache.

Each narrowed carrier records the kind of a typed provider failure and lets anything else propagate, so a defect is
never reported as a provider outage.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import update

from alembic import command
from src.config import ProjectSettings
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfile,
    InstrumentProfileCandidate,
    InstrumentProfileCapability,
    InstrumentProfileResolutionStatus,
    complete_security_unit_profile,
    compose_instrument_profile,
    profile_identity_resolution,
)
from src.data.instrument_profile_cache import CachedInstrumentProfileResolver
from src.data.repositories.instrument_profiles import (
    INSTRUMENT_PROFILE_SCHEMA_VERSION,
    SQLiteInstrumentProfileRepository,
)
from src.data.repositories.schema import instrument_profiles
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentity,
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    resolve_security_identity,
)
from src.data.security_unit import (
    SecurityUnitRequest,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
TTL = timedelta(days=30)


class _FailingIdentity:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        raise self.error


class _FailingKind:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        raise self.error


class _FailingUnit:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def resolve_security_unit(self, _request: SecurityUnitRequest) -> SecurityUnitResolution:
        raise self.error


class _MismatchedIdentity:
    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity:
        return SecurityIdentity(ticker="OTHER", provider_id=request.provider_id, resolved_at=NOW)


class _MismatchedKind:
    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence:
        return InstrumentKindEvidence(
            ticker="OTHER",
            kind=InstrumentKind.EQUITY,
            provider_value="EQUITY",
            provider_id=request.provider_id,
            resolved_at=NOW,
        )


class _Identity:
    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity:
        return SecurityIdentity(
            ticker=request.ticker,
            provider_id=request.provider_id,
            resolved_at=NOW,
            instrument_name="Coca-Cola",
            issuer_identifier="0000021344",
        )


def _typed(error_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind) -> BaseException:
    return error_type("synthetic failure", kind=kind, provider_id="yfinance")


@pytest.mark.parametrize("error_type", [DataFetchError, FinancialProviderError])
@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_identity_and_kind_diagnostics_record_the_kind_of_a_typed_failure(
    error_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind
) -> None:
    error = _typed(error_type, kind)
    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(InstrumentProfileCandidate("yfinance", _FailingIdentity(error)),),
        kind_candidate=InstrumentProfileCandidate("yfinance", _FailingKind(error)),
    )

    expected = ProviderFailureRecord(kind=kind, provider_id="yfinance")
    assert [item.status for item in profile.diagnostics] == [InstrumentProfileResolutionStatus.PROVIDER_ERROR] * 2
    assert [item.provider_failure for item in profile.diagnostics] == [expected, expected]
    assert profile_identity_resolution(profile).provider_failure == expected


def test_an_unclassified_typed_failure_records_no_kind() -> None:
    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(InstrumentProfileCandidate("yfinance", _FailingIdentity(DataFetchError("bare"))),),
        kind_candidate=None,
    )

    assert profile.diagnostics[0].status is InstrumentProfileResolutionStatus.PROVIDER_ERROR
    assert profile.diagnostics[0].provider_failure is None


def test_mismatched_evidence_is_an_unexpected_response_from_the_candidate() -> None:
    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(InstrumentProfileCandidate("yfinance", _MismatchedIdentity()),),
        kind_candidate=InstrumentProfileCandidate("yfinance", _MismatchedKind()),
    )

    expected = ProviderFailureRecord(kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id="yfinance")
    assert [item.provider_failure for item in profile.diagnostics] == [expected, expected]


@pytest.mark.parametrize("defect", [ValueError("defect"), KeyError("defect"), RuntimeError("defect")])
def test_a_defect_in_a_profile_provider_propagates(defect: BaseException) -> None:
    with pytest.raises(type(defect)):
        compose_instrument_profile(
            "KO",
            identity_candidates=(InstrumentProfileCandidate("yfinance", _FailingIdentity(defect)),),
            kind_candidate=None,
        )
    with pytest.raises(type(defect)):
        compose_instrument_profile(
            "KO",
            identity_candidates=(),
            kind_candidate=InstrumentProfileCandidate("yfinance", _FailingKind(defect)),
        )


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_the_standalone_identity_resolution_records_the_kind(kind: ProviderFailureKind) -> None:
    resolution = resolve_security_identity(
        _FailingIdentity(_typed(FinancialProviderError, kind)), SecurityIdentityRequest("KO", "yfinance")
    )

    assert resolution.status is IdentityResolutionStatus.PROVIDER_ERROR
    assert resolution.provider_failure == ProviderFailureRecord(kind=kind, provider_id="yfinance")


def test_a_defect_in_the_standalone_identity_resolution_propagates() -> None:
    with pytest.raises(RuntimeError):
        resolve_security_identity(_FailingIdentity(RuntimeError("defect")), SecurityIdentityRequest("KO", "yfinance"))


def test_a_failure_kind_requires_the_provider_error_status() -> None:
    record = ProviderFailureRecord(kind=ProviderFailureKind.NO_DATA, provider_id="yfinance")

    with pytest.raises(ValueError, match="provider_failure requires"):
        SecurityUnitResolution(SecurityUnitResolutionReason.MISSING_EVIDENCE, provider_failure=record)
    with pytest.raises(ValueError, match="provider_failure requires"):
        SecurityIdentityResolution(IdentityResolutionStatus.UNAVAILABLE, None, "message", record)


def _unit_request() -> SecurityUnitRequest:
    quote = ResolvedInput(
        field_name="current_price",
        value=50.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="latest_provider_quote",
        units="currency_per_share",
        currency="USD",
        provider_id="yfinance",
        provider_field="fast_info.last_price",
        retrieved_at=NOW,
    )
    return SecurityUnitRequest("KO", "sec_edgar", None, (), quote)


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_the_security_unit_completion_records_the_kind(kind: ProviderFailureKind) -> None:
    profile = InstrumentProfile(ticker="KO", identity=None, kind_evidence=None, diagnostics=())

    completed = complete_security_unit_profile(
        profile, _FailingUnit(_typed(FinancialProviderError, kind)), _unit_request()
    )

    expected = ProviderFailureRecord(kind=kind, provider_id="yfinance")
    assert completed.security_unit_resolution is not None
    assert completed.security_unit_resolution.reason is SecurityUnitResolutionReason.PROVIDER_ERROR
    assert completed.security_unit_resolution.provider_failure == expected
    assert completed.diagnostics[-1].capability is InstrumentProfileCapability.SECURITY_UNIT
    assert completed.diagnostics[-1].provider_failure == expected


def test_a_defect_in_the_security_unit_completion_propagates() -> None:
    profile = InstrumentProfile(ticker="KO", identity=None, kind_evidence=None, diagnostics=())

    with pytest.raises(ValueError, match="defect"):
        complete_security_unit_profile(profile, _FailingUnit(ValueError("defect")), _unit_request())


# --- profile cache -----------------------------------------------------------------------------------------------


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'profile_kinds.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def repository(database: SQLiteDatabase) -> SQLiteInstrumentProfileRepository:
    return SQLiteInstrumentProfileRepository(database, clock=lambda: NOW)


def _anchored_candidates(
    kind_error: BaseException,
) -> tuple[tuple[InstrumentProfileCandidate, ...], InstrumentProfileCandidate]:
    return (InstrumentProfileCandidate("yfinance", _Identity()),), InstrumentProfileCandidate(
        "yfinance", _FailingKind(kind_error)
    )


def _set_version(database: SQLiteDatabase, version: int) -> None:
    with database.transaction() as connection:
        connection.execute(update(instrument_profiles).values(schema_version=version))


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_the_profile_cache_payload_round_trips_the_kind(
    repository: SQLiteInstrumentProfileRepository, kind: ProviderFailureKind
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, kind))
    live = resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    reused = resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    expected = ProviderFailureRecord(kind=kind, provider_id="yfinance")
    assert [item.provider_failure for item in live.diagnostics if item.provider_failure] == [expected]
    assert reused.diagnostics[:-1] == live.diagnostics
    assert reused.diagnostics[1].provider_failure == expected
    assert any(item.capability is InstrumentProfileCapability.CACHE for item in reused.diagnostics)
    record = repository.get("KO")
    assert record is not None
    assert record.schema_version == INSTRUMENT_PROFILE_SCHEMA_VERSION == 2


def test_a_version_one_record_is_not_reused_on_the_fresh_path(
    database: SQLiteDatabase, repository: SQLiteInstrumentProfileRepository
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, ProviderFailureKind.NO_DATA))
    resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    _set_version(database, 1)

    calls = _CountingIdentity()
    result = resolver.resolve(
        "ko",
        identity_candidates=(InstrumentProfileCandidate("yfinance", calls),),
        kind_candidate=None,
    )

    assert calls.calls == 1
    assert not any(item.capability is InstrumentProfileCapability.CACHE for item in result.diagnostics)
    record = repository.get("KO")
    assert record is not None
    assert record.schema_version == INSTRUMENT_PROFILE_SCHEMA_VERSION


def test_a_version_one_record_is_not_reused_on_the_fail_open_path(
    database: SQLiteDatabase, repository: SQLiteInstrumentProfileRepository
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, ProviderFailureKind.NO_DATA))
    resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    _set_version(database, 1)

    anchorless = _AnchorlessIdentity()
    result = resolver.resolve(
        "ko", identity_candidates=(InstrumentProfileCandidate("yfinance", anchorless),), kind_candidate=None
    )

    assert anchorless.calls == 1
    assert result.identity is not None
    assert result.identity.issuer_identifier is None
    assert not any(item.capability is InstrumentProfileCapability.CACHE for item in result.diagnostics)


def test_a_current_record_still_falls_open_to_the_stored_profile(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, ProviderFailureKind.NO_DATA))
    resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    result = resolver.resolve(
        "ko",
        identity_candidates=(InstrumentProfileCandidate("yfinance", _AnchorlessIdentity()),),
        kind_candidate=None,
        force_refresh=True,
    )

    assert result.identity is not None
    assert result.identity.issuer_identifier == "0000021344"
    assert result.diagnostics[-1].capability is InstrumentProfileCapability.CACHE
    assert result.diagnostics[-1].status is InstrumentProfileResolutionStatus.UNAVAILABLE


class _CountingIdentity(_Identity):
    def __init__(self) -> None:
        self.calls = 0

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity:
        self.calls += 1
        return super().resolve_security_identity(request)


class _AnchorlessIdentity:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity:
        self.calls += 1
        return SecurityIdentity(
            ticker=request.ticker, provider_id=request.provider_id, resolved_at=NOW, instrument_name="Coca-Cola"
        )
