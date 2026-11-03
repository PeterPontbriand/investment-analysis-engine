"""The one database opener: readiness first, closed on every path, a readiness error unchanged."""

from pathlib import Path
from unittest.mock import patch

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from tests.application._unready_database import unready_database_url


def test_a_ready_database_is_yielded_and_closed_afterward(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    with patch.object(SQLiteDatabase, "close", autospec=True, side_effect=SQLiteDatabase.close) as close:
        with open_database(context) as database:
            assert isinstance(database, SQLiteDatabase)
            close.assert_not_called()
        close.assert_called_once_with(database)


def test_the_database_is_closed_when_the_block_raises(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    with patch.object(SQLiteDatabase, "close", autospec=True, side_effect=SQLiteDatabase.close) as close:
        with pytest.raises(RuntimeError, match="inside"), open_database(context):
            raise RuntimeError("inside")
        close.assert_called_once()


def test_a_readiness_error_passes_through_unchanged_and_the_database_is_closed(
    isolated_cli_settings: ProjectSettings, tmp_path: Path
) -> None:
    error = DatabaseReadinessError(ReadinessReason.BUSY, tmp_path / "x.sqlite3")
    with (
        patch("investment_analysis_engine.application.database.ensure_database_ready", side_effect=error),
        patch.object(SQLiteDatabase, "close", autospec=True, side_effect=SQLiteDatabase.close) as close,
    ):
        with (
            pytest.raises(DatabaseReadinessError) as caught,
            open_database(ApplicationContext(settings=isolated_cli_settings)),
        ):
            raise AssertionError("the block must not run")
        close.assert_called_once()
    assert caught.value is error


def test_a_database_that_was_never_migrated_is_a_readiness_error(tmp_path: Path) -> None:
    settings = ProjectSettings(database_url=unready_database_url(tmp_path))
    with pytest.raises(DatabaseReadinessError), open_database(ApplicationContext(settings=settings)):
        raise AssertionError("the block must not run")
