"""Conservative SQLite readiness with atomic initialization of empty storage."""

import errno
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from src.data.repositories.migrations import (
    MigrationResources,
    migration_resources,
    upgrade_database_revision,
    upgrade_fresh_database,
)
from src.data.repositories.readiness_lock import ReadinessLockTimeoutError, readiness_lock
from src.data.repositories.schema import metadata
from src.data.repositories.sqlite import SQLiteDatabase


class ReadinessOutcome(StrEnum):
    """Successful readiness disposition without an investor-facing preamble."""

    READY = "ready"
    INITIALIZED = "initialized"
    UPGRADED = "upgraded"


class ReadinessReason(StrEnum):
    """Stable failure categories independent of driver exception wording."""

    UPGRADE_REQUIRED = "database_upgrade_required"
    INCOMPATIBLE_SCHEMA = "database_incompatible_schema"
    BUSY = "database_busy"
    PERMISSION_DENIED = "database_permission_denied"
    INVALID_FILE = "database_invalid_file"
    IO_ERROR = "database_io_error"
    RESOURCES_UNAVAILABLE = "database_resources_unavailable"
    INITIALIZATION_FAILED = "database_initialization_failed"
    MIGRATION_FAILED = "database_migration_failed"


_MESSAGES = {
    ReadinessReason.MIGRATION_FAILED: (
        "schema migration did not complete. Preserve this database and inspect application diagnostics; "
        "the migration transaction was rolled back."
    ),
    ReadinessReason.UPGRADE_REQUIRED: (
        "schema upgrade required. Stop application processes and back up this database, then run "
        "uv run --no-sync alembic upgrade head from the installation folder with DATABASE_URL set to this target."
    ),
    ReadinessReason.INCOMPATIBLE_SCHEMA: (
        "schema is incompatible or incomplete. Preserve this database and inspect it with the matching "
        "application version; automatic initialization was not performed."
    ),
    ReadinessReason.BUSY: (
        "readiness could not acquire storage access within the configured wait. "
        "Close other database operations and retry."
    ),
    ReadinessReason.PERMISSION_DENIED: "access was denied. Check permissions for this file and its parent directory.",
    ReadinessReason.INVALID_FILE: (
        "the file is not a readable SQLite database or is corrupt. "
        "Preserve it and inspect or restore it before retrying."
    ),
    ReadinessReason.IO_ERROR: "storage could not be accessed. Check the path, available storage and filesystem health.",
    ReadinessReason.RESOURCES_UNAVAILABLE: (
        "migration resources are unavailable or inconsistent. Use a complete matching source installation; "
        "the database was not initialized."
    ),
    ReadinessReason.INITIALIZATION_FAILED: (
        "fresh initialization did not complete. "
        "Preserve this file and inspect application diagnostics before retrying; "
        "no partial schema was accepted."
    ),
}


class DatabaseReadinessError(RuntimeError):
    """Sanitized storage error with read-only safe evidence and a chained cause."""

    def __init__(
        self, reason: ReadinessReason, database_path: Path | None, expected_revision: str | None = None
    ) -> None:
        """Retain the category/target without incorporating raw driver messages."""
        self._reason = reason
        self._database_path = database_path
        self._expected_revision = expected_revision
        target = "in-memory database" if database_path is None else json.dumps(str(database_path), ensure_ascii=True)
        super().__init__(f"Database {target}: {_MESSAGES[reason]}")

    @property
    def reason(self) -> ReadinessReason:
        """Return the stable error category."""
        return self._reason

    @property
    def database_path(self) -> Path | None:
        """Return the configured target, never a fallback database."""
        return self._database_path

    @property
    def expected_revision(self) -> str | None:
        """Return the verified bundled revision, when resource discovery succeeded."""
        return self._expected_revision


class _SchemaMismatchError(Exception):
    pass


class _UpgradeRequiredError(Exception):
    pass


class DatabaseState(StrEnum):
    """Observable persistent storage states, without initialization side effects."""

    READY = "ready"
    MISSING = "missing"
    FRESH = "fresh"
    UPGRADE_REQUIRED = "upgrade_required"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class DatabaseInspection:
    """Safe evidence from a single inspection snapshot."""

    state: DatabaseState
    current_revision: str | None
    expected_revision: str


def _schema_objects(connection: Connection) -> dict[tuple[str, str], str | None]:
    return {
        (kind, name): _sql(sql)
        for kind, name, sql in connection.exec_driver_sql("SELECT type, name, sql FROM sqlite_schema")
        if not name.startswith("sqlite_")
    }


