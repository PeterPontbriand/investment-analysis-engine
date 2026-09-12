"""Maintenance snapshots, real storage locks, and structural upgrades use disposable files."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.engine import Connection

from src.config import ProjectSettings
from src.data.repositories import SQLiteDatabase, migrations, readiness
from src.data.repositories.readiness import DatabaseReadinessError, DatabaseState, ReadinessOutcome, ReadinessReason


def database_for(path: Path) -> SQLiteDatabase:
    """Keep real SQLite contention tests bounded."""
    return SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}", database_busy_timeout_ms=10))


def test_status_reads_one_snapshot_during_committed_revision_change(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    database = database_for(path)
    try:
        readiness.ensure_database_ready(database)
        original = readiness._schema_ready

        def change_after_snapshot(connection: Connection, resources: migrations.MigrationResources) -> bool:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == resources.head
            with closing(sqlite3.connect(path, autocommit=True)) as writer:
                writer.execute("UPDATE alembic_version SET version_num='private-unknown-revision'")
            return original(connection, resources)

        with patch.object(readiness, "_schema_ready", change_after_snapshot):
            assert readiness.inspect_database(database).state is DatabaseState.READY
        observed = readiness.inspect_database(database)
        assert observed.state is DatabaseState.INCOMPATIBLE
        assert observed.current_revision is None
    finally:
        database.close()


def test_status_classifies_real_sqlite_exclusive_lock_without_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "busy.sqlite3"
    database = database_for(path)
    try:
        with closing(sqlite3.connect(path, autocommit=True)) as writer:
            writer.execute("CREATE TABLE existing(value TEXT)")
            writer.execute("BEGIN EXCLUSIVE")
            with pytest.raises(DatabaseReadinessError) as caught:
                readiness.inspect_database(database)
            assert caught.value.reason is ReadinessReason.BUSY
            assert not Path(str(path) + ".readiness.lock").exists()
            writer.rollback()
    finally:
        database.close()


@pytest.mark.parametrize("drift", [False, True])
def test_structurally_older_schema_is_validated_then_migrated(tmp_path: Path, drift: bool) -> None:
    resources = migrations.migration_resources()
    directory = tmp_path / "structural-alembic"
    shutil.copytree(resources.directory, directory, ignore=shutil.ignore_patterns("__pycache__"))
    base = directory / "versions" / "0001_persistence.py"
    source = base.read_text(encoding="utf-8")
    source = source.replace(
        "\ndef downgrade() -> None:",
        "    op.create_table('legacy_probe', sa.Column('value', sa.Integer(), nullable=False))\n\n"
        "\ndef downgrade() -> None:",
    )
    base.write_text(source, encoding="utf-8")
    head = "synthetic_structural_head"
    (directory / "versions" / f"{head}.py").write_text(
        "from alembic import op\n"
        f"revision = '{head}'\ndown_revision = '0001_persistence'\n"
        "def upgrade():\n    op.drop_table('legacy_probe')\n"
        "def downgrade():\n    pass\n",
        encoding="utf-8",
    )
    graph = migrations.MigrationResources(directory, head, frozenset({resources.head}))
    path = tmp_path / "older.sqlite3"
    database = database_for(path)
    try:
        with database.transaction() as connection:
            migrations.upgrade_database_revision(connection, graph, resources.head)
            connection.exec_driver_sql("INSERT INTO legacy_probe VALUES (42)")
        if drift:
            with database.transaction() as connection:
                connection.exec_driver_sql("ALTER TABLE legacy_probe ADD COLUMN unrecognized TEXT")
        before = path.read_bytes()
        with patch.object(readiness, "migration_resources", return_value=graph):
            observed = readiness.inspect_database(database)
            if drift:
                assert observed.state is DatabaseState.INCOMPATIBLE
                with pytest.raises(DatabaseReadinessError) as caught:
                    readiness.upgrade_database(database)
                assert caught.value.reason is ReadinessReason.INCOMPATIBLE_SCHEMA
                assert path.read_bytes() == before
            else:
                assert observed.state is DatabaseState.UPGRADE_REQUIRED
                assert observed.current_revision == resources.head
                assert readiness.upgrade_database(database) == (ReadinessOutcome.UPGRADED, head)
                assert readiness.inspect_database(database).state is DatabaseState.READY
                with database.read() as connection:
                    assert (
                        connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE name='legacy_probe'").all()
                        == []
                    )
    finally:
        database.close()


@pytest.mark.parametrize(
    "version_sql",
    [
        "DELETE FROM alembic_version",
        "INSERT INTO alembic_version VALUES ('private-extra-revision')",
        "UPDATE alembic_version SET version_num='private-unknown-revision'",
        "DROP TABLE market_price_observations",
        "UPDATE schema_metadata SET metadata_value=999",
    ],
)
def test_status_and_upgrade_preserve_inconsistent_storage(tmp_path: Path, version_sql: str) -> None:
    path = tmp_path / "inconsistent.sqlite3"
    database = database_for(path)
    try:
        readiness.ensure_database_ready(database)
        with database.transaction() as connection:
            connection.exec_driver_sql(version_sql)
        before = path.read_bytes()
        report = readiness.inspect_database(database)
        assert report.state is DatabaseState.INCOMPATIBLE
        assert report.current_revision is None
        with pytest.raises(DatabaseReadinessError) as caught:
            readiness.upgrade_database(database)
        assert caught.value.reason is ReadinessReason.INCOMPATIBLE_SCHEMA
        assert "private-" not in str(caught.value)
        assert path.read_bytes() == before
    finally:
        database.close()


def test_upgrade_rolls_back_failed_head_verification_and_releases_lock(tmp_path: Path) -> None:
    path = tmp_path / "verify.sqlite3"
    database = database_for(path)
    resources = migrations.migration_resources()
    graph = migrations.MigrationResources(resources.directory, "synthetic_head", frozenset({resources.head}))
    original = migrations.upgrade_database_revision

    def inconsistent_head(connection: Connection, selected: migrations.MigrationResources, revision: str) -> None:
        if revision == resources.head:
            original(connection, selected, revision)
        else:
            connection.exec_driver_sql("CREATE TABLE partial_upgrade(value INTEGER)")
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='synthetic_head'")

    try:
        readiness.ensure_database_ready(database)
        with (
            patch.object(readiness, "migration_resources", return_value=graph),
            patch.object(readiness, "upgrade_database_revision", side_effect=inconsistent_head),
        ):
            with pytest.raises(DatabaseReadinessError) as caught:
                readiness.upgrade_database(database)
            assert caught.value.reason is ReadinessReason.MIGRATION_FAILED
        assert readiness.upgrade_database(database)[0] is ReadinessOutcome.READY
        with database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE name='partial_upgrade'").all() == []
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == resources.head
    finally:
        database.close()
