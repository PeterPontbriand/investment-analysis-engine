# investment_analysis_engine/config/__init__.py
"""Application configurations managed via Pydantic-settings and external TOML profiles."""

import dataclasses
import os
import re
import tomllib
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, Literal, Self

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

import investment_analysis_engine.config.paths as anchored_paths  # noqa: PLR0402 - the initializer cannot name its own package in a from-import
from investment_analysis_engine.config.reliability_limits import ReliabilityLimits
from investment_analysis_engine.config.schema_config import SchemaConfig
from investment_analysis_engine.config.user_folders import (
    CONFIG_DIR_VARIABLE,
    resolve_settings_folder,
    user_data_folder,
    user_log_folder,
    user_settings_folder,
)
from investment_analysis_engine.core.settings_error import SettingsEnvironmentError

ENV_PREFIX = "IAN_"
NESTED_DELIMITER = "__"
DATABASE_FILE_NAME = "investment-analysis-engine.sqlite3"
DOTENV_FILE_NAME = ".env"


def load_user_dotenv(environ: Mapping[str, str]) -> Path:
    """Load the ``.env`` file of the settings folder into the process environment and return the folder.

    The file is looked up only in the settings folder, with an explicit path and no search upward. A variable that is
    already in the process environment keeps its value, so the order is the process environment, then the file.
    ``IAN_CONFIG_DIR`` locates the file and so cannot be set in it.

    Args:
        environ: The process environment, from which ``IAN_CONFIG_DIR`` is read.

    Returns:
        The settings folder, whether or not it exists.

    Raises:
        SettingsEnvironmentError: If ``IAN_CONFIG_DIR`` is not absolute, or the file sets it.
    """
    folder = resolve_settings_folder(environ)
    path = folder / DOTENV_FILE_NAME
    if path.is_file():
        if any(key.upper() == CONFIG_DIR_VARIABLE for key in dotenv_values(path)):
            raise SettingsEnvironmentError(
                f"{CONFIG_DIR_VARIABLE} is set in {path}, but it names the folder that holds this file, so it cannot "
                "be set there; set it in the process environment or remove it from the file."
            )
        load_dotenv(path, override=False)
    return folder


# Populate the process environment from the user's .env file before any setting is read.
load_user_dotenv(os.environ)


def load_config_file(file_path: str) -> dict[str, Any]:
    """Load configuration values from a specified TOML file profile."""
    try:
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at path: {file_path}") from None
    except tomllib.TOMLDecodeError:
        raise ValueError(f"Failed to decode configuration file at path: {file_path}") from None