def _verify_ancestor(connection: Connection, resources: MigrationResources, revision: str) -> None:
    # Build only the trusted bundled schema in disposable memory. Never use current
    # metadata as a substitute for the schema that this older revision actually owns.
    engine = sa.create_engine(
        "sqlite://", creator=lambda: sqlite3.connect(":memory:", autocommit=False), poolclass=NullPool
    )
    try:
        with engine.begin() as reference:
            upgrade_database_revision(reference, resources, revision)
            if _schema_objects(connection) != _schema_objects(reference):
                raise _SchemaMismatchError()
            if ("table", "schema_metadata") in _schema_objects(reference):
                required = reference.exec_driver_sql("SELECT metadata_key, metadata_value FROM schema_metadata").all()
                metadata_rows = connection.exec_driver_sql("SELECT metadata_key, metadata_value FROM schema_metadata")
                actual = {key: value for key, value in metadata_rows}  # noqa: C416
                if any(actual.get(key) != value for key, value in required):
                    raise _SchemaMismatchError()
    finally:
        engine.dispose()


def _sql(value: object) -> str | None:
    if value is None:
        return None
    # Preserve literal/quoted-identifier content when normalizing SQL spacing.
    return re.sub(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\s+",
        lambda match: match[0] if match[0][0] in "'\"" else " ",
        str(value),
    ).strip()


def _expected_signature(table: sa.Table, connection: Connection) -> dict[str, Any]:
    return {
        "columns": [
            (
                column.name,
                str(column.type.compile(dialect=connection.dialect)),
                column.nullable,
                _sql(column.server_default.arg) if isinstance(column.server_default, sa.DefaultClause) else None,
            )
            for column in table.columns
        ],
        "pk": (table.primary_key.name, tuple(column.name for column in table.primary_key)),
        "unique": {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        },
        "checks": {
            (constraint.name, _sql(constraint.sqltext))
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        },
        "fk": {
            (
                constraint.name,
                tuple(element.parent.name for element in constraint.elements),
                constraint.elements[0].column.table.name,
                tuple(element.column.name for element in constraint.elements),
                constraint.ondelete,
                constraint.onupdate,
            )
            for constraint in table.constraints
            if isinstance(constraint, sa.ForeignKeyConstraint)
        },
        "indexes": {
            (index.name, tuple(column.name for column in index.columns), bool(index.unique)) for index in table.indexes
        },
    }


def _actual_signature(table: str, inspector: sa.Inspector) -> dict[str, Any]:
    primary = inspector.get_pk_constraint(table)
    indexes = inspector.get_indexes(table)
    # Partial/expression/sorted indexes are not interchangeable with this schema's indexes.
    if any(item.get("dialect_options") or item.get("column_sorting") for item in indexes):
        raise _SchemaMismatchError()
    return {
        "columns": [
            (column["name"], str(column["type"]), column["nullable"], _sql(column["default"]))
            for column in inspector.get_columns(table)
        ],
        "pk": (primary["name"], tuple(primary["constrained_columns"])),
        "unique": {(item["name"], tuple(item["column_names"])) for item in inspector.get_unique_constraints(table)},
        "checks": {(item["name"], _sql(item["sqltext"])) for item in inspector.get_check_constraints(table)},
        "fk": {
            (
                item["name"],
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
                item["options"].get("ondelete"),
                item["options"].get("onupdate"),
            )
            for item in inspector.get_foreign_keys(table)
        },
        "indexes": {(item["name"], tuple(item["column_names"]), bool(item["unique"])) for item in indexes},
    }


def _schema_ready(connection: Connection, resources: MigrationResources) -> bool:  # noqa: PLR0912
    objects = connection.exec_driver_sql("SELECT type, name, sql FROM sqlite_schema").tuples().all()
    objects = [(kind, name, sql) for kind, name, sql in objects if not name.startswith("sqlite_")]
    if not objects:
        return False
    if not any(kind == "table" and name == "alembic_version" for kind, name, _ in objects):
        raise _SchemaMismatchError()
    columns = sa.inspect(connection).get_columns("alembic_version")
    if [column["name"] for column in columns] != ["version_num"]:
        raise _SchemaMismatchError()
    revisions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
    if len(revisions) != 1:
        raise _SchemaMismatchError()
    if revisions[0] in resources.ancestors:
        _verify_ancestor(connection, resources, revisions[0])
        raise _UpgradeRequiredError()
    tables = {name for kind, name, _ in objects if kind == "table"}
    if tables != set(metadata.tables) | {"alembic_version"} or any(
        kind in ("view", "trigger") for kind, _, _ in objects
    ):
        raise _SchemaMismatchError()
    if {name for kind, name, _ in objects if kind == "index"} != {
        index.name for table in metadata.tables.values() for index in table.indexes
    }:
        raise _SchemaMismatchError()
    inspector = sa.inspect(connection)
    version = sa.Table(
        "alembic_version",
        sa.MetaData(),
        sa.Column("version_num", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name="alembic_version_pkc"),
    )
    if _actual_signature(version.name, inspector) != _expected_signature(version, connection):
        raise _SchemaMismatchError()
    revisions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
    if len(revisions) != 1:
        raise _SchemaMismatchError()
    # Check metadata structure before querying its required encoding value.
    if _actual_signature("schema_metadata", inspector) != _expected_signature(
        metadata.tables["schema_metadata"], connection
    ):
        raise _SchemaMismatchError()
    encoding = (
        connection.exec_driver_sql(
            "SELECT metadata_value FROM schema_metadata WHERE metadata_key='persistence_encoding_version'"
        )
        .scalars()
        .all()
    )
    if encoding != [1]:
        raise _SchemaMismatchError()
    if revisions[0] != resources.head:
        raise _SchemaMismatchError()
    for table in metadata.sorted_tables:
        if _actual_signature(table.name, inspector) != _expected_signature(table, connection):
            raise _SchemaMismatchError()
    _verify_ddl(connection, {name: sql for _, name, sql in objects}, version)
    return True


