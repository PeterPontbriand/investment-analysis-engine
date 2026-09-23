"""Prove the durable instrument-profile cache and Analysis Run persistence compose correctly.

P2-Profiles contract §5: a completed Analysis Run stores its instrument-profile
snapshot inline, and a later ticker-reuse supersession in the durable cache
must never relabel a previously persisted historical run. This exercises the
real chain end to end: `CachedInstrumentProfileResolver` -> `execute()` ->
`SQLiteAnalysisRunRepository` -> reopen -> `project_run()`, with no mocks on
the persistence or replay path.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config

from alembic import command
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.config import ProjectSettings
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfileCandidate,
)
from src.data.instrument_profile_cache import CachedInstrumentProfileResolver
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from src.reporting.analysis_runs import ReplayOptions, project_run
from src.reporting.presentation import PresentationMode
from src.workspace.execution import ExecutionCapture, execute
from src.workspace.models import RunOutcome
from src.workspace.requests import AnalysisRequest, GrahamNumberSelection

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=31)
TTL = timedelta(days=30)
FIRST_RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
SECOND_RUN_ID = UUID("22222222-2222-4222-8222-222222222222")


class _IdentityProvider:
    """Identity provider spy with one configured, replaceable response."""

    def __init__(self, identity: SecurityIdentity | None) -> None:
        self.identity = identity
        self.calls = 0

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        return self.identity


class _KindProvider:
    """Instrument-kind provider spy with one configured response."""

    def __init__(self, evidence: InstrumentKindEvidence | None) -> None:
        self.evidence = evidence

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        return self.evidence


def _identity(anchor: str, *, name: str, resolved_at: datetime) -> SecurityIdentity:
    return SecurityIdentity(
        ticker="RENU", provider_id="yfinance", resolved_at=resolved_at, instrument_name=name, issuer_identifier=anchor
    )


def _kind_evidence(resolved_at: datetime) -> InstrumentKindEvidence:
    return InstrumentKindEvidence(
        ticker="RENU",
        kind=InstrumentKind.EQUITY,
        provider_value="EQUITY",
        provider_id="yfinance",
        resolved_at=resolved_at,
    )


def _candidates(
    identity_provider: _IdentityProvider, kind_provider: _KindProvider
) -> tuple[tuple[InstrumentProfileCandidate, ...], InstrumentProfileCandidate]:
    return (InstrumentProfileCandidate("yfinance", identity_provider),), InstrumentProfileCandidate(
        "yfinance", kind_provider
    )


def _graham_number_analysis(ticker: str, price: float) -> GrahamNumberAnalysis:
    """A deterministic, minimal Graham Number result; only the profile matters here."""
    eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
    bvps = ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
    assembly = GrahamNumberInputAssembly(CalculationStatus.OK, eps, bvps, None)
    return GrahamNumberAnalysis(
        ticker=ticker,
        as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=price),
        margin_of_safety_percent=None,
    )


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'analysis_run_profile_snapshot.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


def test_a_ticker_reuse_supersession_never_relabels_a_previously_persisted_run(
    database: SQLiteDatabase,
) -> None:
    """The core P2-Profiles §5 proof: history is frozen, only the current view moves on."""
    # The repository's own clock stamps each successful put(): NOW for Generation
    # A's mint, LATER for Generation B's supersede-and-mint.
    repository_clock = iter([NOW, LATER])
    profile_repository = SQLiteInstrumentProfileRepository(database, clock=lambda: next(repository_clock))
    run_repository = SQLiteAnalysisRunRepository(database)

    # --- Generation A: first resolution, first Analysis Run ---
    profile_cache_a = CachedInstrumentProfileResolver(profile_repository, ttl=TTL, clock=lambda: NOW)
    identity_candidates_a, kind_candidate_a = _candidates(
        _IdentityProvider(_identity("0000011111", name="Generation A Inc.", resolved_at=NOW)),
        _KindProvider(_kind_evidence(NOW)),
    )
    profile_a = profile_cache_a.resolve(
        "renu", identity_candidates=identity_candidates_a, kind_candidate=kind_candidate_a
    )
    assert profile_a.identity is not None
    assert profile_a.identity.instrument_name == "Generation A Inc."

    def _capture_a() -> ExecutionCapture:
        return ExecutionCapture(
            native_evidence=_graham_number_analysis("RENU", 30.0), profile=profile_a, outcome=RunOutcome.COMPLETED
        )

    first_run = execute(
        AnalysisRequest(ticker="RENU", selection=GrahamNumberSelection()),
        capture=_capture_a,
        repository=run_repository,
        id_factory=lambda: FIRST_RUN_ID,
        clock=lambda: NOW,
    )

    # --- Ticker reuse: the same ticker now resolves to a different entity, past the TTL ---
    profile_cache_b = CachedInstrumentProfileResolver(profile_repository, ttl=TTL, clock=lambda: LATER)
    identity_candidates_b, kind_candidate_b = _candidates(
        _IdentityProvider(_identity("0000099999", name="Generation B Corp.", resolved_at=LATER)),
        _KindProvider(_kind_evidence(LATER)),
    )
    profile_b = profile_cache_b.resolve(
        "RENU", identity_candidates=identity_candidates_b, kind_candidate=kind_candidate_b
    )
    assert profile_b.identity is not None
    assert profile_b.identity.instrument_name == "Generation B Corp."

    def _capture_b() -> ExecutionCapture:
        return ExecutionCapture(
            native_evidence=_graham_number_analysis("RENU", 55.0), profile=profile_b, outcome=RunOutcome.COMPLETED
        )

    second_run = execute(
        AnalysisRequest(ticker="RENU", selection=GrahamNumberSelection()),
        capture=_capture_b,
        repository=run_repository,
        id_factory=lambda: SECOND_RUN_ID,
        clock=lambda: LATER,
    )

    # The durable "current" profile has moved on to Generation B.
    current = profile_repository.get("RENU")
    assert current is not None
    assert current.identity_anchor == "0000099999"

    # Reopening the FIRST run must still show Generation A -- never relabeled.
    reopened_first = run_repository.get(first_run.analysis_run_id)
    assert reopened_first is not None
    assert reopened_first.instrument_profile is not None
    assert reopened_first.instrument_profile.identity is not None
    assert reopened_first.instrument_profile.identity.instrument_name == "Generation A Inc."
    assert reopened_first.instrument_profile.identity.issuer_identifier == "0000011111"
    rendered_first = project_run(reopened_first, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Generation A Inc." in rendered_first
    assert "Generation B Corp." not in rendered_first

    # Reopening the SECOND run shows Generation B, its own execution-time snapshot.
    reopened_second = run_repository.get(second_run.analysis_run_id)
    assert reopened_second is not None
    assert reopened_second.instrument_profile is not None
    assert reopened_second.instrument_profile.identity is not None
    assert reopened_second.instrument_profile.identity.instrument_name == "Generation B Corp."
    rendered_second = project_run(reopened_second, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Generation B Corp." in rendered_second
    assert "Generation A Inc." not in rendered_second


def test_repeated_execution_within_ttl_reuses_the_cache_and_each_run_keeps_its_own_snapshot(
    database: SQLiteDatabase,
) -> None:
    """Reopen/reuse proof: no re-call to the provider, and every run's own snapshot is intact."""
    profile_repository = SQLiteInstrumentProfileRepository(database, clock=lambda: NOW)
    profile_cache = CachedInstrumentProfileResolver(profile_repository, ttl=TTL, clock=lambda: NOW)
    run_repository = SQLiteAnalysisRunRepository(database)
    identity_provider = _IdentityProvider(_identity("0000011111", name="Stable Co.", resolved_at=NOW))
    identity_candidates, kind_candidate = _candidates(identity_provider, _KindProvider(_kind_evidence(NOW)))

    def _capture() -> ExecutionCapture:
        profile = profile_cache.resolve("RENU", identity_candidates=identity_candidates, kind_candidate=kind_candidate)
        return ExecutionCapture(
            native_evidence=_graham_number_analysis("RENU", 30.0), profile=profile, outcome=RunOutcome.COMPLETED
        )

    first_run = execute(
        AnalysisRequest(ticker="RENU", selection=GrahamNumberSelection()),
        capture=_capture,
        repository=run_repository,
        id_factory=lambda: FIRST_RUN_ID,
        clock=lambda: NOW,
    )
    second_run = execute(
        AnalysisRequest(ticker="RENU", selection=GrahamNumberSelection()),
        capture=_capture,
        repository=run_repository,
        id_factory=lambda: SECOND_RUN_ID,
        clock=lambda: NOW,
    )

    assert identity_provider.calls == 1  # the second execution reused the durable cache
    for run_id in (first_run.analysis_run_id, second_run.analysis_run_id):
        run = run_repository.get(run_id)
        assert run is not None
        assert run.instrument_profile is not None
        assert run.instrument_profile.identity is not None
        assert run.instrument_profile.identity.instrument_name == "Stable Co."
