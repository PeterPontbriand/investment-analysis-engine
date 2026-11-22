"""The storage-error rule and its conversion by the database scopes: which errors become a typed database error."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.database_errors import DatabaseError, DatabaseReason, storage_reason
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from tests._database_lock import SHORT_WAIT_MS, held_lock


def _raw(code: int) -> sqlite3.OperationalError:
    """Return a SQLite error carrying ``code`` as the driver sets it."""
    error = sqlite3.OperationalError("driver text that must not reach a client")
    error.sqlite_errorcode = code
    return error


_FAMILIES = [
    (sqlite3.SQLITE_BUSY, DatabaseReason.BUSY),
    (sqlite3.SQLITE_LOCKED, DatabaseReason.BUSY),
    (sqlite3.SQLITE_READONLY, DatabaseReason.PERMISSION_DENIED),
    (sqlite3.SQLITE_PERM, DatabaseReason.PERMISSION_DENIED),
    (sqlite3.SQLITE_AUTH, DatabaseReason.PERMISSION_DENIED),
    (sqlite3.SQLITE_NOTADB, DatabaseReason.INVALID_FILE),
    (sqlite3.SQLITE_CORRUPT, DatabaseReason.INVALID_FILE),
    (sqlite3.SQLITE_IOERR, DatabaseReason.IO_ERROR),
    (sqlite3.SQLITE_FULL, DatabaseReason.IO_ERROR),
    (sqlite3.SQLITE_CANTOPEN, DatabaseReason.IO_ERROR),
]
_EXTENDED = [
    (sqlite3.SQLITE_BUSY | (2 << 8), DatabaseReason.BUSY),
    (sqlite3.SQLITE_READONLY | (5 << 8), DatabaseReason.PERMISSION_DENIED),
    (sqlite3.SQLITE_IOERR | (10 << 8), DatabaseReason.IO_ERROR),
]
_NOT_STORAGE = [
    sqlite3.SQLITE_ERROR,
    sqlite3.SQLITE_CONSTRAINT,
    sqlite3.SQLITE_MISUSE,
    sqlite3.SQLITE_INTERNAL,
    sqlite3.SQLITE_TOOBIG,
    sqlite3.SQLITE_CONSTRAINT | (8 << 8),
]


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    settings = ProjectSettings(
        database_url=f"sqlite:///{(tmp_path / 'db/test.sqlite3').as_posix()}", database_busy_timeout_ms=SHORT_WAIT_MS
    )
    database = SQLiteDatabase(settings)
    yield database
    database.close()


@pytest.mark.parametrize(("code", "reason"), [*_FAMILIES, *_EXTENDED])
def test_each_storage_code_family_maps_to_its_reason(code: int, reason: DatabaseReason) -> None:
    error = _raw(code)

    assert storage_reason(error) is reason
    wrapped = OperationalError("SELECT 1", {}, error)
    assert storage_reason(wrapped) is reason


@pytest.mark.parametrize("code", _NOT_STORAGE)
def test_a_code_outside_the_families_is_not_a_storage_error(code: int) -> None:
    assert storage_reason(_raw(code)) is None
    assert storage_reason(OperationalError("SELECT 1", {}, _raw(code))) is None


def test_a_sqlite_error_without_a_code_and_a_foreign_exception_are_not_storage_errors() -> None:
    assert storage_reason(sqlite3.Error("no code")) is None
    assert storage_reason(RuntimeError("boom")) is None


def test_a_raw_os_error_is_classified_as_readiness_classifies_it() -> None:
    assert storage_reason(PermissionError(13, "denied")) is DatabaseReason.PERMISSION_DENIED
    assert storage_reason(OSError(5, "disk")) is DatabaseReason.IO_ERROR


@pytest.mark.parametrize(("code", "reason"), _FAMILIES)
def test_a_scope_re_raises_a_storage_error_as_the_typed_error_chained_from_the_raw_one(
    database: SQLiteDatabase, code: int, reason: DatabaseReason
) -> None:
    raw = _raw(code)
    for scope in (database.transaction, database.read):
        with pytest.raises(DatabaseError) as caught, scope():
            raise raw
        assert caught.value.reason is reason
        assert caught.value.__cause__ is raw
        assert (caught.value.database_path, caught.value.expected_revision) == (database.database_path, None)
        assert "driver text" not in str(caught.value)


def test_a_scope_converts_a_storage_error_a_statement_raises(database: SQLiteDatabase) -> None:
    with pytest.raises(DatabaseError) as caught, database.read() as reader:
        reader.exec_driver_sql("CREATE TABLE forbidden (id INTEGER)")

    assert isinstance(caught.value.__cause__, OperationalError)
    assert caught.value.reason is DatabaseReason.PERMISSION_DENIED


def test_a_real_lock_is_database_busy_in_a_transaction_scope(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER)")
    path = database.database_path
    assert path is not None

    with held_lock(path), pytest.raises(DatabaseError) as caught, database.transaction() as second:
        second.exec_driver_sql("INSERT INTO sample VALUES (1)")

    assert caught.value.reason is DatabaseReason.BUSY


def test_a_real_lock_is_database_busy_when_the_connection_opens(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER)")
    path = database.database_path
    assert path is not None

    with held_lock(path, block_reads=True), pytest.raises(DatabaseError) as caught, database.read():
        pass

    assert caught.value.reason is DatabaseReason.BUSY


def test_a_file_that_is_not_a_database_is_database_invalid_file_when_the_connection_opens(tmp_path: Path) -> None:
    path = tmp_path / "junk.sqlite3"
    path.write_bytes(b"this is not a database file " * 100)
    junk = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with pytest.raises(DatabaseError) as caught, junk.read():
            pass
    finally:
        junk.close()

    assert caught.value.reason is DatabaseReason.INVALID_FILE


def test_a_target_that_cannot_be_opened_is_database_io_error(tmp_path: Path) -> None:
    folder = tmp_path / "a-folder.sqlite3"
    folder.mkdir()
    unopenable = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{folder.as_posix()}"))
    try:
        with pytest.raises(DatabaseError) as caught, unopenable.read():
            pass
    finally:
        unopenable.close()

    assert caught.value.reason is DatabaseReason.IO_ERROR


def test_a_constraint_violation_stays_a_raw_error(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO sample VALUES (1)")
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.exec_driver_sql("INSERT INTO sample VALUES (1)")


def test_an_error_outside_the_families_stays_raw(database: SQLiteDatabase) -> None:
    with pytest.raises(OperationalError, match="syntax"), database.read() as reader:
        reader.exec_driver_sql("SELEKT 1")
    raw = _raw(sqlite3.SQLITE_MISUSE)
    with pytest.raises(sqlite3.OperationalError) as caught, database.transaction():
        raise raw
    assert caught.value is raw


def test_an_os_error_and_a_defect_pass_through_a_scope_unchanged(database: SQLiteDatabase) -> None:
    with pytest.raises(PermissionError), database.transaction():
        raise PermissionError(13, "denied")
    with pytest.raises(ValueError, match="defect"), database.read():
        raise ValueError("defect")
