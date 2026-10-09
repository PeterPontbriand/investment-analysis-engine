# src/config.py
"""Application configurations managed via Pydantic-settings and external TOML profiles."""

import dataclasses
import os
import tomllib
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, Literal, Self

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from src.orchestrator.reliability import ReliabilityLimits
from src.schema.config import SchemaConfig
from src.utils import paths

# Ensure core environment variables are populated
load_dotenv()

ENV_PREFIX = "IAN_"
NESTED_DELIMITER = "__"


class SettingsEnvironmentError(ValueError):
    """Raised when the process environment cannot be mapped onto the engine settings unambiguously."""


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
                f"Environment variable {keys[0]} does not match any engine setting. Engine settings are read as "
                f"{ENV_PREFIX}<NAME> (for example {ENV_PREFIX}DATA_DIR); correct the name or remove the variable."
            )
        if len(keys) > 1:
            listed = " and ".join(sorted(keys))
            raise SettingsEnvironmentError(
                f"Environment variables {listed} differ only by case and both set the same engine setting; "
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
    are not read. The provider credentials ``SEC_USER_AGENT`` and ``MASSIVE_API_KEY`` keep their own names, also
    in any case. An ``IAN_`` variable that names no setting, or two variables differing only by case for one
    setting, raise :class:`SettingsEnvironmentError`.
    """

    # Fixed application identity; deliberately not environment-overridable.
    version: ClassVar[str] = "0.1.0"
    environment: ClassVar[str] = "development"
    encoding: ClassVar[str] = "utf-8"

    # AI/Agent Settings
    ollama_base_url: str = "http://192.168.1.19:11434"
    model_selection: str = "deepseek-r1:14b"

    # Native Schema Enforcement Settings
    schema_config: SchemaConfig = Field(default_factory=SchemaConfig)

    # Orchestration reliability limits
    reliability_limits: ReliabilityLimits = Field(default_factory=ReliabilityLimits)

    # External data-provider settings
    sec_user_agent: str | None = Field(default=None, validation_alias="SEC_USER_AGENT")
    massive_api_key: SecretStr | None = Field(default=None, validation_alias="MASSIVE_API_KEY")

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
    telemetry_log_dir: Path = Path(__file__).resolve().parent.parent / "logs"
    telemetry_level: Literal["INFO", "DEBUG", "OFF"] = "INFO"
    telemetry_max_log_files: int = 100
    telemetry_max_total_size: int = 100 * 1024 * 1024

    # Database Configuration
    database_url: str = "sqlite:///data/investment-analysis-engine.sqlite3"
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

    # Project Root Directory
    base_dir: Path = Path(__file__).resolve().parent.parent

    # Core Paths
    data_dir: Path = base_dir / "data"
    log_dir: Path = base_dir / "logs"

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

    @model_validator(mode="after")
    def resolve_database_configuration(self) -> Self:
        """Resolve SQLite paths without opening a connection or creating a database.

        Relative base paths anchor to the application root; relative data and
        database paths anchor to base_dir, independent of the caller's cwd.
        Explicit SQLite memory URLs remain available for injected tests. On Windows, a configured path
        that is only partly anchored (a root without a drive, or a drive without a root) is rejected
        before any resolution; see :func:`src.utils.paths.require_anchored_path`.
        """
        # Assignments below add fields to model_fields_set, so the user's choices are captured first:
        # only values the user set are checked, never the paths this validator derives.
        user_set = frozenset(self.model_fields_set)
        for name in ("base_dir", "data_dir", "log_dir", "telemetry_log_dir"):
            if name in user_set:
                paths.require_anchored_path(getattr(self, name).as_posix(), name=name, windows=paths.is_windows())
        application_root = Path(__file__).resolve().parent.parent
        self.base_dir = (application_root / self.base_dir).resolve()
        data_path = self.data_dir if "data_dir" in user_set else Path("data")
        self.data_dir = (self.base_dir / data_path).resolve()
        for name in ("log_dir", "telemetry_log_dir"):
            if name in user_set:
                setattr(self, name, (self.base_dir / getattr(self, name)).resolve())
        if "database_url" not in user_set:
            self.database_url = URL.create(
                "sqlite", database=(self.data_dir / "investment-analysis-engine.sqlite3").as_posix()
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
            database_path = Path(url.database)
            if url.database.startswith("file:"):
                raise ValueError("SQLite file URI databases are not supported; use a filesystem path.")
            if "database_url" in user_set:
                paths.require_anchored_path(url.database, name="database_url", windows=paths.is_windows())
            url = url.set(database=(self.base_dir / database_path).resolve().as_posix())
        self.database_url = url.render_as_string()
        return self

    def get_analysis_settings(self) -> dict[str, Any]:
        """Retrieve historical and ingestion settings."""
        analysis_config_path = self.base_dir / "config" / "general_analysis_settings.toml"
        return load_config_file(str(analysis_config_path))

    def get_graham_value_analysis(self) -> dict[str, Any]:
        """Benjamin Graham formula settings (base P/E, growth multiplier, baseline AAA yield)."""
        toml_path = self.base_dir / "config" / "graham_value_config" / "graham_value_analysis_settings.toml"
        return load_config_file(str(toml_path))

    def get_momentum_analysis(self) -> dict[str, Any]:
        """Retrieve core fast/slow moving average parameters settings."""
        momentum_config_path = self.base_dir / "config" / "momentum_config" / "momentum_analysis_settings.toml"
        return load_config_file(str(momentum_config_path))


def configured_massive_api_key() -> str | None:
    """Return the Massive API key from a fresh read of the environment, or None when it is not set."""
    secret = ProjectSettings().massive_api_key
    return None if secret is None else secret.get_secret_value()


# Instantiate singleton settings proxy
settings = ProjectSettings()

# Ensure directories exist
if not settings.data_dir.exists():
    settings.data_dir.mkdir(parents=True, exist_ok=True)

if not settings.log_dir.exists():
    settings.log_dir.mkdir(parents=True, exist_ok=True)

if not settings.telemetry_log_dir.exists():
    settings.telemetry_log_dir.mkdir(parents=True, exist_ok=True)
