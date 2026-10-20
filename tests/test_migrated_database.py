"""The migrated-database helper: a copy of the migrated template is a complete database at head."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from investment_analysis_engine.config import ProjectSettings, settings
from investment_analysis_engine.data.repositories.readiness import ReadinessOutcome, ensure_database_ready
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from tests._migrated_database import _template, migrated_database_url
from tests.conftest import SESSION_FOLDER


def _database_at(url: str) -> SQLiteDatabase:
    return SQLiteDatabase(ProjectSettings(database_url=url))


def test_a_copied_database_is_at_head_and_ready(tmp_path: Path) -> None:
    """The check the CLI runs finds a copy ready: no upgrade is needed and none is run."""
    database = _database_at(migrated_database_url(tmp_path))
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.READY
    finally:
        database.close()


def test_the_template_is_in_the_session_folder_and_has_no_pending_write_ahead_content() -> None:
    template = _template()

    assert template.resolve().is_relative_to(SESSION_FOLDER)
    assert settings.data_dir.resolve().is_relative_to(SESSION_FOLDER)
    assert not Path(f"{template}-wal").exists() or Path(f"{template}-wal").stat().st_size == 0


def test_the_template_is_migrated_once_per_process() -> None:
    assert _template() is _template()


def test_two_copies_are_independent_files(tmp_path: Path) -> None:
    """A write to one copy changes neither the template nor another copy."""
    first_url = migrated_database_url(tmp_path / "first")
    second_url = migrated_database_url(tmp_path / "second")
    template_bytes = _template().read_bytes()
    first = _database_at(first_url)
    try:
        with first.transaction() as connection:
            connection.exec_driver_sql("CREATE TABLE marker (value INTEGER)")
    finally:
        first.close()

    second = _database_at(second_url)
    try:
        with second.read() as connection:
            tables = connection.exec_driver_sql("SELECT name FROM sqlite_master").scalars().all()
    finally:
        second.close()
    assert "marker" not in tables
    assert _template().read_bytes() == template_bytes
    assert make_url(first_url).database != make_url(second_url).database


def test_a_second_copy_into_the_same_folder_is_refused(tmp_path: Path) -> None:
    migrated_database_url(tmp_path)

    with pytest.raises(FileExistsError):
        migrated_database_url(tmp_path)