def _nested_field_names(annotation: object) -> frozenset[str] | None:
    """Return the field names of a nested settings model, or None when the field is a plain value."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return frozenset(annotation.model_fields)
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return frozenset(item.name for item in dataclasses.fields(annotation))
    return None


def _environment_name(name: str, field: FieldInfo) -> str:
    """Return the upper-case environment variable that sets a field (its alias, or the prefixed field name)."""
    if isinstance(field.validation_alias, str):
        return field.validation_alias.upper()
    return f"{ENV_PREFIX}{name}".upper()


def declared_environment_names(settings_cls: type[BaseSettings]) -> frozenset[str]:
    """Return every environment variable name the settings class accepts, lower-cased.

    Plain fields are read as ``IAN_<FIELD>``; a field with a string validation alias keeps that alias (the
    provider credentials). Nested model fields additionally accept ``IAN_<FIELD>__<SUBFIELD>`` and the
    whole-object ``IAN_<FIELD>`` form.
    """
    names: set[str] = set()
    for name, field in settings_cls.model_fields.items():
        base = _environment_name(name, field)
        names.add(base.lower())
        nested = _nested_field_names(field.annotation)
        if nested is not None:
            names.update(f"{base}{NESTED_DELIMITER}{sub}".lower() for sub in nested)
    return frozenset(names)


def check_environment(environ: Mapping[str, str], declared: frozenset[str]) -> None:
    """Fail closed when the environment does not map onto the declared settings unambiguously.

    Args:
        environ: The process environment (or any mapping of variable names to values).
        declared: Lower-cased names from :func:`declared_environment_names`.

    Raises:
        SettingsEnvironmentError: An ``IAN_`` variable names no setting, or two variables that differ only
            by case are both set for the same setting. The message names the offending variables.
    """
    spellings: dict[str, list[str]] = defaultdict(list)
    for key in environ:
        lowered = key.lower()
        if lowered in declared or lowered.startswith(ENV_PREFIX.lower()):
            spellings[lowered].append(key)
    for lowered, keys in sorted(spellings.items()):
        if lowered not in declared:
            raise SettingsEnvironmentError(
                f"Environment variable {keys[0]} matches no engine setting (engine settings are read as "
                f"{ENV_PREFIX}<NAME>, for example {ENV_PREFIX}DATA_DIR); correct the name or remove the variable."
            )
        if len(keys) > 1:
            listed = " and ".join(sorted(keys))
            raise SettingsEnvironmentError(
                f"Environment variables {listed} differ only by letter case and both set the same engine setting; "
                "set exactly one."
            )


class _EngineEnvSource(EnvSettingsSource):
    """Environment source that validates the whole environment before any value is read."""

    def _load_env_vars(self) -> Mapping[str, str | None]:
        """Validate the process environment, then load it as the base source does."""
        check_environment(os.environ, declared_environment_names(self.settings_cls))
        return super()._load_env_vars()


class ProjectSettings(BaseSettings):
    """Application configuration loaded from environment variables and config tables.

    Every setting is read from ``IAN_<NAME>`` in any letter case (for example ``IAN_DATA_DIR``); unprefixed names
    are not read. The provider credential ``SEC_USER_AGENT`` keeps its own name, also
    in any case. An ``IAN_`` variable that names no setting, or two variables differing only by case for one
    setting, raise :class:`SettingsEnvironmentError`.
    """

    # Fixed application identity; deliberately not environment-overridable.
    version: ClassVar[str] = "0.1.0"
    environment: ClassVar[str] = "development"
    encoding: ClassVar[str] = "utf-8"

    # AI/Agent Settings
    ollama_base_url: str = "http://localhost:11434"
    model_selection: str = "deepseek-r1:14b"

    # Native Schema Enforcement Settings
    schema_config: SchemaConfig = Field(default_factory=SchemaConfig)

    # Orchestration reliability limits
    reliability_limits: ReliabilityLimits = Field(default_factory=ReliabilityLimits)

    # External data-provider settings
    sec_user_agent: str | None = Field(default=None, validation_alias="SEC_USER_AGENT")

    # Automatic provider check: after a provider failure, one bounded test request to the implicated provider
    provider_check: bool = Field(
        default=True,
        description=(
            "After a provider failure, send one bounded test request to the implicated provider and print what it "
            "found; false turns the check off. Read as IAN_PROVIDER_CHECK."
        ),
    )
    provider_check_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
        allow_inf_nan=False,
        description=(
            "Time limit in seconds for the whole test request of the automatic provider check; ten seconds by "
            "default. Read as IAN_PROVIDER_CHECK_TIMEOUT_SECONDS."
        ),
    )

    # Human-readable operational logging
    log_level: str = "INFO"
    log_file_name: str = "app.log"
    log_max_bytes: int = 1 * 1024 * 1024  # 1MB per file
    log_backup_count: int = 5
    log_encoding: str = "utf-8"
    log_when: str = "D"  # Rotate daily
    log_interval: int = 1

    # Structured trajectory telemetry
    telemetry_sink: Literal["jsonl", "sqlite"] = "jsonl"
    telemetry_log_dir: Path = Field(
        default_factory=user_log_folder,
        description="Folder holding the trajectory telemetry; the log folder in use unless this is set.",
    )
    telemetry_level: Literal["INFO", "DEBUG", "OFF"] = "INFO"
    telemetry_max_log_files: int = 100
    telemetry_max_total_size: int = 100 * 1024 * 1024

    # Database Configuration
    database_url: str = Field(
        default="",
        description="SQLite URL; an empty value means the database file in the data folder.",
    )
    database_busy_timeout_ms: int = Field(
        default=5_000,
        gt=0,
        le=2_147_483_647,
        description="Bounded SQLite lock wait in milliseconds; five seconds permits short concurrent writes.",
    )
    historical_cache_ttl_seconds: float | None = Field(
        default=3_600,
        ge=0,
        allow_inf_nan=False,
        description="Historical cache reuse age: one hour by default; None disables TTL, zero allows no positive age.",
    )
    financial_cache_ttl_seconds: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        description="Financial cache residence age; None preserves unlimited reuse subject to temporal quality checks.",
    )
    quote_cache_ttl_seconds: float = Field(
        default=300,
        ge=0,
        allow_inf_nan=False,
        description="Maximum quote-response reuse age; zero disables quote cache reuse.",
    )
    instrument_profile_ttl_seconds: float | None = Field(
        default=2_592_000,
        ge=0,
        allow_inf_nan=False,
        description=(
            "Durable instrument-profile reuse age: thirty days by default; None disables TTL "
            "(always reuse the durable profile until an explicit refresh is requested)."
        ),
    )

    # Per-user folders; each default is the platform's conventional folder and an environment variable overrides it.
    config_dir: Path = Field(
        default_factory=user_settings_folder,
        description="Settings folder, holding the .env file and the strategy settings; read as IAN_CONFIG_DIR.",
    )
    data_dir: Path = Field(default_factory=user_data_folder, description="Folder holding the database.")
    log_dir: Path = Field(default_factory=user_log_folder, description="Folder holding the application log.")

    model_config = SettingsConfigDict(
        extra="ignore",
        env_ignore_empty=True,
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=NESTED_DELIMITER,
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003 - fixed override signature
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003 - fixed override signature
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003 - fixed override signature
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Read explicit arguments first, then the validated process environment."""
        return (init_settings, _EngineEnvSource(settings_cls))

    @model_validator(mode="before")
    @classmethod
    def require_absolute_user_paths(cls, data: Any) -> Any:
        """Reject a folder or a database file path the user set that is not absolute.

        A relative path would depend on where the command happens to run. On Windows a path that is only partly
        anchored (a root without a drive, or a drive without a root) is rejected with advice on writing a full path;
        see :func:`investment_analysis_engine.config.paths.require_absolute_path`. This sees only the values the user
        gave, from arguments or the environment, never the defaults.
        """
        if not isinstance(data, dict):
            return data
        windows = anchored_paths.is_windows()
        for name in ("config_dir", "data_dir", "log_dir", "telemetry_log_dir"):
            if data.get(name) is not None:
                anchored_paths.require_absolute_path(Path(data[name]).as_posix(), name=name, windows=windows)
        database_url = data.get("database_url")
        if isinstance(database_url, str):
            try:
                database = make_url(database_url).database
            except ArgumentError:
                return data
            if database not in (None, "", ":memory:") and not database.startswith("file:"):
                anchored_paths.require_absolute_path(database, name="database_url", windows=windows)
        return data

    @model_validator(mode="after")
    def resolve_database_configuration(self) -> Self:
        """Resolve the folders and the SQLite target without opening a connection or creating anything.

        The telemetry folder is the log folder unless set. The database is the file in the data folder unless a URL
        is set. Explicit SQLite memory URLs remain available for injected tests.
        """
        # Assignments below add fields to model_fields_set, so the user's choices are captured first.
        user_set = frozenset(self.model_fields_set)
        self.config_dir = self.config_dir.resolve()
        self.data_dir = self.data_dir.resolve()
        self.log_dir = self.log_dir.resolve()
        self.telemetry_log_dir = self.telemetry_log_dir.resolve() if "telemetry_log_dir" in user_set else self.log_dir
        if "database_url" not in user_set:
            self.database_url = URL.create(
                "sqlite", database=(self.data_dir / DATABASE_FILE_NAME).as_posix()
            ).render_as_string()
        try:
            url = make_url(self.database_url)
        except ArgumentError as error:
            raise ValueError("database_url must be a valid SQLite URL.") from error
        if url.drivername not in ("sqlite", "sqlite+pysqlite"):
            raise ValueError("database_url must use synchronous SQLite (sqlite or sqlite+pysqlite).")
        if any(value is not None for value in (url.username, url.password, url.host, url.port)) or url.query:
            raise ValueError("database_url must not contain credentials, host, port, or query parameters.")
        if url.database not in (None, "", ":memory:"):
            if url.database.startswith("file:"):
                raise ValueError("SQLite file URI databases are not supported; use a filesystem path.")
            url = url.set(database=Path(url.database).resolve().as_posix())
        self.database_url = url.render_as_string()
        return self


