"""A test session works only inside its own temporary folder, and stops if any location lies outside it."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from investment_analysis_engine.config import ProjectSettings, settings
from tests._session_isolation import locations_outside, session_database_file, stop_session_if_outside
from tests.conftest import SESSION_FOLDER


def test_the_session_folder_is_a_temporary_folder_and_the_engine_variables_point_into_it() -> None:
    assert SESSION_FOLDER.is_dir() or not SESSION_FOLDER.exists()
    assert SESSION_FOLDER.name.startswith("ian-tests-")
    for name in ("IAN_CONFIG_DIR", "IAN_DATA_DIR", "IAN_LOG_DIR"):
        assert Path(os.environ[name]).resolve().is_relative_to(SESSION_FOLDER)


def test_every_resolved_location_of_the_process_settings_is_inside_the_session_folder() -> None:
    assert locations_outside(SESSION_FOLDER, settings) == []
    assert settings.telemetry_log_dir == settings.log_dir


def test_a_location_outside_the_session_folder_is_named(tmp_path: Path) -> None:
    elsewhere = ProjectSettings(config_dir=SESSION_FOLDER / "c", data_dir=tmp_path / "d", log_dir=SESSION_FOLDER / "l")

    assert locations_outside(SESSION_FOLDER, elsewhere) == ["data folder", "database"]


def test_the_session_stops_before_any_test_when_a_location_lies_outside(tmp_path: Path) -> None:
    session = tmp_path / "ian-tests-stopped"
    session.mkdir()
    (session / "left-behind.txt").write_text("x", encoding="utf-8")
    elsewhere = ProjectSettings(config_dir=tmp_path / "c", data_dir=tmp_path / "d", log_dir=tmp_path / "l")

    with pytest.raises(pytest.exit.Exception) as stopped:
        stop_session_if_outside(session, elsewhere)

    assert stopped.value.returncode == 2
    assert "Test isolation failed: the settings folder, data folder, log folder, telemetry folder, database lie" in str(
        stopped.value
    )
    assert not session.exists()


def test_a_session_with_every_location_inside_keeps_its_folder(tmp_path: Path) -> None:
    session = tmp_path / "ian-tests-kept"
    session.mkdir()
    inside = ProjectSettings(config_dir=session / "c", data_dir=session / "d", log_dir=session / "l")

    stop_session_if_outside(session, inside)

    assert session.is_dir()


def test_a_session_with_every_location_inside_is_not_stopped() -> None:
    stop_session_if_outside(SESSION_FOLDER, settings)


def test_the_session_database_the_guard_checks_is_the_default_database_in_the_session_data_folder() -> None:
    database = session_database_file(settings)

    assert database == settings.data_dir / "investment-analysis-engine.sqlite3"
    assert database.resolve().is_relative_to(SESSION_FOLDER)
    assert not database.exists()


def test_a_database_that_is_not_a_file_has_no_session_database_file() -> None:
    assert session_database_file(ProjectSettings(database_url="sqlite:///:memory:")) is None
