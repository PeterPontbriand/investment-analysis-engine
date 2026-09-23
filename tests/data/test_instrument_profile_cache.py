"""Verify durable freshness/refresh/ticker-reuse caching over live composition."""

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from src.config import ProjectSettings
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfileCandidate,
    InstrumentProfileCapability,
    InstrumentProfileResolutionStatus,
)
from src.data.instrument_profile_cache import CachedInstrumentProfileResolver
from src.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
STALE = NOW + timedelta(days=31)
TTL = timedelta(days=30)


class _IdentityProvider:
    """Identity provider spy with one configured, replaceable response."""

    def __init__(self, identity: SecurityIdentity | None) -> None:
        self.identity = identity
        self.calls = 0

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        return self.identity


class _KindProvider:
    """Instrument-kind provider spy with one configured, replaceable response."""

    def __init__(self, evidence: InstrumentKindEvidence | None) -> None:
        self.evidence = evidence
        self.calls = 0

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        self.calls += 1
        return self.evidence


def _identity(anchor: str | None, *, resolved_at: datetime = NOW) -> SecurityIdentity:
    return SecurityIdentity(
        ticker="KO",
        provider_id="yfinance",
        resolved_at=resolved_at,
        instrument_name="Coca-Cola",
        issuer_identifier=anchor,
    )


def _kind_evidence(*, resolved_at: datetime = NOW) -> InstrumentKindEvidence:
    return InstrumentKindEvidence(
        ticker="KO",
        kind=InstrumentKind.EQUITY,
        provider_value="EQUITY",
        provider_id="yfinance",
        resolved_at=resolved_at,
    )


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'instrument_profile_cache.sqlite3').as_posix()}"
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


def _candidates(
    identity_provider: _IdentityProvider, kind_provider: _KindProvider
) -> tuple[tuple[InstrumentProfileCandidate, ...], InstrumentProfileCandidate]:
    return (InstrumentProfileCandidate("yfinance", identity_provider),), InstrumentProfileCandidate(
        "yfinance", kind_provider
    )


def test_first_resolution_with_an_anchor_persists_and_returns_the_live_profile(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    identity_provider = _IdentityProvider(_identity("0000021344"))
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)

    profile = resolver.resolve("ko", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert identity_provider.calls == 1
    assert profile.identity is not None
    assert profile.identity.issuer_identifier == "0000021344"
    assert not any(item.capability is InstrumentProfileCapability.CACHE for item in profile.diagnostics)

    record = repository.get("KO")
    assert record is not None
    assert record.identity_anchor == "0000021344"


def test_fresh_reuse_returns_a_decoded_profile_without_calling_the_provider(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    identity_provider = _IdentityProvider(_identity("0000021344"))
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    assert identity_provider.calls == 1

    profile = resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert identity_provider.calls == 1  # no second live call
    assert kind_provider.calls == 1
    assert profile.identity is not None
    assert profile.identity.issuer_identifier == "0000021344"
    assert profile.kind_evidence is not None
    assert profile.kind_evidence.kind is InstrumentKind.EQUITY
    cache_diagnostics = [item for item in profile.diagnostics if item.capability is InstrumentProfileCapability.CACHE]
    assert len(cache_diagnostics) == 1
    assert cache_diagnostics[0].status is InstrumentProfileResolutionStatus.RESOLVED
    assert "Reused" in cache_diagnostics[0].message


def test_stale_entry_triggers_a_live_refresh_and_updates_in_place(database: SQLiteDatabase) -> None:
    identity_provider = _IdentityProvider(_identity("0000021344"))
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    # The repository and the resolver share one clock, as production composition would.
    clock = iter([NOW, NOW, STALE, STALE])
    shared_clock = lambda: next(clock)  # noqa: E731
    repository = SQLiteInstrumentProfileRepository(database, clock=shared_clock)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=shared_clock)
    resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    profile = resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert identity_provider.calls == 2  # TTL expired: refreshed live
    assert profile.identity is not None
    record = repository.get("KO")
    assert record is not None
    assert record.refreshed_at == STALE
    assert record.cached_at == NOW  # same profile_id, only refreshed


def test_force_refresh_bypasses_fresh_reuse(repository: SQLiteInstrumentProfileRepository) -> None:
    identity_provider = _IdentityProvider(_identity("0000021344"))
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    assert identity_provider.calls == 1

    resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate, force_refresh=True)

    assert identity_provider.calls == 2


def test_disagreeing_anchor_on_refresh_supersedes_the_prior_profile(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates_first, kind_candidate = _candidates(_IdentityProvider(_identity("0000021344")), kind_provider)
    clock = iter([NOW, STALE])
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: next(clock))
    first = resolver.resolve("KO", identity_candidates=identity_candidates_first, kind_candidate=kind_candidate)
    assert first.identity is not None

    identity_candidates_second, _ = _candidates(_IdentityProvider(_identity("9999999999")), kind_provider)
    second = resolver.resolve("KO", identity_candidates=identity_candidates_second, kind_candidate=kind_candidate)

    assert second.identity is not None
    assert second.identity.issuer_identifier == "9999999999"
    current = repository.get("KO")
    assert current is not None
    assert current.identity_anchor == "9999999999"
    assert current.is_current