def _verify_ddl(connection: Connection, actual: dict[str, str], version: sa.Table) -> None:
    # SQLite reflection omits some collations, index ordering and conflict clauses.
    # The supported Alembic schema must also match canonical dialect DDL.
    for table in (version, *metadata.sorted_tables):
        if _sql(actual[table.name]) != _sql(sa.schema.CreateTable(table).compile(dialect=connection.dialect)):
            raise _SchemaMismatchError()
        for index in table.indexes:
            assert index.name is not None
            if _sql(actual[index.name]) != _sql(sa.schema.CreateIndex(index).compile(dialect=connection.dialect)):
                raise _SchemaMismatchError()


def _file_ready(database: SQLiteDatabase, resources: MigrationResources) -> bool:
    path = database.database_path
    assert path is not None
    try:
        path.stat()
    except FileNotFoundError:
        return False
    with _read_file(database) as connection:
        return _schema_ready(connection, resources)


@contextmanager
def _read_file(database: SQLiteDatabase) -> Iterator[Connection]:
    path = database.database_path
    assert path is not None

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=database.busy_timeout_ms / 1_000, autocommit=False
        )

    engine = sa.create_engine("sqlite://", creator=connect, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def _storage_reason(error: Exception) -> ReadinessReason:
    if isinstance(error, ReadinessLockTimeoutError):
        return ReadinessReason.BUSY
    original = error.orig if isinstance(error, DBAPIError) else error
    code = getattr(original, "sqlite_errorcode", None)
    if isinstance(code, int):
        primary = code & 0xFF
        if primary in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            return ReadinessReason.BUSY
        if primary in (sqlite3.SQLITE_READONLY, sqlite3.SQLITE_PERM, sqlite3.SQLITE_AUTH):
            return ReadinessReason.PERMISSION_DENIED
        if primary in (sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_CORRUPT):
            return ReadinessReason.INVALID_FILE
    if isinstance(original, OSError) and original.errno in (errno.EACCES, errno.EPERM):
        return ReadinessReason.PERMISSION_DENIED
    return ReadinessReason.IO_ERROR


def _initialize(database: SQLiteDatabase, resources: MigrationResources) -> ReadinessOutcome:
    with database.transaction() as connection:
        if _schema_ready(connection, resources):
            return ReadinessOutcome.READY
        try:
            upgrade_fresh_database(connection)
            if not _schema_ready(connection, resources):
                raise _SchemaMismatchError()
        except Exception as exc:
            original = exc.orig if isinstance(exc, DBAPIError) else exc
            code = getattr(original, "sqlite_errorcode", None)
            storage_failure = isinstance(original, OSError) or (
                isinstance(code, int)
                and (code & 0xFF)
                in (
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                    sqlite3.SQLITE_READONLY,
                    sqlite3.SQLITE_PERM,
                    sqlite3.SQLITE_AUTH,
                    sqlite3.SQLITE_NOTADB,
                    sqlite3.SQLITE_CORRUPT,
                    sqlite3.SQLITE_IOERR,
                    sqlite3.SQLITE_FULL,
                    sqlite3.SQLITE_CANTOPEN,
                )
            )
            raise DatabaseReadinessError(
                _storage_reason(exc) if storage_failure else ReadinessReason.INITIALIZATION_FAILED,
                database.database_path,
                resources.head,
            ) from exc
    return ReadinessOutcome.INITIALIZED


def ensure_database_ready(database: SQLiteDatabase) -> ReadinessOutcome:
    """Verify storage or atomically initialize a proven empty database.

    Existing incompatible files are inspected read-only before application
    connection policy runs. The caller retains ownership of the database.
    """
    path = database.database_path
    try:
        resources = migration_resources()
    except Exception as exc:
        raise DatabaseReadinessError(ReadinessReason.RESOURCES_UNAVAILABLE, path) from exc
    try:
        with readiness_lock(path, database.busy_timeout_ms):
            if path is not None and _file_ready(database, resources):
                return ReadinessOutcome.READY
            return _initialize(database, resources)
    except _SchemaMismatchError as exc:
        raise DatabaseReadinessError(ReadinessReason.INCOMPATIBLE_SCHEMA, path, resources.head) from exc
    except _UpgradeRequiredError as exc:
        raise DatabaseReadinessError(ReadinessReason.UPGRADE_REQUIRED, path, resources.head) from exc
    except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
        raise DatabaseReadinessError(_storage_reason(exc), path, resources.head) from exc


def _inspect_connection(connection: Connection, resources: MigrationResources) -> DatabaseInspection:
    try:
        ready = _schema_ready(connection, resources)
    except _SchemaMismatchError:
        return DatabaseInspection(DatabaseState.INCOMPATIBLE, None, resources.head)
    except _UpgradeRequiredError:
        revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
        return DatabaseInspection(DatabaseState.UPGRADE_REQUIRED, revision, resources.head)
    return DatabaseInspection(
        DatabaseState.READY if ready else DatabaseState.FRESH,
        resources.head if ready else None,
        resources.head,
    )


def _inspection(database: SQLiteDatabase, resources: MigrationResources) -> DatabaseInspection:
    path = database.database_path
    if path is None:
        raise ValueError("Persistent inspection requires a file-backed database.")
    try:
        path.stat()
    except FileNotFoundError:
        return DatabaseInspection(DatabaseState.MISSING, None, resources.head)
    with _read_file(database) as connection:
        return _inspect_connection(connection, resources)


def _resources(database: SQLiteDatabase) -> MigrationResources:
    try:
        return migration_resources()
    except Exception as exc:
        raise DatabaseReadinessError(ReadinessReason.RESOURCES_UNAVAILABLE, database.database_path) from exc


def inspect_database(database: SQLiteDatabase) -> DatabaseInspection:
    """Inspect one read-only snapshot without acquiring a sidecar or initializing."""
    resources = _resources(database)
    try:
        return _inspection(database, resources)
    except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
        raise DatabaseReadinessError(_storage_reason(exc), database.database_path, resources.head) from exc


def upgrade_database(database: SQLiteDatabase) -> tuple[ReadinessOutcome, str]:
    """Explicitly upgrade validated storage and return its outcome and head revision."""
    resources = _resources(database)
    path = database.database_path
    if path is None:
        raise ValueError("Persistent maintenance requires a file-backed database.")
    try:
        with readiness_lock(path, database.busy_timeout_ms):
            observed = _inspection(database, resources)
            if observed.state is DatabaseState.INCOMPATIBLE:
                raise DatabaseReadinessError(ReadinessReason.INCOMPATIBLE_SCHEMA, path, resources.head)
            if observed.state is DatabaseState.READY:
                return ReadinessOutcome.READY, resources.head
            if observed.state in (DatabaseState.MISSING, DatabaseState.FRESH):
                return _initialize(database, resources), resources.head
            try:
                with database.transaction() as connection:
                    rechecked = _inspect_connection(connection, resources)
                    if rechecked.state is DatabaseState.READY:
                        return ReadinessOutcome.READY, resources.head
                    if rechecked.state is not DatabaseState.UPGRADE_REQUIRED:
                        raise DatabaseReadinessError(ReadinessReason.INCOMPATIBLE_SCHEMA, path, resources.head)
                    upgrade_database_revision(connection, resources, resources.head)
                    if not _schema_ready(connection, resources):
                        raise _SchemaMismatchError()
            except DatabaseReadinessError:
                raise
            except Exception as exc:
                reason = _storage_reason(exc)
                original = exc.orig if isinstance(exc, DBAPIError) else exc
                # SQL syntax/migration logic failures are migration failures, not I/O.
                if not isinstance(original, OSError) and reason is ReadinessReason.IO_ERROR:
                    code = getattr(original, "sqlite_errorcode", None)
                    if not isinstance(code, int) or (code & 0xFF) not in (
                        sqlite3.SQLITE_IOERR,
                        sqlite3.SQLITE_FULL,
                        sqlite3.SQLITE_CANTOPEN,
                    ):
                        reason = ReadinessReason.MIGRATION_FAILED
                raise DatabaseReadinessError(reason, path, resources.head) from exc
            return ReadinessOutcome.UPGRADED, resources.head
    except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
        raise DatabaseReadinessError(_storage_reason(exc), path, resources.head) from exc
