"""The per-user folders, the environment overrides, and the .env file of the settings folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_analysis_engine.config import (
    DATABASE_FILE_NAME,
    ProjectSettings,
    describe_validation_error,
    load_user_dotenv,
)
from investment_analysis_engine.config.user_folders import (
    APPLICATION_FOLDER_NAME,
    resolve_settings_folder,
    user_data_folder,
    user_log_folder,
    user_settings_folder,
)
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.settings_error import SettingsEnvironmentError
from scripts.repository_root import REPOSITORY_ROOT

_OVERRIDES = (
    "IAN_CONFIG_DIR",
    "IAN_DATA_DIR",
    "IAN_LOG_DIR",
    "IAN_DATABASE_URL",
    "IAN_TELEMETRY_LOG_DIR",
)


@pytest.fixture
def no_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every folder override, so the defaults show; the suite's session folders are restored afterwards."""
    for name in _OVERRIDES:
        monkeypatch.delenv(name, raising=False)


def _expected_folders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return the settings, data and log folders the platform's convention gives, for this test's environment."""
    name = APPLICATION_FOLDER_NAME
    if sys.platform == "win32":
        roaming = Path(os.environ["APPDATA"])
        local = Path(os.environ["LOCALAPPDATA"])
        return roaming / name, local / name, local / name / "Logs"
    if sys.platform == "darwin":
        home = Path.home()
        return (
            home / "Library" / "Application Support" / name,
            home / "Library" / "Application Support" / name,
            home / "Library" / "Logs" / name,
        )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "config" / name, tmp_path / "data" / name, tmp_path / "state" / name / "log"


def _same(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def test_the_test_anchors_are_the_repository_and_package_roots() -> None:
    assert (REPOSITORY_ROOT / "pyproject.toml").is_file()
    assert (PACKAGE_ROOT / "config" / "__init__.py").is_file()


def test_the_user_folders_are_the_platforms_conventional_ones(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del no_overrides
    settings_folder, data_folder, log_folder = _expected_folders(monkeypatch, tmp_path)
    before = [path.exists() for path in (settings_folder, data_folder, log_folder)]

    assert _same(user_settings_folder(), settings_folder)
    assert _same(user_data_folder(), data_folder)
    assert _same(user_log_folder(), log_folder)
    assert [path.exists() for path in (settings_folder, data_folder, log_folder)] == before


def test_default_settings_use_the_user_folders_and_create_nothing(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del no_overrides
    _expected_folders(monkeypatch, tmp_path)
    folders = (user_settings_folder(), user_data_folder(), user_log_folder())
    before = [path.exists() for path in folders]

    configured = ProjectSettings()

    assert _same(configured.config_dir, user_settings_folder())
    assert _same(configured.data_dir, user_data_folder())
    assert _same(configured.log_dir, user_log_folder())
    assert configured.telemetry_log_dir == configured.log_dir
    assert configured.database_url == f"sqlite:///{(configured.data_dir / DATABASE_FILE_NAME).as_posix()}"
    assert [path.exists() for path in folders] == before


def test_each_folder_variable_overrides_its_default(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del no_overrides
    for name, folder in (("IAN_CONFIG_DIR", "c"), ("IAN_DATA_DIR", "d"), ("IAN_LOG_DIR", "l")):
        monkeypatch.setenv(name, str(tmp_path / folder))

    configured = ProjectSettings()

    assert configured.config_dir == (tmp_path / "c").resolve()
    assert configured.data_dir == (tmp_path / "d").resolve()
    assert configured.log_dir == (tmp_path / "l").resolve()
    assert configured.telemetry_log_dir == configured.log_dir
    assert configured.database_url == f"sqlite:///{((tmp_path / 'd').resolve() / DATABASE_FILE_NAME).as_posix()}"
    assert not (tmp_path / "d").exists()


def test_the_telemetry_folder_follows_the_log_folder_unless_it_is_set(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del no_overrides
    monkeypatch.setenv("IAN_LOG_DIR", str(tmp_path / "logs"))
    assert ProjectSettings().telemetry_log_dir == (tmp_path / "logs").resolve()

    monkeypatch.setenv("IAN_TELEMETRY_LOG_DIR", str(tmp_path / "telemetry"))
    assert ProjectSettings().telemetry_log_dir == (tmp_path / "telemetry").resolve()


def test_the_database_url_overrides_the_default_database(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del no_overrides
    monkeypatch.setenv("IAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("IAN_DATABASE_URL", f"sqlite:///{(tmp_path / 'elsewhere.sqlite3').as_posix()}")

    assert ProjectSettings().database_url == f"sqlite:///{(tmp_path / 'elsewhere.sqlite3').resolve().as_posix()}"


@pytest.mark.parametrize("name", ["IAN_DATA_DIR", "IAN_LOG_DIR", "IAN_TELEMETRY_LOG_DIR", "IAN_CONFIG_DIR"])
def test_a_relative_folder_variable_is_rejected_and_named(
    name: str, no_overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del no_overrides
    monkeypatch.setenv(name, "relative/folder")

    with pytest.raises(ValidationError) as error:
        ProjectSettings()

    message = describe_validation_error(error.value, os.environ)
    assert message == f"The engine settings are invalid: {name} path 'relative/folder' must be an absolute path."


def test_a_relative_database_file_path_is_rejected_and_names_the_variable(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del no_overrides
    monkeypatch.setenv("IAN_DATABASE_URL", "sqlite:///data/x.sqlite3")

    with pytest.raises(ValidationError) as error:
        ProjectSettings()

    assert describe_validation_error(error.value, os.environ) == (
        "The engine settings are invalid: IAN_DATABASE_URL path 'data/x.sqlite3' must be an absolute path."
    )


def test_the_memory_database_stays_accepted(no_overrides: None, monkeypatch: pytest.MonkeyPatch) -> None:
    del no_overrides
    monkeypatch.setenv("IAN_DATABASE_URL", "sqlite:///:memory:")

    assert ProjectSettings().database_url == "sqlite:///:memory:"


def test_the_removed_base_directory_setting_is_not_accepted(
    no_overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del no_overrides
    monkeypatch.setenv("IAN_BASE_DIR", "/x")

    with pytest.raises(SettingsEnvironmentError, match="IAN_BASE_DIR matches no engine setting"):
        ProjectSettings()
    assert "base_dir" not in ProjectSettings.model_fields


def test_the_settings_folder_comes_from_the_process_environment_then_the_user_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert resolve_settings_folder({"IAN_CONFIG_DIR": str(tmp_path)}) == tmp_path.resolve()
    assert resolve_settings_folder({"ian_config_dir": str(tmp_path)}) == tmp_path.resolve()
    assert resolve_settings_folder({"IAN_CONFIG_DIR": ""}) == user_settings_folder()
    assert resolve_settings_folder({}) == user_settings_folder()
    with pytest.raises(SettingsEnvironmentError, match="IAN_CONFIG_DIR path 'rel' must be an absolute path"):
        resolve_settings_folder({"IAN_CONFIG_DIR": "rel"})
    del monkeypatch


def _probe_variable(monkeypatch: pytest.MonkeyPatch) -> str:
    """Return a setting name whose process-environment state is restored when the test ends."""
    name = "IAN_LOG_LEVEL"
    monkeypatch.setenv(name, "placeholder")
    monkeypatch.delenv(name)
    return name


def test_the_env_file_of_the_settings_folder_is_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    name = _probe_variable(monkeypatch)
    (tmp_path / ".env").write_text(f"{name}=DEBUG\n", encoding="utf-8")

    folder = load_user_dotenv({"IAN_CONFIG_DIR": str(tmp_path)})

    assert folder == tmp_path.resolve()
    assert os.environ[name] == "DEBUG"


def test_a_process_variable_beats_the_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    name = _probe_variable(monkeypatch)
    monkeypatch.setenv(name, "WARNING")
    (tmp_path / ".env").write_text(f"{name}=DEBUG\n", encoding="utf-8")

    load_user_dotenv({"IAN_CONFIG_DIR": str(tmp_path)})

    assert os.environ[name] == "WARNING"


def test_a_missing_env_file_is_normal(tmp_path: Path) -> None:
    assert load_user_dotenv({"IAN_CONFIG_DIR": str(tmp_path / "absent")}) == (tmp_path / "absent").resolve()
    assert not (tmp_path / "absent").exists()


def test_the_env_file_cannot_set_the_variable_that_locates_it(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"IAN_CONFIG_DIR={tmp_path}\n", encoding="utf-8")

    with pytest.raises(SettingsEnvironmentError) as error:
        load_user_dotenv({"IAN_CONFIG_DIR": str(tmp_path)})

    assert str(error.value) == (
        f"IAN_CONFIG_DIR is set in {tmp_path.resolve() / '.env'}, but it names the folder that holds this file, "
        "so it cannot be set there; set it in the process environment or remove it from the file."
    )


def test_an_env_file_in_the_current_folder_or_above_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = _probe_variable(monkeypatch)
    work = tmp_path / "work" / "deeper"
    work.mkdir(parents=True)
    (tmp_path / "work" / ".env").write_text(f"{name}=DEBUG\n", encoding="utf-8")
    (work / ".env").write_text(f"{name}=DEBUG\n", encoding="utf-8")
    monkeypatch.chdir(work)

    load_user_dotenv({"IAN_CONFIG_DIR": str(tmp_path / "settings")})

    assert name not in os.environ
