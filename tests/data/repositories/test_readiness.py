"""Readiness verifies real disposable schemas and preserves rejected storage."""

import errno
import shutil
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.engine import Connection

from src.config import ProjectSettings
from src.data.repositories import (
    DatabaseReadinessError,
    ReadinessOutcome,
    ReadinessReason,
    SQLiteDatabase,
    migrations,
    readiness,
)
from src.data.repositories.readiness import ensure_database_ready


def database_for(path: Path) -> SQLiteDatabase:
    """Create a lazy owner for a disposable target."""
    return SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}", database_busy_timeout_ms=100))


def execute(path: Path, sql: str) -> None:
    """Apply an intentional test-only schema/data mutation and release the handle."""
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        connection.executescript(sql)


def _synthetic_migration_resources(tmp_path: Path, *, failing: bool) -> migrations.MigrationResources:
    """Materialize a two-revision graph (real base plus one synthetic child head).

    ``upgrade_database`` must run a real on-disk revision to reach the successful
    ``UPGRADED`` outcome, so the bundled base revision is copied and a single child
    revision is added. When ``failing`` is set that child applies a partial table and
    then raises, exercising the rollback path.
    """
    repository = Path(__file__).resolve().parents[3]
    source = repository / "alembic"
    directory = tmp_path / "synthetic-alembic"
    shutil.copytree(source, directory, ignore=shutil.ignore_patterns("__pycache__"))
    base_head = "0001_persistence"
    head = "zz99_synthetic_failing" if failing else "zz99_synthetic_no_op"
    preamble = "import sqlalchemy as sa\n\nfrom alembic import op\n\n" if failing else ""
    upgrade_body = (
        "    op.create_table('synthetic_partial', sa.Column('id', sa.Integer(), primary_key=True))\n"
        "    raise RuntimeError('synthetic failure')\n"
        if failing
        else "    pass\n"
    )
    revision = directory / "versions" / f"{head}.py"
    revision.write_text(
        preamble
        + f'revision: str = "{head}"\n'
        + f'down_revision: str = "{base_head}"\n\n'
        + "def upgrade() -> None:\n"
        + upgrade_body
        + "\ndef downgrade() -> None:\n    pass\n",
        encoding="utf-8",
    )
    return migrations.MigrationResources(directory, head, frozenset({base_head}))


@pytest.mark.parametrize("initial", ["missing", "zero_byte", "empty", "internal_only"])
def test_fresh_initialization_and_reopen_preserve_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initial: str
) -> None:
    path = tmp_path / "100% café.sqlite3"
    if initial == "zero_byte":
        path.touch()
    elif initial == "empty":
        execute(path, "PRAGMA user_version=0")
    elif initial == "internal_only":
        execute(path, "CREATE TABLE removed(id INTEGER PRIMARY KEY AUTOINCREMENT); DROP TABLE removed;")
    database = database_for(path)
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        with database.transaction() as connection:
            connection.exec_driver_sql("INSERT INTO schema_metadata VALUES ('retained_test_value', 42)")
    finally:
        database.close()

    def forbidden_upgrade(connection: Connection) -> None:
        del connection
        pytest.fail("A ready database must not run migrations again.")

    monkeypatch.setattr(readiness, "upgrade_fresh_database", forbidden_upgrade)
    reopened = database_for(path)
    try:
        assert ensure_database_ready(reopened) is ReadinessOutcome.READY
        with reopened.read() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT metadata_value FROM schema_metadata WHERE metadata_key='retained_test_value'"
                ).scalar_one()
                == 42
            )
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE unrelated (value TEXT); INSERT INTO unrelated VALUES ('retain me');",
        "CREATE VIEW unrelated AS SELECT 1;",
        "CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY NOT NULL);",
        "CREATE TABLE schema_metadata(metadata_key TEXT, metadata_value INTEGER);",
    ],
)
def test_nonempty_unversioned_storage_is_preserved(tmp_path: Path, sql: str) -> None:
    path = tmp_path / "existing.sqlite3"
    execute(path, sql)
    before = path.read_bytes()
    database = database_for(path)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.INCOMPATIBLE_SCHEMA
        assert path.read_bytes() == before
        with closing(sqlite3.connect(path, autocommit=True)) as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    finally:
        database.close()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM alembic_version;",
        "UPDATE alembic_version SET version_num='untrusted-secret-version';",
        "INSERT INTO alembic_version VALUES ('second');",
        "DROP TABLE market_price_observations;",
        "ALTER TABLE trajectory_events ADD COLUMN extra TEXT;",
        "ALTER TABLE trajectory_events DROP COLUMN error_json;",
        "DROP INDEX ix_trajectory_events_1;",
        "CREATE INDEX extra_index ON trajectory_events(event_type);",
        "CREATE INDEX expression_index ON trajectory_events(lower(event_type));",
        "DROP INDEX ix_trajectory_events_1; "
        "CREATE INDEX ix_trajectory_events_1 ON trajectory_events(session_id,timestamp DESC);",
        "CREATE VIEW extra_view AS SELECT 1;",
        "CREATE TRIGGER extra_trigger AFTER INSERT ON schema_metadata BEGIN SELECT 1; END;",
        "UPDATE schema_metadata SET metadata_value=2 WHERE metadata_key='persistence_encoding_version';",
        "DELETE FROM schema_metadata WHERE metadata_key='persistence_encoding_version';",
        "DROP TABLE schema_metadata; CREATE TABLE schema_metadata(metadata_key TEXT, metadata_value INTEGER);"
        "INSERT INTO schema_metadata VALUES ('persistence_encoding_version',1);",
    ],
)
def test_head_stamp_does_not_hide_schema_drift(tmp_path: Path, sql: str) -> None:
    path = tmp_path / "drift.sqlite3"
    database = database_for(path)
    try:
        ensure_database_ready(database)
        execute(path, sql)
        before = path.read_bytes()
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.INCOMPATIBLE_SCHEMA
        assert "untrusted-secret-version" not in str(caught.value)
        assert path.read_bytes() == before
    finally:
        database.close()


