"""SQLite infrastructure tests use isolated files and test-only tables."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from src.config import ProjectSettings
from src.data.repositories import SQLiteDatabase


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    configured = ProjectSettings(
        database_url=f"sqlite:///{(tmp_path / 'db/test.sqlite3').as_posix()}", database_busy_timeout_ms=25
    )
    database = SQLiteDatabase(configured)
    yield database
    database.close()


def test_each_fresh_connection_has_policy_and_no_application_tables(database: SQLiteDatabase) -> None:
    with database.read() as first, database.read() as second:
        assert first.connection.dbapi_connection is not second.connection.dbapi_connection
        for connection in (first, second):
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 25
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []
    assert first.closed
    assert second.closed


def test_commit_survives_new_engine(database: SQLiteDatabase, tmp_path: Path) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO sample VALUES (1)")
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'db/test.sqlite3').as_posix()}"))
    try:
        with reopened.read() as connection:
            assert connection.exec_driver_sql("SELECT id FROM sample").scalars().all() == [1]
    finally:
        reopened.close()


def test_failed_write_rolls_back_entire_scope(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER PRIMARY KEY)")

    def conflicting_write() -> None:
        with database.transaction() as connection:
            connection.exec_driver_sql("INSERT INTO sample VALUES (1)")
            connection.exec_driver_sql("INSERT INTO sample VALUES (1)")

    with pytest.raises(IntegrityError):
        conflicting_write()
    with database.read() as connection:
        assert connection.exec_driver_sql("SELECT id FROM sample").scalars().all() == []


def test_ddl_is_rolled_back_on_application_error(database: SQLiteDatabase) -> None:
    def aborted_ddl() -> None:
        with database.transaction() as connection:
            connection.exec_driver_sql("CREATE TABLE aborted (id INTEGER)")
            raise ValueError("abort")

    with pytest.raises(ValueError, match="abort"):
        aborted_ddl()
    with database.read() as connection:
        assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='aborted'").all() == []


def test_foreign_keys_are_enforced(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.exec_driver_sql("INSERT INTO child VALUES (99)")


def test_reader_keeps_snapshot_while_writer_commits(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER)")
        connection.exec_driver_sql("INSERT INTO sample VALUES (1)")
    with database.read() as reader:
        assert reader.exec_driver_sql("SELECT id FROM sample").scalars().all() == [1]
        with database.transaction() as writer:
            writer.exec_driver_sql("INSERT INTO sample VALUES (2)")
        assert reader.exec_driver_sql("SELECT id FROM sample").scalars().all() == [1]
    with database.read() as reader:
        assert reader.exec_driver_sql("SELECT id FROM sample ORDER BY id").scalars().all() == [1, 2]


def test_read_scope_rejects_writes(database: SQLiteDatabase) -> None:
    with pytest.raises(OperationalError, match="readonly"), database.read() as reader:
        reader.exec_driver_sql("CREATE TABLE forbidden (id INTEGER)")


def test_competing_writer_fails_at_configured_timeout(database: SQLiteDatabase) -> None:
    with database.transaction() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER)")
    with database.transaction() as first:
        first.exec_driver_sql("INSERT INTO sample VALUES (1)")
        with pytest.raises(OperationalError, match="locked"), database.transaction() as second:
            second.exec_driver_sql("INSERT INTO sample VALUES (2)")
    with database.read() as reader:
        assert reader.exec_driver_sql("SELECT id FROM sample").scalars().all() == [1]


def test_close_guards_active_scopes_and_rejects_reuse(database: SQLiteDatabase) -> None:
    with database.read(), pytest.raises(RuntimeError, match="active"):
        database.close()
    database.close()
    database.close()
    with pytest.raises(RuntimeError, match="closed"), database.transaction():
        pytest.fail("Closed database returned a connection")


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_memory_database_is_sequential_and_retains_data(url: str) -> None:
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        with database.transaction() as connection:
            connection.exec_driver_sql("CREATE TABLE sample (id INTEGER)")
        with database.read() as reader:
            assert reader.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "memory"
            with pytest.raises(RuntimeError, match="sequential"), database.read():
                pytest.fail("Overlapping memory scope was accepted")
        with database.transaction() as writer:
            writer.exec_driver_sql("INSERT INTO sample VALUES (1)")
        with database.read() as reader:
            assert reader.exec_driver_sql("SELECT id FROM sample").scalars().all() == [1]
    finally:
        database.close()


def test_construction_is_lazy_and_file_handles_are_released(tmp_path: Path) -> None:
    path = tmp_path / "lazy.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    assert not path.exists()
    with database.read():
        pass
    database.close()
    # Windows refuses this rename if an open connection retains the file handle.
    renamed = path.rename(tmp_path / "released.sqlite3")
    assert renamed.exists()
