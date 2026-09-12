"""Hidden database maintenance commands preserve targets and output contracts."""

import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.config import ProjectSettings
from src.data.repositories import migrations, readiness, readiness_lock


@pytest.fixture
def target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Select disposable storage without touching operational settings."""
    path = tmp_path / "nested" / "selected.sqlite3"
    monkeypatch.setattr("src.cli_database.settings", ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    return path


def _synthetic_head_graph(tmp_path: Path) -> migrations.MigrationResources:
    """Copy the bundled base revision and append one no-op child head.

    ``db upgrade`` reports ``state == "upgraded"`` only when it runs a real
    on-disk revision, so the base graph is copied and a single child revision is
    added on top of it.
    """
    repository = Path(__file__).resolve().parent.parent
    source = repository / "alembic"
    directory = tmp_path / "cli-synthetic-alembic"
    shutil.copytree(source, directory, ignore=shutil.ignore_patterns("__pycache__"))
    head = "zz99_cli_synthetic"
    revision = directory / "versions" / f"{head}.py"
    revision.write_text(
        f'revision: str = "{head}"\n'
        + 'down_revision: str = "0001_persistence"\n\n'
        + "def upgrade() -> None:\n    pass\n\n"
        + "def downgrade() -> None:\n    pass\n",
        encoding="utf-8",
    )
    return migrations.MigrationResources(directory, head, frozenset({"0001_persistence"}))


def test_hidden_help_and_read_only_missing_status(target: Path) -> None:
    runner = CliRunner()
    assert "db" not in runner.invoke(app, ["--help"]).stdout.split()
    help_result = runner.invoke(app, ["db", "--help"])
    assert help_result.exit_code == 0
    assert "status" in help_result.stdout
    assert "upgrade" in help_result.stdout
    result = runner.invoke(app, ["db", "status", "--json"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["state"] == "missing"
    assert report["status"] == "success"
    assert report["database_path"] == str(target)
    assert report["schema_version"] == 1
    assert not target.parent.exists()
    assert not result.stderr


def test_explicit_upgrade_and_repeated_status(target: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(app, ["db", "upgrade", "--json"])
    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["state"] == "initialized"
    for command in ("status", "upgrade"):
        result = runner.invoke(app, ["db", command, "--json"])
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report["state"] == "ready"
        assert report["database_path"] == str(target)
        assert report["current_revision"] == report["expected_revision"] == "0001_persistence"
        assert not result.stderr


@pytest.mark.parametrize("command", ["status", "upgrade"])
def test_override_and_invalid_memory_target(target: Path, tmp_path: Path, command: str) -> None:
    other = tmp_path / "other.sqlite3"
    result = CliRunner().invoke(app, ["db", command, "--database-url", f"sqlite:///{other.as_posix()}", "--json"])
    assert result.exit_code == (1 if command == "status" else 0), result.output
    assert json.loads(result.stdout)["database_path"] == str(other)
    assert not target.parent.exists()
    invalid = CliRunner().invoke(app, ["db", command, "--database-url", "sqlite:///:memory:"])
    assert invalid.exit_code == 2


def test_incompatible_status_and_upgrade_preserve_storage(target: Path) -> None:
    target.parent.mkdir()
    with closing(sqlite3.connect(target, autocommit=True)) as connection:
        connection.execute("CREATE TABLE private_records (value TEXT)")
        connection.execute("INSERT INTO private_records VALUES ('secret-payload')")
    before = target.read_bytes()
    status = CliRunner().invoke(app, ["db", "status", "--json"])
    assert status.exit_code == 1
    assert json.loads(status.stdout)["state"] == "incompatible"
    assert not Path(str(target) + ".readiness.lock").exists()
    upgrade = CliRunner().invoke(app, ["db", "upgrade", "--json"])
    assert upgrade.exit_code == 1
    assert json.loads(upgrade.stdout)["reason"] == "database_incompatible_schema"
    assert "secret-payload" not in status.output + upgrade.output
    assert target.read_bytes() == before


@pytest.mark.parametrize("json_output", [False, True])
def test_corruption_is_sanitized(target: Path, json_output: bool) -> None:
    target.parent.mkdir()
    target.write_bytes(b"private-invalid-file")
    result = CliRunner().invoke(app, ["db", "status", *(["--json"] if json_output else [])])
    assert result.exit_code == 1
    if json_output:
        assert json.loads(result.stdout)["reason"] == "database_invalid_file"
        assert not result.stderr
    else:
        assert not result.stdout
        assert "not a readable SQLite" in result.stderr
    assert "private-invalid-file" not in result.output


def test_db_upgrade_command_synthetic_upgraded_success(
    target: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    initialized = runner.invoke(app, ["db", "upgrade", "--json"])
    assert initialized.exit_code == 0, initialized.output
    assert json.loads(initialized.stdout)["state"] == "initialized"
    resources = _synthetic_head_graph(tmp_path)
    monkeypatch.setattr(readiness, "migration_resources", lambda: resources)
    result = runner.invoke(app, ["db", "upgrade", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["status"] == "success"
    assert report["state"] == "upgraded"
    assert report["current_revision"] == report["expected_revision"] == resources.head
    assert report["database_path"] == str(target)
    assert not result.stderr


def test_db_upgrade_command_busy_lock(target: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def busy_lock(path: Path, timeout_ms: int) -> None:
        raise readiness_lock.ReadinessLockTimeoutError(f"synthetic busy lock for {path} after {timeout_ms} ms")

    monkeypatch.setattr(readiness, "readiness_lock", busy_lock)
    result = CliRunner().invoke(app, ["db", "upgrade", "--json"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["reason"] == "database_busy"
    assert report["state"] is None
    assert report["database_path"] == str(target)
    assert report["expected_revision"] == "0001_persistence"
    assert "synthetic busy lock" not in result.output


@pytest.mark.parametrize("json_output", [False, True])
def test_empty_status_is_fresh_and_does_not_create_sidecars(target: Path, json_output: bool) -> None:
    target.parent.mkdir()
    target.touch()
    before = set(target.parent.iterdir())
    result = CliRunner().invoke(app, ["db", "status", *(["--json"] if json_output else [])])
    assert result.exit_code == 1, result.output
    assert not result.stderr
    assert set(target.parent.iterdir()) == before
    assert target.read_bytes() == b""
    if json_output:
        report = json.loads(result.stdout)
        assert report["state"] == "fresh"
        assert report["status"] == "success"
        assert report["current_revision"] is None
        assert report["expected_revision"] == "0001_persistence"
        assert report["database_path"] == str(target)
        assert "db upgrade" in report["message"]
    else:
        assert "State: fresh" in result.stdout


@pytest.mark.parametrize("command", ["status", "upgrade"])
@pytest.mark.parametrize(
    "url", ["not-a-url", "postgresql://user:private-password@host/db", "sqlite:///file.db?mode=ro"]
)
def test_invalid_target_is_sanitized_usage_error(target: Path, command: str, url: str) -> None:
    result = CliRunner().invoke(app, ["db", command, "--database-url", url, "--json"])
    assert result.exit_code == 2
    assert not result.stdout
    assert "private-password" not in result.output
    assert not target.parent.exists()


@pytest.mark.parametrize("command", ["status", "upgrade"])
def test_missing_resources_emit_one_safe_report(target: Path, command: str) -> None:
    with patch.object(readiness, "migration_resources", side_effect=RuntimeError("private-resources")):
        result = CliRunner().invoke(app, ["db", command, "--json"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["reason"] == "database_resources_unavailable"
    assert report["expected_revision"] is None
    assert not result.stderr
    assert "private-resources" not in result.output
    assert not target.parent.exists()


def test_relative_override_keeps_base_directory_after_chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "base"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr("src.cli_database.settings", ProjectSettings(base_dir=base))
    monkeypatch.chdir(elsewhere)
    target = base / "nested" / "selected % café.sqlite3"
    result = CliRunner().invoke(
        app, ["db", "status", "--database-url", "sqlite:///nested/selected % café.sqlite3", "--json"]
    )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["database_path"] == str(target)
    assert not base.exists()
    assert not list(elsewhere.iterdir())
