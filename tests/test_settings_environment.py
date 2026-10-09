"""Environment mapping of the engine settings: prefix, letter case, and fail-closed validation."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import ProjectSettings, describe_validation_error
from src.core.settings_error import SettingsEnvironmentError

_CASE_VARIANTS = ["IAN_DATA_DIR", "ian_data_dir", "Ian_Data_Dir"]


@pytest.fixture(autouse=True)
def clean_engine_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every engine and provider variable so each test sets exactly the names it exercises."""
    for name in list(os.environ):
        if name.lower().startswith("ian_") or name.lower() in {"data_dir", "sec_user_agent", "massive_api_key"}:
            monkeypatch.delenv(name)


def _replace_environment(monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]) -> None:
    """Install a plain mapping as the environment, which can hold names differing only by case on any OS."""
    monkeypatch.setattr(os, "environ", variables)


def test_documented_spelling_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IAN_DATA_DIR", str(tmp_path / "documented"))

    assert ProjectSettings().data_dir == (tmp_path / "documented").resolve()


@pytest.mark.parametrize("spelling", _CASE_VARIANTS)
def test_any_letter_case_of_the_documented_name_is_honoured(
    spelling: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _replace_environment(monkeypatch, {spelling: str(tmp_path / "cased")})

    assert ProjectSettings().data_dir == (tmp_path / "cased").resolve()


def test_nested_settings_are_prefixed_and_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IAN_RELIABILITY_LIMITS__MAX_STEPS", "7")
    monkeypatch.setenv("Ian_Schema_Config__Max_Validation_Retries", "9")
    monkeypatch.setenv("IAN_SCHEMA_CONFIG__OLLAMA_VERSION", "0.9.0")

    configured = ProjectSettings()

    assert configured.reliability_limits.max_steps == 7
    assert configured.schema_config.max_validation_retries == 9
    assert configured.schema_config.ollama_version == "0.9.0"


@pytest.mark.parametrize("unprefixed", ["DATA_DIR", "data_dir", "SCHEMA_MAX_RETRIES", "OLLAMA_VERSION", "VERSION"])
def test_unprefixed_names_are_not_read(unprefixed: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(unprefixed, str(tmp_path / "ignored"))
    defaults = ProjectSettings(base_dir=tmp_path)

    configured = ProjectSettings(base_dir=tmp_path)

    assert configured.data_dir == defaults.data_dir == (tmp_path / "data").resolve()
    assert configured.schema_config.max_validation_retries == 3
    assert configured.schema_config.ollama_version is None
    assert configured.version == "0.1.0"


@pytest.mark.parametrize(
    "unknown",
    [
        "IAN_NO_SUCH_SETTING",
        "ian_datadir",
        "IAN_RELIABILITY_LIMITS__NO_SUCH_FIELD",
        "IAN_VERSION",
        "IAN_SEC_USER_AGENT",
    ],
)
def test_unknown_engine_variable_fails_closed_naming_it(unknown: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(unknown, "value")

    with pytest.raises(SettingsEnvironmentError, match=f"(?i){re.escape(unknown)}"):
        ProjectSettings()


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("IAN_DATA_DIR", "ian_data_dir"),
        ("IAN_RELIABILITY_LIMITS__MAX_STEPS", "ian_reliability_limits__max_steps"),
        ("SEC_USER_AGENT", "sec_user_agent"),
        ("MASSIVE_API_KEY", "Massive_Api_Key"),
    ],
)
def test_variables_differing_only_by_case_fail_closed_naming_both(
    first: str, second: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _replace_environment(monkeypatch, {first: "1", second: "2"})

    with pytest.raises(SettingsEnvironmentError) as raised:
        ProjectSettings()

    assert first in str(raised.value)
    assert second in str(raised.value)


@pytest.mark.parametrize("spelling", ["SEC_USER_AGENT", "sec_user_agent", "Sec_User_Agent"])
def test_sec_user_agent_keeps_its_name_in_any_case(spelling: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _replace_environment(monkeypatch, {spelling: "Test Identity test@example.invalid"})

    assert ProjectSettings().sec_user_agent == "Test Identity test@example.invalid"


@pytest.mark.parametrize("spelling", ["MASSIVE_API_KEY", "massive_api_key", "Massive_Api_Key"])
def test_massive_api_key_keeps_its_name_in_any_case(spelling: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _replace_environment(monkeypatch, {spelling: "test-key"})

    configured = ProjectSettings().massive_api_key
    assert configured is not None
    assert configured.get_secret_value() == "test-key"
    assert "test-key" not in repr(ProjectSettings())


def test_massive_api_key_is_none_when_unset() -> None:
    assert ProjectSettings().massive_api_key is None


def test_application_identity_is_constant() -> None:
    assert (ProjectSettings.version, ProjectSettings.environment, ProjectSettings.encoding) == (
        "0.1.0",
        "development",
        "utf-8",
    )
    assert not {"version", "environment", "encoding"} & set(ProjectSettings.model_fields)


def test_invalid_value_is_described_by_variable_without_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ian_database_busy_timeout_ms", "not-a-number")
    with pytest.raises(ValidationError) as raised:
        ProjectSettings()

    sentence = describe_validation_error(raised.value, os.environ)

    assert sentence.startswith("Environment variable ")
    assert "DATABASE_BUSY_TIMEOUT_MS" in sentence.upper()
    assert "not-a-number" not in sentence


def test_invalid_secret_value_is_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MASSIVE_API_KEY", "leaky secret")
    with pytest.raises(ValidationError) as raised:
        ProjectSettings()

    sentence = describe_validation_error(raised.value, os.environ)

    assert "MASSIVE_API_KEY" in sentence
    assert "not shown" in sentence
    assert "leaky" not in sentence
