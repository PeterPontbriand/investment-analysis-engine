"""Deterministic Alembic bootstrap checks against disposable SQLite databases."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command, context
from src.config import ProjectSettings
from src.data.repositories import SQLiteDatabase

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def migration_config(path: Path) -> Config:
    """Build a repository-rooted Alembic config for a disposable database."""
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


def test_cli_schema_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cli database.sqlite3"
    unused = tmp_path / "unused.sqlite3"
    monkeypatch.setenv("database_url", f"sqlite:///{unused.as_posix()}")
    for operation, revision in [("upgrade", "head"), ("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"database_url=sqlite:///{path.as_posix()}", operation, revision],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
        try:
            with database.read() as connection:
                tables = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars().all()
                expected = (
                    {"alembic_version"}
                    if operation == "downgrade"
                    else {
                        "alembic_version",
                        "schema_metadata",
                        "trajectory_events",
                        "resolved_input_cache",
                        "market_data_cache_entries",
                        "market_price_observations",
                    }
                )
                assert set(tables) == expected
                versions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
                assert versions == ([] if operation == "downgrade" else ["0001_persistence"])
        finally:
            database.close()
    assert not unused.exists()


def test_environment_url_and_logging_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "environment.sqlite3"
    monkeypatch.setenv("database_url", f"sqlite:///{path.as_posix()}")
    logger = logging.getLogger()
    handlers = list(logger.handlers)
    level = logger.level

    command.upgrade(Config(str(REPOSITORY_ROOT / "alembic.ini")), "head")

    assert path.exists()
    assert logger.handlers == handlers
    assert logger.level == level


def test_migration_connection_uses_b1_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("database_busy_timeout_ms", "123")
    visited: list[bool] = []

    def inspect_connection() -> None:
        connection = context.get_context().connection
        assert connection is not None
        assert connection.in_transaction()
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 123
        visited.append(True)

    monkeypatch.setattr(context, "run_migrations", inspect_connection)
    command.upgrade(migration_config(tmp_path / "policy.sqlite3"), "head")
    assert visited == [True]


def test_failure_rolls_back_ddl_and_releases_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "failed.sqlite3"

    def fail_migration() -> None:
        connection = context.get_context().connection
        assert connection is not None
        connection.exec_driver_sql("CREATE TABLE should_rollback (id INTEGER)")
        raise RuntimeError("deliberate migration failure")

    monkeypatch.setattr(context, "run_migrations", fail_migration)
    with pytest.raises(RuntimeError, match="deliberate migration failure"):
        command.upgrade(migration_config(path), "head")
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []
    finally:
        database.close()
    assert path.rename(tmp_path / "released.sqlite3").exists()


def test_programmatic_override_with_percent_and_independent_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "100% valid.sqlite3"
    unused = tmp_path / "unused.sqlite3"
    monkeypatch.setenv("database_url", f"sqlite:///{unused.as_posix()}")
    monkeypatch.chdir(tmp_path)

    command.upgrade(migration_config(path), "head")

    assert path.exists()
    assert not unused.exists()


def test_offline_mode_rejected_without_creating_database(tmp_path: Path) -> None:
    path = tmp_path / "offline.sqlite3"
    with pytest.raises(ValueError, match="Offline migrations"):
        command.upgrade(migration_config(path), "head", sql=True)
    assert not path.exists()
