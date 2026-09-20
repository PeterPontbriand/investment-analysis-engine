"""Focused tests for the terminal execution/save service, using fake dependencies only."""

import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from alembic.config import Config

from alembic import command
from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.config import ProjectSettings
from src.data.instrument_profile import InstrumentKind
from src.data.repositories.analysis_runs import AnalysisRunConflictError, SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.workspace.codecs import decode_evidence
from src.workspace.execution import (
    BatchContext,
    ExecutionCapture,
    execute,
    from_fcf_growth_capture,
    from_graham_growth_capture,
    from_graham_number_capture,
    from_momentum_capture,
)
from src.workspace.fcf_growth_execution import FCFGrowthCapture
from src.workspace.graham_growth_execution import GrahamGrowthCapture
from src.workspace.graham_number_execution import GrahamNumberCapture
from src.workspace.models import RunOutcome
from src.workspace.momentum_execution import capture_momentum, run_momentum
from src.workspace.requests import AnalysisRequest, MomentumSelection
from src.workspace.runs import AnalysisRun

NOW = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 18, 12, 0, 1, tzinfo=UTC)
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


@pytest.fixture(autouse=True)
def mock_momentum_settings() -> Iterator[None]:
    """Materialize deterministic Momentum defaults for the analyzer's fallback ticker."""
    mock_analysis = {"default": {"default_ticker": "BTC-USD", "data_start_date": "2026-01-01"}}
    with patch("src.config.ProjectSettings.get_analysis_settings", return_value=mock_analysis):
        yield


