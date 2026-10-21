"""A database at the latest revision, migrated once per test process and copied for each caller.

Upgrading a database through Alembic takes real time and the suite needs one at head for most of its storage tests.
:func:`migrated_database_url` migrates one template inside the session folder on first use and copies the file, so a
test pays for a file copy and not for a migration. :func:`alembic_config` and :func:`upgrade_to_head` serve the tests
whose subject is migration. Only the modules in ``_MIGRATION_TESTS`` in ``tests/test_helper_conventions.py`` may
call :func:`upgrade_to_head` or name ``alembic.ini``; a test elsewhere that does fails that file's scan, and copies
the template instead.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from functools import cache
from pathlib import Path
from typing import Final

import pytest
from alembic import command
from alembic.config import Config

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from scripts.repository_root import REPOSITORY_ROOT

ALEMBIC_INI: Final = REPOSITORY_ROOT / "alembic.ini"
DATABASE_FILE_NAME: Final = "migrated.sqlite3"
"""The name of every copy inside its folder, and of the template inside its own."""

_TEMPLATE_FOLDER_NAME: Final = "migrated-template"


def alembic_config(database_url: str) -> Config:
    """Return the repository's Alembic configuration pointed at ``database_url``."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_to_head(config: Config) -> None:
    """Upgrade the database ``config`` names to the latest revision."""
    command.upgrade(config, "head")


def _url_of(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


@cache
def _template() -> Path:
    """Migrate the template to head, close everything that holds it and return its file.

    The write-ahead log is checkpointed and removed first, so the main file is complete and a copy of it alone is a
    whole database.
    """
    from tests.conftest import SESSION_FOLDER  # noqa: PLC0415 - conftest imports this module

    folder = SESSION_FOLDER / _TEMPLATE_FOLDER_NAME
    folder.mkdir(parents=True)
    path = folder / DATABASE_FILE_NAME
    upgrade_to_head(alembic_config(_url_of(path)))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    leftovers = [item for item in (Path(f"{path}-wal"), Path(f"{path}-shm")) if item.exists() and item.stat().st_size]
    if leftovers:
        raise RuntimeError(f"The migrated template still holds pending write-ahead content: {leftovers}")
    return path


def migrated_database_url(folder: Path) -> str:
    """Copy the migrated template into ``folder`` and return the URL of the copy.

    A folder holds one copy: a second call for it raises ``FileExistsError``, and a test that needs two databases
    uses two folders.
    """
    folder.mkdir(parents=True, exist_ok=True)
    copy = folder / DATABASE_FILE_NAME
    with _template().open("rb") as source, copy.open("xb") as target:
        shutil.copyfileobj(source, target)
    return _url_of(copy)


@pytest.fixture
def migrated_database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    """Yield a ``SQLiteDatabase`` over a copy of the migrated template in the test's folder, and close it."""
    database = SQLiteDatabase(ProjectSettings(database_url=migrated_database_url(tmp_path)))
    try:
        yield database
    finally:
        database.close()
