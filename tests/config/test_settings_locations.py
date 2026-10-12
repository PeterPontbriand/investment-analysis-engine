"""The directories the settings derive from their own file location are the repository's, wherever the file lives."""

from pathlib import Path

import pytest

from src.config import ProjectSettings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolate_location_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "IAN_BASE_DIR",
        "IAN_DATA_DIR",
        "IAN_LOG_DIR",
        "IAN_DATABASE_URL",
        "IAN_TELEMETRY_LOG_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


def test_the_test_anchor_is_the_repository_root() -> None:
    assert (REPOSITORY_ROOT / "pyproject.toml").is_file()
    assert (REPOSITORY_ROOT / "src" / "config" / "__init__.py").is_file()


def test_class_level_defaults_derive_from_the_repository_root() -> None:
    assert ProjectSettings.model_fields["base_dir"].default == REPOSITORY_ROOT
    assert ProjectSettings.model_fields["data_dir"].default == REPOSITORY_ROOT / "data"
    assert ProjectSettings.model_fields["log_dir"].default == REPOSITORY_ROOT / "logs"
    assert ProjectSettings.model_fields["telemetry_log_dir"].default == REPOSITORY_ROOT / "logs"


def test_resolved_default_settings_are_built_from_the_repository_root() -> None:
    configured = ProjectSettings()

    assert configured.base_dir == REPOSITORY_ROOT
    assert configured.data_dir == REPOSITORY_ROOT / "data"
    assert configured.log_dir == REPOSITORY_ROOT / "logs"
    assert configured.telemetry_log_dir == REPOSITORY_ROOT / "logs"
    assert (
        configured.database_url
        == f"sqlite:///{(REPOSITORY_ROOT / 'data' / 'investment-analysis-engine.sqlite3').as_posix()}"
    )


def test_relative_directories_anchor_to_the_repository_root() -> None:
    configured = ProjectSettings(base_dir=Path("."), log_dir=Path("custom-logs"))

    assert configured.base_dir == REPOSITORY_ROOT
    assert configured.log_dir == REPOSITORY_ROOT / "custom-logs"
