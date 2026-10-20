"""The provider failure kind is stored on the profile, identity and security-unit carriers and in the profile cache.

Each narrowed carrier records the kind of a typed provider failure and lets anything else propagate, so a defect is
never reported as a provider outage.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.financial.provenance import ResolvedInput, SourceKind
from investment_analysis_engine.data.instrument_profile import (
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
from investment_analysis_engine.data.instrument_profile_cache import CachedInstrumentProfileResolver
from investment_analysis_engine.data.repositories.instrument_profiles import (
    INSTRUMENT_PROFILE_SCHEMA_VERSION,
    SQLiteInstrumentProfileRepository,
)
from investment_analysis_engine.data.repositories.schema import instrument_profiles
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentity,
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    resolve_security_identity,
)
from investment_analysis_engine.data.security_unit import (
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
def repository(migrated_database: SQLiteDatabase) -> SQLiteInstrumentProfileRepository:
    return SQLiteInstrumentProfileRepository(migrated_database, clock=lambda: NOW)


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
    assert record.schema_version == INSTRUMENT_PROFILE_SCHEMA_VERSION == 3


def test_a_version_one_record_is_not_reused_on_the_fresh_path(
    migrated_database: SQLiteDatabase, repository: SQLiteInstrumentProfileRepository
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, ProviderFailureKind.NO_DATA))
    resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    _set_version(migrated_database, 1)

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
    migrated_database: SQLiteDatabase, repository: SQLiteInstrumentProfileRepository
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates, kind_candidate = _anchored_candidates(_typed(DataFetchError, ProviderFailureKind.NO_DATA))
    resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    _set_version(migrated_database, 1)

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


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        ((ProviderFailureKind.NO_DATA, ProviderFailureKind.UNREACHABLE), ProviderFailureKind.UNREACHABLE),
        ((ProviderFailureKind.UNREACHABLE, ProviderFailureKind.NO_DATA), ProviderFailureKind.UNREACHABLE),
        (
            (ProviderFailureKind.NO_DATA, ProviderFailureKind.UNEXPECTED_RESPONSE),
            ProviderFailureKind.UNEXPECTED_RESPONSE,
        ),
        (
            (ProviderFailureKind.UNEXPECTED_RESPONSE, ProviderFailureKind.NO_DATA),
            ProviderFailureKind.UNEXPECTED_RESPONSE,
        ),
        ((ProviderFailureKind.NO_DATA, ProviderFailureKind.NO_DATA), ProviderFailureKind.NO_DATA),
    ],
)
def test_several_failed_identity_candidates_report_the_highest_precedence_kind(
    kinds: tuple[ProviderFailureKind, ProviderFailureKind], expected: ProviderFailureKind
) -> None:
    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(
            InstrumentProfileCandidate(
                "first", _FailingIdentity(DataFetchError("a", kind=kinds[0], provider_id="first"))
            ),
            InstrumentProfileCandidate(
                "second", _FailingIdentity(DataFetchError("b", kind=kinds[1], provider_id="second"))
            ),
        ),
        kind_candidate=None,
    )

    failure = profile_identity_resolution(profile).provider_failure

    assert failure is not None
    assert failure.kind is expected


def test_equal_precedence_keeps_the_first_candidate() -> None:
    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(
            InstrumentProfileCandidate(
                "first", _FailingIdentity(DataFetchError("a", kind=ProviderFailureKind.NO_DATA, provider_id="first"))
            ),
            InstrumentProfileCandidate(
                "second", _FailingIdentity(DataFetchError("b", kind=ProviderFailureKind.NO_DATA, provider_id="second"))
            ),
        ),
        kind_candidate=None,
    )

    failure = profile_identity_resolution(profile).provider_failure

    assert failure is not None
    assert failure.provider_id == "first"
