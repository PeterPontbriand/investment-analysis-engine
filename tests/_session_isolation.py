"""The check that keeps a test session inside its temporary folder.

``tests/conftest.py`` points the settings, data and log folders at one session folder before the package is imported.
This check, run when the session starts, confirms that every resolved location is inside that folder and otherwise stops
the session, so that no test can reach the user's real settings, database or logs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from investment_analysis_engine.config import ProjectSettings


def locations_outside(session_folder: Path, configured: ProjectSettings) -> list[str]:
    """Name every resolved folder, and the database file, that does not lie inside ``session_folder``."""
    locations = {
        "settings folder": configured.config_dir,
        "data folder": configured.data_dir,
        "log folder": configured.log_dir,
        "telemetry folder": configured.telemetry_log_dir,
    }
    database = make_url(configured.database_url).database
    if database not in (None, "", ":memory:"):
        locations["database"] = Path(database)
    return [name for name, path in locations.items() if not path.resolve().is_relative_to(session_folder.resolve())]


def stop_session_if_outside(session_folder: Path, configured: ProjectSettings) -> None:
    """Stop the whole pytest session, before any test runs, when a location lies outside ``session_folder``.

    Stopping at session start skips the hook that removes the session folder, so the folder is removed here.
    """
    outside = locations_outside(session_folder, configured)
    if outside:
        shutil.rmtree(session_folder, ignore_errors=True)
        pytest.exit(
            f"Test isolation failed: the {', '.join(outside)} lie outside the session folder {session_folder}.",
            returncode=2,
        )