def test_corrupt_file_is_not_initialized(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"private payload that is not SQLite")
    database = database_for(path)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.INVALID_FILE
        assert "private payload" not in str(caught.value)
        assert path.read_bytes() == b"private payload that is not SQLite"
    finally:
        database.close()


def test_memory_uses_the_existing_instance_and_rejects_overlapping_scopes() -> None:
    database = SQLiteDatabase(ProjectSettings(database_url="sqlite:///:memory:"))
    other = SQLiteDatabase(ProjectSettings(database_url="sqlite:///:memory:"))
    try:
        assert database.database_path is None
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        assert ensure_database_ready(database) is ReadinessOutcome.READY
        with database.read(), pytest.raises(RuntimeError, match="sequential"):
            ensure_database_ready(database)
        assert ensure_database_ready(other) is ReadinessOutcome.INITIALIZED
    finally:
        database.close()
        other.close()


@pytest.mark.parametrize("stage", ["ddl", "version", "verification"])
def test_failed_initialization_rolls_back_and_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    database = database_for(tmp_path / "rollback.sqlite3")
    real_upgrade = migrations.upgrade_fresh_database

    def fail_upgrade(connection: Connection) -> None:
        if stage == "ddl":
            connection.exec_driver_sql("CREATE TABLE partial (id INTEGER)")
        else:
            real_upgrade(connection)
        if stage == "verification":
            connection.exec_driver_sql("DELETE FROM schema_metadata")
        else:
            raise RuntimeError("private migration exception")

    try:
        with monkeypatch.context() as context:
            context.setattr(readiness, "upgrade_fresh_database", fail_upgrade)
            with pytest.raises(DatabaseReadinessError) as caught:
                ensure_database_ready(database)
            assert caught.value.reason is ReadinessReason.INITIALIZATION_FAILED
            assert "private migration exception" not in str(caught.value)
        with database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table'").all() == []
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
    finally:
        database.close()


def test_missing_resources_precede_all_storage_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "absent" / "untouched.sqlite3"
    database = database_for(path)

    def missing() -> migrations.MigrationResources:
        raise ValueError("private installation path")

    monkeypatch.setattr(readiness, "migration_resources", missing)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.RESOURCES_UNAVAILABLE
        assert not path.parent.exists()
        assert "private installation path" not in str(caught.value)
    finally:
        database.close()


def test_known_ancestor_requires_explicit_upgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "older.sqlite3"
    database = database_for(path)
    try:
        ensure_database_ready(database)
        original = migrations.migration_resources()
        synthetic = replace(original, head="synthetic_next", ancestors=frozenset({original.head}))
        monkeypatch.setattr(readiness, "migration_resources", lambda: synthetic)
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.UPGRADE_REQUIRED
        assert "DATABASE_URL" in str(caught.value)
        assert caught.value.database_path == path
        assert caught.value.expected_revision == "synthetic_next"
    finally:
        database.close()


def test_upgrade_database_synthetic_older_schema_returns_upgraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "upgraded.sqlite3"
    database = database_for(path)
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        resources = _synthetic_migration_resources(tmp_path, failing=False)
        monkeypatch.setattr(readiness, "migration_resources", lambda: resources)
        outcome, revision = readiness.upgrade_database(database)
        assert outcome is ReadinessOutcome.UPGRADED
        assert revision == resources.head
        with closing(sqlite3.connect(path, autocommit=True)) as connection:
            stamped = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            assert stamped == resources.head
    finally:
        database.close()