class _FakeSink:
    """Minimal AnalysisRunSink recording every insert call."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.inserted: list[AnalysisRun] = []
        self._fail = fail

    def insert(self, run: AnalysisRun) -> None:
        if self._fail is not None:
            raise self._fail
        self.inserted.append(run)


def _momentum_native_evidence() -> MomentumRun:
    client = _FixtureClient()
    return run_momentum(MomentumSelection(short_window=2, long_window=3), "AAPL", client)


def _momentum_request() -> AnalysisRequest:
    return AnalysisRequest(ticker="AAPL", selection=MomentumSelection(short_window=2, long_window=3))


def _fake_capture(outcome: RunOutcome) -> ExecutionCapture:
    """A capture using real native evidence (so encode_evidence works) with a chosen outcome."""
    return ExecutionCapture(
        native_evidence=_momentum_native_evidence(),
        profile=fixture_instrument_profile("AAPL", kind=InstrumentKind.EQUITY, provider_value="EQUITY"),
        outcome=outcome,
    )


def test_execute_assembles_and_inserts_a_completed_run() -> None:
    sink = _FakeSink()
    clock_values = iter([NOW, LATER])
    profile = fixture_instrument_profile("AAPL", kind=InstrumentKind.EQUITY, provider_value="EQUITY")

    run = execute(
        _momentum_request(),
        capture=lambda: ExecutionCapture(
            native_evidence=_momentum_native_evidence(), profile=profile, outcome=RunOutcome.COMPLETED
        ),
        repository=sink,
        id_factory=lambda: RUN_ID,
        clock=lambda: next(clock_values),
    )

    assert sink.inserted == [run]
    assert run.instrument_profile == profile
    assert run.analysis_run_id == RUN_ID
    assert run.started_at == NOW
    assert run.completed_at == LATER
    assert run.ticker == "AAPL"
    assert run.analysis_id == "momentum"
    assert run.method_id == "sma_crossover"
    assert run.config_schema_version == 1
    assert run.method_version == 1
    assert run.result_schema_version == 1
    assert run.evidence_codec_version == 1
    assert run.projection_version == 1
    assert run.status is RunOutcome.COMPLETED
    assert run.failure_reason_code is None
    assert run.requested_config == run.effective_config == MomentumSelection(short_window=2, long_window=3)
    assert run.result_evidence is not None
    assert decode_evidence(run) is not None
    assert run.refresh_id is None
    assert run.batch_position is None
    assert run.watchlist_id is None
    assert run.watchlist_name is None


def test_execute_without_batch_leaves_refresh_and_watchlist_fields_null() -> None:
    """A direct (non-refresh) call passes no `batch`; every batch-identity field stays null."""
    run = execute(
        _momentum_request(),
        capture=lambda: _fake_capture(RunOutcome.COMPLETED),
        repository=_FakeSink(),
        id_factory=lambda: RUN_ID,
        clock=lambda: NOW,
    )
    assert run.refresh_id is None
    assert run.batch_position is None
    assert run.watchlist_id is None
    assert run.watchlist_name is None


def test_execute_with_batch_context_stamps_refresh_and_watchlist_identity() -> None:
    refresh_id = UUID("22222222-2222-4222-8222-222222222222")
    watchlist_id = UUID("33333333-3333-4333-8333-333333333333")
    batch = BatchContext(refresh_id=refresh_id, batch_position=3, watchlist_id=watchlist_id, watchlist_name="My Watch")

    run = execute(
        _momentum_request(),
        capture=lambda: _fake_capture(RunOutcome.COMPLETED),
        repository=_FakeSink(),
        id_factory=lambda: RUN_ID,
        clock=lambda: NOW,
        batch=batch,
    )

    assert run.refresh_id == refresh_id
    assert run.batch_position == 3
    assert run.watchlist_id == watchlist_id
    assert run.watchlist_name == "My Watch"


@pytest.mark.parametrize("outcome", [RunOutcome.NOT_APPLICABLE, RunOutcome.UNAVAILABLE, RunOutcome.COMPLETED])
def test_execute_only_sets_failure_reason_code_for_failed(outcome: RunOutcome) -> None:
    run = execute(
        _momentum_request(),
        capture=lambda: _fake_capture(outcome),
        repository=_FakeSink(),
        id_factory=lambda: RUN_ID,
        clock=lambda: NOW,
    )
    assert run.status is outcome
    assert run.failure_reason_code is None


def test_execute_sets_a_stable_failure_reason_code_when_failed() -> None:
    run = execute(
        _momentum_request(),
        capture=lambda: _fake_capture(RunOutcome.FAILED),
        repository=_FakeSink(),
        id_factory=lambda: RUN_ID,
        clock=lambda: NOW,
    )
    assert run.status is RunOutcome.FAILED
    assert run.failure_reason_code == "execution_failed"


def test_execute_does_not_insert_when_capture_raises() -> None:
    sink = _FakeSink()

    def raiser() -> ExecutionCapture:
        raise RuntimeError("simulated adapter failure")

    with pytest.raises(RuntimeError, match="simulated adapter failure"):
        execute(_momentum_request(), capture=raiser, repository=sink, id_factory=lambda: RUN_ID, clock=lambda: NOW)

    assert sink.inserted == []


def test_execute_propagates_persistence_errors_without_masking_them() -> None:
    sink = _FakeSink(fail=AnalysisRunConflictError("duplicate"))

    with pytest.raises(AnalysisRunConflictError):
        execute(
            _momentum_request(),
            capture=lambda: _fake_capture(RunOutcome.COMPLETED),
            repository=sink,
            id_factory=lambda: RUN_ID,
            clock=lambda: NOW,
        )


def test_execute_calls_capture_exactly_once() -> None:
    calls = Mock(wraps=lambda: _fake_capture(RunOutcome.COMPLETED))
    execute(_momentum_request(), capture=calls, repository=_FakeSink(), id_factory=lambda: RUN_ID, clock=lambda: NOW)
    assert calls.call_count == 1


def test_from_momentum_capture_maps_fields() -> None:
    client = _FixtureClient()
    run = run_momentum(MomentumSelection(short_window=2, long_window=3), "AAPL", client)
    profile = fixture_instrument_profile("AAPL", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    momentum_capture = capture_momentum(run, profile)

    result = from_momentum_capture(momentum_capture)

    assert result.native_evidence is run
    assert result.profile is profile
    assert result.outcome is RunOutcome.COMPLETED
    assert result.presentation_inputs == momentum_capture.presentation_inputs


def test_from_graham_number_capture_maps_fields() -> None:
    evidence = _momentum_native_evidence()  # any object works; the normalizer only reshapes fields
    profile = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    capture = GrahamNumberCapture(analysis=evidence, profile=profile, outcome=RunOutcome.FAILED)  # type: ignore[arg-type]

    result = from_graham_number_capture(capture)

    assert result.native_evidence is evidence
    assert result.profile is profile
    assert result.outcome is RunOutcome.FAILED
    assert result.presentation_inputs == {}


def test_from_graham_growth_capture_maps_fields() -> None:
    evidence = _momentum_native_evidence()
    profile = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    capture = GrahamGrowthCapture(analysis=evidence, profile=profile, outcome=RunOutcome.NOT_APPLICABLE)  # type: ignore[arg-type]

    result = from_graham_growth_capture(capture)

    assert result.native_evidence is evidence
    assert result.profile is profile
    assert result.outcome is RunOutcome.NOT_APPLICABLE
    assert result.presentation_inputs == {}


def test_from_fcf_growth_capture_maps_fields() -> None:
    evidence = _momentum_native_evidence()
    profile = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    capture = FCFGrowthCapture(result=evidence, profile=profile, outcome=RunOutcome.UNAVAILABLE)  # type: ignore[arg-type]

    result = from_fcf_growth_capture(capture)

    assert result.native_evidence is evidence
    assert result.profile is profile
    assert result.outcome is RunOutcome.UNAVAILABLE
    assert result.presentation_inputs == {}


def test_execute_persists_through_a_real_repository_and_reopens(tmp_path: Path) -> None:
    """End-to-end: a real SQLiteAnalysisRunRepository, reopened, matches exactly."""
    url = f"sqlite:///{(tmp_path / 'reopen.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = SQLiteAnalysisRunRepository(first_database)
        saved = execute(
            _momentum_request(),
            capture=lambda: _fake_capture(RunOutcome.COMPLETED),
            repository=repository,
            id_factory=lambda: RUN_ID,
            clock=lambda: NOW,
        )
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        reopened = SQLiteAnalysisRunRepository(second_database).get(RUN_ID)
        assert reopened == saved
        assert reopened is not None
        assert reopened.instrument_profile == saved.instrument_profile is not None
    finally:
        second_database.close()


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Execution service must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    run = execute(
        _momentum_request(),
        capture=lambda: _fake_capture(RunOutcome.COMPLETED),
        repository=_FakeSink(),
        id_factory=lambda: RUN_ID,
        clock=lambda: NOW,
    )
    assert run.ticker == "AAPL"
