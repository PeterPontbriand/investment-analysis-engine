"""Verify instrument-profile minting, in-place refresh, supersession, and reopen."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config

from alembic import command
from src.config import ProjectSettings
from src.data.repositories.instrument_profiles import (
    InstrumentProfileRecord,
    SQLiteInstrumentProfileRepository,
)
from src.data.repositories.sqlite import SQLiteDatabase

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 21, 12, 5, 0, tzinfo=UTC)
FIRST_ID = UUID("11111111-1111-4111-8111-111111111111")
SECOND_ID = UUID("22222222-2222-4222-8222-222222222222")
THIRD_ID = UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'instrument_profiles.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def repository(database: SQLiteDatabase) -> SQLiteInstrumentProfileRepository:
    ids = iter([FIRST_ID, SECOND_ID])
    return SQLiteInstrumentProfileRepository(database, clock=lambda: NOW, id_factory=lambda: next(ids))


def test_get_returns_none_for_an_unknown_ticker(repository: SQLiteInstrumentProfileRepository) -> None:
    assert repository.get("KO") is None
    assert repository.get_by_id(FIRST_ID) is None


def test_put_mints_a_new_profile_on_first_resolution(repository: SQLiteInstrumentProfileRepository) -> None:
    record = repository.put("ko", identity_anchor="0000021344", evidence={"provider_id": "yfinance", "kind": "equity"})
    assert record == InstrumentProfileRecord(
        profile_id=FIRST_ID,
        ticker="KO",
        identity_anchor="0000021344",
        cached_at=NOW,
        refreshed_at=NOW,
        schema_version=1,
        evidence={"provider_id": "yfinance", "kind": "equity"},
    )
    assert record.is_current
    assert repository.get("KO") == record
    assert repository.get_by_id(FIRST_ID) == record


def test_matching_anchor_updates_in_place_and_preserves_cached_at(database: SQLiteDatabase) -> None:
    clock = iter([NOW, LATER])
    repository = SQLiteInstrumentProfileRepository(database, clock=lambda: next(clock), id_factory=lambda: FIRST_ID)
    repository.put("KO", identity_anchor="0000021344", evidence={"kind": "equity"})
    updated = repository.put("KO", identity_anchor="0000021344", evidence={"kind": "equity", "name": "Coca-Cola"})

    assert updated.profile_id == FIRST_ID
    assert updated.cached_at == NOW
    assert updated.refreshed_at == LATER
    assert updated.evidence == {"kind": "equity", "name": "Coca-Cola"}
    assert updated.superseded_at is None
    assert repository.get("KO") == updated


def test_disagreeing_anchor_supersedes_and_mints_a_new_profile(database: SQLiteDatabase) -> None:
    clock = iter([NOW, LATER])
    ids = iter([FIRST_ID, SECOND_ID])
    repository = SQLiteInstrumentProfileRepository(database, clock=lambda: next(clock), id_factory=lambda: next(ids))
    first = repository.put("KO", identity_anchor="0000021344", evidence={"kind": "equity"})
    second = repository.put("KO", identity_anchor="9999999999", evidence={"kind": "equity"})

    assert second.profile_id == SECOND_ID
    assert second.identity_anchor == "9999999999"
    assert second.cached_at == LATER
    assert second.superseded_at is None

    superseded = repository.get_by_id(FIRST_ID)
    assert superseded is not None
    assert superseded.profile_id == first.profile_id
    assert superseded.superseded_at == LATER
    assert superseded.superseded_reason is not None
    assert "0000021344" in superseded.superseded_reason
    assert "9999999999" in superseded.superseded_reason
    assert not superseded.is_current

    # The superseded row is retained, never deleted, but is no longer current.
    assert repository.get("KO") == second


def test_a_superseded_row_is_never_deleted_and_survives_further_activity(database: SQLiteDatabase) -> None:
    clock = iter([NOW, LATER, LATER])
    ids = iter([FIRST_ID, SECOND_ID, THIRD_ID])
    repository = SQLiteInstrumentProfileRepository(database, clock=lambda: next(clock), id_factory=lambda: next(ids))
    repository.put("KO", identity_anchor="0000021344", evidence={})
    repository.put("KO", identity_anchor="9999999999", evidence={})
    repository.put("MSFT", identity_anchor="0000789019", evidence={"kind": "equity"})

    assert repository.get_by_id(FIRST_ID) is not None
    msft = repository.get("MSFT")
    assert msft is not None
    assert msft.ticker == "MSFT"


def test_put_rejects_blank_ticker_or_anchor(repository: SQLiteInstrumentProfileRepository) -> None:
    with pytest.raises(ValueError, match="ticker"):
        repository.put("  ", identity_anchor="0000021344", evidence={})
    with pytest.raises(ValueError, match="identity_anchor"):
        repository.put("KO", identity_anchor="   ", evidence={})


def test_put_rejects_a_naive_clock(database: SQLiteDatabase) -> None:
    naive_clock = lambda: datetime(2026, 9, 21, 12, 0, 0)  # noqa: E731
    repository = SQLiteInstrumentProfileRepository(database, clock=naive_clock)
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.put("KO", identity_anchor="0000021344", evidence={})


def test_reopen_preserves_current_and_superseded_profiles(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'reopen.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")

    first_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        clock = iter([NOW, LATER])
        ids = iter([FIRST_ID, SECOND_ID])
        repository = SQLiteInstrumentProfileRepository(
            first_database, clock=lambda: next(clock), id_factory=lambda: next(ids)
        )
        repository.put("KO", identity_anchor="0000021344", evidence={"kind": "equity"})
        repository.put("KO", identity_anchor="9999999999", evidence={"kind": "equity", "reused": True})
    finally:
        first_database.close()

    second_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        reopened = SQLiteInstrumentProfileRepository(second_database)
        current = reopened.get("ko")
        assert current is not None
        assert current.profile_id == SECOND_ID
        assert current.evidence == {"kind": "equity", "reused": True}

        superseded = reopened.get_by_id(FIRST_ID)
        assert superseded is not None
        assert not superseded.is_current
        assert superseded.identity_anchor == "0000021344"
    finally:
        second_database.close()
