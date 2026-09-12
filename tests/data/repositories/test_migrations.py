"""Deterministic Alembic bootstrap checks against disposable SQLite databases."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine

from alembic import command, context
from src.config import ProjectSettings
from src.data.repositories import SQLiteDatabase, migrations

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


def test_borrowed_transaction_is_not_committed_or_closed(tmp_path: Path) -> None:
    path = tmp_path / "borrowed.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))

    def migrate_and_abort() -> None:
        with database.transaction() as connection:
            migrations.upgrade_fresh_database(connection)
            assert not connection.closed
            assert connection.in_transaction()
            revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            assert revision == "0001_persistence"
            raise RuntimeError("outer rollback")

    try:
        with pytest.raises(RuntimeError, match="outer rollback"):
            migrate_and_abort()
        with database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table'").all() == []
    finally:
        database.close()


def test_borrowed_connection_rejects_url_override_without_touching_it(tmp_path: Path) -> None:
    unused = tmp_path / "unused.sqlite3"
    config = migration_config(unused)
    database = SQLiteDatabase(ProjectSettings(database_url="sqlite:///:memory:"))
    try:
        with database.transaction() as connection:
            config.attributes["connection"] = connection
            with pytest.raises(ValueError, match="URL overrides"):
                command.upgrade(config, "head")
            assert not connection.closed
        assert not unused.exists()
    finally:
        database.close()


def test_invalid_borrowed_connection_rejected(tmp_path: Path) -> None:
    config = migration_config(tmp_path / "unused.sqlite3")
    config.attributes["connection"] = object()
    with pytest.raises(ValueError, match="active SQLAlchemy"):
        command.upgrade(config, "head")
    assert not (tmp_path / "unused.sqlite3").exists()


def test_fresh_upgrade_requires_active_transaction() -> None:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection, pytest.raises(ValueError, match="active transaction"):
            migrations.upgrade_fresh_database(connection)
    finally:
        engine.dispose()


@pytest.mark.parametrize("shape", ["missing", "empty", "two_heads", "ancestor"])
def test_resource_discovery_checks_actual_synthetic_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    fake_module = tmp_path / "src" / "data" / "repositories" / "migrations.py"
    monkeypatch.setattr(migrations, "__file__", str(fake_module))
    scripts = tmp_path / "alembic"
    if shape != "missing":
        (scripts / "versions").mkdir(parents=True)
        (scripts / "env.py").write_text('"""Synthetic migration environment."""\n', encoding="utf-8")
    if shape in ("two_heads", "ancestor"):
        (scripts / "versions" / "a.py").write_text("revision = 'a'\ndown_revision = None\n", encoding="utf-8")
        parent = "'a'" if shape == "ancestor" else "None"
        (scripts / "versions" / "b.py").write_text(f"revision = 'b'\ndown_revision = {parent}\n", encoding="utf-8")
    if shape == "ancestor":
        resources = migrations.migration_resources()
        assert resources.head == "b"
        assert resources.ancestors == frozenset({"a"})
    else:
        with pytest.raises(ValueError, match="missing|exactly one head"):
            migrations.migration_resources()