def test_upgrade_database_synthetic_older_schema_rollback_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rollback.sqlite3"
    database = database_for(path)
    before = None
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        before = path.read_bytes()
        resources = _synthetic_migration_resources(tmp_path, failing=True)
        monkeypatch.setattr(readiness, "migration_resources", lambda: resources)
        with pytest.raises(DatabaseReadinessError) as caught:
            readiness.upgrade_database(database)
        assert caught.value.reason is ReadinessReason.MIGRATION_FAILED
        assert "synthetic failure" not in str(caught.value)
        with closing(sqlite3.connect(path, autocommit=True)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
            assert "synthetic_partial" not in tables
            stamped = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            assert stamped == "0001_persistence"
    finally:
        database.close()
    assert path.read_bytes() == before


def test_upgrade_database_synthetic_newer_schema_returns_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "current.sqlite3"
    database = database_for(path)
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        resources = _synthetic_migration_resources(tmp_path, failing=False)
        monkeypatch.setattr(readiness, "migration_resources", lambda: resources)
        first = readiness.upgrade_database(database)
        assert first[0] is ReadinessOutcome.UPGRADED
        outcome, revision = readiness.upgrade_database(database)
        assert outcome is ReadinessOutcome.READY
        assert revision == resources.head
    finally:
        database.close()


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (sqlite3.SQLITE_BUSY, ReadinessReason.BUSY),
        (sqlite3.SQLITE_LOCKED, ReadinessReason.BUSY),
        (sqlite3.SQLITE_READONLY, ReadinessReason.PERMISSION_DENIED),
        (sqlite3.SQLITE_AUTH, ReadinessReason.PERMISSION_DENIED),
        (sqlite3.SQLITE_PERM, ReadinessReason.PERMISSION_DENIED),
        (sqlite3.SQLITE_CORRUPT, ReadinessReason.INVALID_FILE),
        (sqlite3.SQLITE_NOTADB, ReadinessReason.INVALID_FILE),
        (sqlite3.SQLITE_IOERR, ReadinessReason.IO_ERROR),
        (sqlite3.SQLITE_CANTOPEN, ReadinessReason.IO_ERROR),
        (sqlite3.SQLITE_FULL, ReadinessReason.IO_ERROR),
        (sqlite3.SQLITE_BUSY | (2 << 8), ReadinessReason.BUSY),
    ],
)
def test_storage_codes_are_classified_without_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, reason: ReadinessReason
) -> None:
    database = database_for(tmp_path / "codes.sqlite3")

    def broken(database: SQLiteDatabase, resources: migrations.MigrationResources) -> bool:
        del database, resources
        error = sqlite3.OperationalError("private SQL and parameters")
        error.sqlite_errorcode = code
        raise error

    monkeypatch.setattr(readiness, "_file_ready", broken)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is reason
        assert "private SQL" not in str(caught.value)
    finally:
        database.close()


@pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM])
def test_sidecar_open_permission_failure_is_not_lock_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    database = database_for(tmp_path / "permission.sqlite3")

    def denied(*args: object, **kwargs: object) -> int:
        del args, kwargs
        raise PermissionError(code, "private path")

    monkeypatch.setattr("src.data.repositories.readiness_lock.os.open", denied)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.PERMISSION_DENIED
    finally:
        database.close()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("close REAL NOT NULL", "close TEXT NOT NULL"),
        ("close REAL NOT NULL", "close REAL"),
        ("close REAL NOT NULL", "close REAL NOT NULL DEFAULT 0"),
        ("entry_key TEXT NOT NULL", "entry_key TEXT COLLATE NOCASE NOT NULL"),
        ("row_position >= 0", "row_position >= -1"),
        ("ON DELETE CASCADE", "ON DELETE RESTRICT"),
        ("UNIQUE (entry_key, index_value)", "UNIQUE (index_value)"),
        ("PRIMARY KEY (entry_key, row_position)", "PRIMARY KEY (row_position, entry_key)"),
    ],
)
def test_constraints_and_column_shapes_are_verified(tmp_path: Path, old: str, new: str) -> None:
    path = tmp_path / "constraints.sqlite3"
    database = database_for(path)
    try:
        ensure_database_ready(database)
        with closing(sqlite3.connect(path, autocommit=True)) as connection:
            sql = connection.execute("SELECT sql FROM sqlite_schema WHERE name='market_price_observations'").fetchone()[
                0
            ]
            assert old in sql
            connection.execute("DROP TABLE market_price_observations")
            connection.execute(sql.replace(old, new))
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.INCOMPATIBLE_SCHEMA
    finally:
        database.close()


def test_resources_and_target_ignore_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = ProjectSettings(base_dir=tmp_path, database_url="sqlite:///nested/100% café.sqlite3")
    database = SQLiteDatabase(settings)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    try:
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
        assert database.database_path == tmp_path / "nested" / "100% café.sqlite3"
        assert not (other / "nested").exists()
    finally:
        database.close()


def test_migration_sql_error_is_initialization_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = database_for(tmp_path / "sql-error.sqlite3")

    def invalid_sql(connection: Connection) -> None:
        connection.exec_driver_sql("CREATE TABLE unfinished(id INTEGER)")
        connection.exec_driver_sql("not valid SQL")

    monkeypatch.setattr(readiness, "upgrade_fresh_database", invalid_sql)
    try:
        with pytest.raises(DatabaseReadinessError) as caught:
            ensure_database_ready(database)
        assert caught.value.reason is ReadinessReason.INITIALIZATION_FAILED
        with database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table'").all() == []
    finally:
        database.close()