def test_no_anchor_never_persists_and_resolves_live_every_time(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    identity_provider = _IdentityProvider(None)
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)

    first = resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
    second = resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    assert identity_provider.calls == 2  # never cached: resolved live both times
    assert first.identity is None
    assert second.identity is None
    assert repository.get("KO") is None


def test_refresh_failure_with_a_prior_entry_falls_open_to_the_stale_profile(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates_first, kind_candidate = _candidates(_IdentityProvider(_identity("0000021344")), kind_provider)
    clock = iter([NOW, STALE])
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: next(clock))
    resolver.resolve("KO", identity_candidates=identity_candidates_first, kind_candidate=kind_candidate)

    failing_candidates, _ = _candidates(_IdentityProvider(None), kind_provider)
    profile = resolver.resolve("KO", identity_candidates=failing_candidates, kind_candidate=kind_candidate)

    assert profile.identity is not None
    assert profile.identity.issuer_identifier == "0000021344"
    cache_diagnostics = [item for item in profile.diagnostics if item.capability is InstrumentProfileCapability.CACHE]
    assert len(cache_diagnostics) == 1
    assert cache_diagnostics[0].status is InstrumentProfileResolutionStatus.UNAVAILABLE
    assert "could not confirm" in cache_diagnostics[0].message
    # The durable record is untouched by the failed refresh attempt.
    record = repository.get("KO")
    assert record is not None
    assert record.refreshed_at == NOW


def test_current_record_reads_the_repository_without_a_live_call(
    repository: SQLiteInstrumentProfileRepository,
) -> None:
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)
    assert resolver.current_record("KO") is None

    identity_provider = _IdentityProvider(_identity("0000021344"))
    kind_provider = _KindProvider(_kind_evidence())
    identity_candidates, kind_candidate = _candidates(identity_provider, kind_provider)
    resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    record = resolver.current_record("ko")
    assert record is not None
    assert record.identity_anchor == "0000021344"
    assert identity_provider.calls == 1


def test_resolve_rejects_a_naive_clock(repository: SQLiteInstrumentProfileRepository) -> None:
    naive_clock = lambda: datetime(2026, 9, 21, 12, 0, 0)  # noqa: E731
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=naive_clock)
    identity_candidates, kind_candidate = _candidates(_IdentityProvider(_identity("0000021344")), _KindProvider(None))
    with pytest.raises(ValueError, match="timezone-aware"):
        resolver.resolve("KO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)


def test_concurrent_resolutions_for_the_same_new_ticker_never_mint_two_current_rows(
    database: SQLiteDatabase,
) -> None:
    """Prove the P2-Profiles §13.6 race fix: a shared resolver serializes per ticker.

    Without ``CachedInstrumentProfileResolver``'s per-ticker lock, several
    threads could all observe "no current row" before any of them commits its
    insert, minting one competing durable profile each (P2-Profiles contract
    §6/§13.6) -- there is no database-level unique constraint left to catch
    it. A slow identity provider widens that race window; the assertion that
    the provider is called exactly once is only possible if every concurrent
    caller but the first was serialized behind the lock and then found a
    freshly minted, still-fresh durable entry to reuse.
    """
    call_count = 0
    call_count_lock = threading.Lock()

    class _SlowIdentityProvider:
        def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
            nonlocal call_count
            with call_count_lock:
                call_count += 1
            time.sleep(0.05)
            return SecurityIdentity(
                ticker="NEWCO", provider_id="yfinance", resolved_at=NOW, issuer_identifier="0000099999"
            )

    newco_kind_evidence = InstrumentKindEvidence(
        ticker="NEWCO", kind=InstrumentKind.EQUITY, provider_value="EQUITY", provider_id="yfinance", resolved_at=NOW
    )
    identity_candidates = (InstrumentProfileCandidate("yfinance", _SlowIdentityProvider()),)
    kind_candidate = InstrumentProfileCandidate("yfinance", _KindProvider(newco_kind_evidence))
    repository = SQLiteInstrumentProfileRepository(database, clock=lambda: NOW)
    resolver = CachedInstrumentProfileResolver(repository, ttl=TTL, clock=lambda: NOW)

    def _resolve() -> None:
        resolver.resolve("NEWCO", identity_candidates=identity_candidates, kind_candidate=kind_candidate)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in [pool.submit(_resolve) for _ in range(8)]:
            future.result()

    assert call_count == 1
    record = repository.get("NEWCO")
    assert record is not None
    assert record.identity_anchor == "0000099999"
