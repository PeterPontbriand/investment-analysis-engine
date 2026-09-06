"""Focused tests for application settings used by user-facing runtime setup."""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from src.config import ProjectSettings


@pytest.fixture(autouse=True)
def isolate_persistence_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "base_dir",
        "data_dir",
        "database_url",
        "database_busy_timeout_ms",
        "historical_cache_ttl_seconds",
        "telemetry_sink",
    ):
        monkeypatch.delenv(name, raising=False)


def test_project_settings_reads_sec_user_agent_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    declared_identity = "financial-data-agents-test test@example.invalid"
    monkeypatch.setenv("SEC_USER_AGENT", declared_identity)

    configured = ProjectSettings()

    assert configured.sec_user_agent == declared_identity


def test_project_settings_reads_nested_reliability_limit_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reliability caps can be changed through the existing nested settings convention."""
    monkeypatch.setenv("reliability_limits__overall_timeout_seconds", "240")

    configured = ProjectSettings()

    assert configured.reliability_limits.overall_timeout_seconds == 240


def test_database_defaults_follow_configured_base(tmp_path: Path) -> None:
    configured = ProjectSettings(base_dir=tmp_path)

    assert configured.data_dir == tmp_path / "data"
    assert make_url(configured.database_url).database == (tmp_path / "data/financial-data-agents.sqlite3").as_posix()
    assert configured.database_busy_timeout_ms == 5_000
    assert configured.historical_cache_ttl_seconds == 3_600
    assert configured.telemetry_sink == "jsonl"
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("relative", [True, False])
def test_database_default_follows_data_directory(tmp_path: Path, relative: bool) -> None:
    data_path = Path("custom data") if relative else tmp_path / "external data"
    configured = ProjectSettings(base_dir=tmp_path, data_dir=data_path)

    assert (
        make_url(configured.database_url).database
        == (tmp_path / data_path / "financial-data-agents.sqlite3").as_posix()
    )


def test_relative_database_environment_override_ignores_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application_base = tmp_path / "application"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("base_dir", str(application_base))
    monkeypatch.setenv("database_url", "sqlite+pysqlite:///database files/custom.sqlite3")
    monkeypatch.setenv("database_busy_timeout_ms", "1200")
    monkeypatch.setenv("historical_cache_ttl_seconds", "90.5")
    monkeypatch.setenv("telemetry_sink", "sqlite")

    configured = ProjectSettings()

    url = make_url(configured.database_url)
    assert url.drivername == "sqlite+pysqlite"
    assert url.database == (application_base / "database files/custom.sqlite3").as_posix()
    assert configured.database_busy_timeout_ms == 1_200
    assert configured.historical_cache_ttl_seconds == 90.5
    assert configured.telemetry_sink == "sqlite"


def test_absolute_database_override_is_preserved(tmp_path: Path) -> None:
    database_path = tmp_path / "override.sqlite3"
    configured = ProjectSettings(database_url=f"sqlite:///{database_path.as_posix()}")

    assert make_url(configured.database_url).database == database_path.as_posix()
    assert not database_path.exists()


def test_relative_base_is_anchored_to_application_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    configured = ProjectSettings(base_dir=Path(".tmp/config-base"))

    assert configured.base_dir == Path(__file__).resolve().parents[1] / ".tmp/config-base"


@pytest.mark.parametrize("database_url", ["sqlite://", "sqlite:///:memory:"])
def test_explicit_memory_database_urls_are_preserved(database_url: str) -> None:
    assert ProjectSettings(database_url=database_url).database_url == database_url


@pytest.mark.parametrize(
    "database_url",
    [
        "",
        "not-a-url",
        "postgresql:///data",
        "sqlite+aiosqlite:///data",
        "sqlite://host/data",
        "sqlite:///data?timeout=0",
        "sqlite:///file:data",
    ],
)
def test_invalid_or_unsupported_database_urls_are_rejected(database_url: str) -> None:
    with pytest.raises(ValidationError):
        ProjectSettings(database_url=database_url)


@pytest.mark.parametrize("timeout", ["0", "-1", "1.5", "2147483648", "nan", "inf"])
def test_invalid_busy_timeout_is_rejected(timeout: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("database_busy_timeout_ms", timeout)
    with pytest.raises(ValidationError):
        ProjectSettings()


@pytest.mark.parametrize("ttl", [-1.0, float("nan"), float("inf")])
def test_invalid_historical_ttl_is_rejected(ttl: float) -> None:
    with pytest.raises(ValidationError):
        ProjectSettings(historical_cache_ttl_seconds=ttl)


@pytest.mark.parametrize("ttl", [None, 0.0])
def test_disabled_and_zero_historical_ttl_are_supported(ttl: float | None) -> None:
    assert ProjectSettings(historical_cache_ttl_seconds=ttl).historical_cache_ttl_seconds == ttl


def test_unknown_telemetry_sink_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectSettings.model_validate({"telemetry_sink": "unknown"})


def test_import_does_not_create_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "database/not-created.sqlite3"
    monkeypatch.setenv("database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("data_dir", str(tmp_path / "data"))
    monkeypatch.setenv("log_dir", str(tmp_path / "logs"))
    monkeypatch.setenv("telemetry_log_dir", str(tmp_path / "telemetry"))
    result = subprocess.run(
        [sys.executable, "-c", "import src.config"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not database_path.parent.exists()