def describe_validation_error(error: ValidationError, environ: Mapping[str, str]) -> str:
    """Describe the first invalid setting as one sentence that names the environment variable.

    The offending value is never included: pydantic's message text describes the rule.

    Args:
        error: The validation error raised while building :class:`ProjectSettings` from the environment.
        environ: The process environment, used to quote the variable in the spelling the user set.

    Returns:
        A single sentence naming the variable and what was wrong with its value.
    """
    first = error.errors(include_input=False, include_url=False, include_context=False)[0]
    location = tuple(str(part) for part in first["loc"])
    message = first["msg"].removeprefix("Value error, ").rstrip(".")
    fields = ProjectSettings.model_fields
    if not location:
        # A whole-model rule (such as path anchoring) names the setting by field name; quote the variable instead.
        for name, field in fields.items():
            message = re.sub(rf"\b{re.escape(name)}\b", _environment_name(name, field), message)
        return f"The engine settings are invalid: {message}."
    owner = next(
        (
            (name, field)
            for name, field in fields.items()
            if location[0] == name or location[0] == field.validation_alias
        ),
        None,
    )
    if owner is None:
        return f"The engine settings are invalid: {message}."
    name, field = owner
    expected = _environment_name(name, field) + "".join(f"{NESTED_DELIMITER}{part.upper()}" for part in location[1:])
    actual = next((key for key in environ if key.lower() == expected.lower()), expected)
    return f"Environment variable {actual} is invalid: {message}."


def _build_settings() -> ProjectSettings:
    """Build the settings from the environment, reporting an invalid value as :class:`SettingsEnvironmentError`."""
    try:
        return ProjectSettings()
    except ValidationError as error:
        raise SettingsEnvironmentError(describe_validation_error(error, os.environ)) from None


# Instantiate singleton settings proxy
settings = _build_settings()
