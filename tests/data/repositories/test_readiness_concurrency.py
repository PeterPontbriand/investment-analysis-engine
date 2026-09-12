"""Spawned processes prove startup ownership and interrupted-DDL recovery."""

from __future__ import annotations

import multiprocessing as mp
import os
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import _ConnectionBase
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.config import Config
from sqlalchemy.engine import Connection

from alembic import command
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
from src.data.repositories.readiness_lock import readiness_lock


def _owner(path: str, channel: _ConnectionBase[object, object], crash: bool, mode: str = "automatic") -> None:
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{Path(path).as_posix()}"))
    original = migrations._run_on_connection if mode == "manual" else migrations.upgrade_fresh_database

    def paused_upgrade(connection: Connection) -> None:
        connection.exec_driver_sql("CREATE TABLE transient_probe (value INTEGER)")
        channel.send("migration-open")
        assert channel.recv() == "continue"
        if crash:
            os._exit(23)
        connection.exec_driver_sql("DROP TABLE transient_probe")
        original(connection)

    try:
        if mode == "manual":
            config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(path).as_posix()}".replace("%", "%%"))
            with patch.object(migrations, "_run_on_connection", paused_upgrade):
                command.upgrade(config, "head")
            channel.send("initialized")
        else:
            with patch.object(readiness, "upgrade_fresh_database", paused_upgrade):
                outcome = (
                    readiness.upgrade_database(database)[0] if mode == "explicit" else ensure_database_ready(database)
                )
                channel.send(outcome.value)
    finally:
        database.close()
        channel.close()


def _waiter(path: str, channel: _ConnectionBase[object, object], mode: str) -> None:
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{Path(path).as_posix()}"))
    original_lock = readiness_lock

    @contextmanager
    def signaled_lock(path: Path | None, timeout_ms: int) -> Iterator[None]:
        channel.send("requesting-ownership")
        with original_lock(path, timeout_ms):
            yield

    def forbidden_upgrade(connection: Connection) -> None:
        del connection
        raise AssertionError("The peer already initialized the database.")

    try:
        if mode == "manual":
            config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(path).as_posix()}".replace("%", "%%"))
            with patch.object(migrations, "readiness_lock", signaled_lock):
                command.upgrade(config, "head")
            channel.send("manual-upgrade-complete")
            return
        with (
            patch.object(readiness, "readiness_lock", signaled_lock),
            patch.object(readiness, "upgrade_fresh_database", forbidden_upgrade),
        ):
            outcome = readiness.upgrade_database(database)[0] if mode == "explicit" else ensure_database_ready(database)
            channel.send(outcome.value)
    finally:
        database.close()
        channel.close()


def _receive(channel: _ConnectionBase[object, object]) -> object:
    assert channel.poll(20), "Child process did not reach the expected synchronization point."
    return channel.recv()


@pytest.mark.parametrize("owner_mode", ["automatic", "manual", "explicit"])
@pytest.mark.parametrize("waiter_mode", ["automatic", "manual", "explicit"])
def test_two_processes_initialize_once(tmp_path: Path, owner_mode: str, waiter_mode: str) -> None:
    context = mp.get_context("spawn")
    owner_parent, owner_child = context.Pipe()
    waiter_parent, waiter_child = context.Pipe()
    path = str(tmp_path / "shared.sqlite3")
    owner = context.Process(target=_owner, args=(path, owner_child, False, owner_mode))
    waiter = context.Process(target=_waiter, args=(path, waiter_child, waiter_mode))
    owner.start()
    try:
        assert _receive(owner_parent) == "migration-open"
        waiter.start()
        assert _receive(waiter_parent) == "requesting-ownership"
        owner_parent.send("continue")
        assert _receive(owner_parent) == "initialized"
        assert _receive(waiter_parent) == ("manual-upgrade-complete" if waiter_mode == "manual" else "ready")
        owner.join(20)
        waiter.join(20)
        assert owner.exitcode == waiter.exitcode == 0
    finally:
        for process in (owner, waiter):
            if process.is_alive():
                process.terminate()
                process.join(20)
        for channel in (owner_parent, owner_child, waiter_parent, waiter_child):
            channel.close()


def test_interrupted_process_releases_ownership_and_rolls_back(tmp_path: Path) -> None:
    context = mp.get_context("spawn")
    parent, child = context.Pipe()
    path = tmp_path / "interrupted.sqlite3"
    process = context.Process(target=_owner, args=(str(path), child, True))
    process.start()
    try:
        assert _receive(parent) == "migration-open"
        parent.send("continue")
        process.join(20)
        assert process.exitcode == 23
        database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
        try:
            assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
            with database.read() as connection:
                assert (
                    connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE name='transient_probe'").all()
                    == []
                )
        finally:
            database.close()
    finally:
        if process.is_alive():
            process.terminate()
            process.join(20)
        parent.close()
        child.close()


def test_ownership_timeout_is_classified_and_sidecar_is_retained(tmp_path: Path) -> None:
    path = tmp_path / "busy.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}", database_busy_timeout_ms=10))
    try:
        with readiness_lock(path, 10):
            with pytest.raises(DatabaseReadinessError) as caught:
                ensure_database_ready(database)
            assert caught.value.reason is ReadinessReason.BUSY
            assert not path.exists()
        assert Path(str(path) + ".readiness.lock").exists()
        assert ensure_database_ready(database) is ReadinessOutcome.INITIALIZED
    finally:
        database.close()
