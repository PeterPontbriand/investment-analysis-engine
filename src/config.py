# src/config.py
"""Application configurations managed via Pydantic-settings and external TOML profiles."""

import tomllib
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.schema.config import SchemaConfig  # Step 2.2 import

# Ensure core environment variables are populated
load_dotenv()


def load_config_file(file_path: str) -> dict[str, Any]:
    """Load configuration values from a specified TOML file profile."""
    try:
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at path: {file_path}") from None
    except tomllib.TOMLDecodeError:
        raise ValueError(f"Failed to decode configuration file at path: {file_path}") from None


class ProjectSettings(BaseSettings):
    """Application configuration loaded from environment variables and config tables."""

    # ProjectSettings
    project_name: str = "financial-data-agents"
    version: str = "0.1.0"

    # AI/Agent Settings
    ollama_base_url: str = "http://192.168.1.19:11434"
    model_selection: str = "deepseek-r1:14b"

    # Native Schema Enforcement Settings (Step 2.2)
    schema_config: SchemaConfig = Field(default_factory=SchemaConfig.from_env)

    # External data-provider settings
    sec_user_agent: str | None = Field(default=None, validation_alias="SEC_USER_AGENT")

    # Human-readable operational logging
    log_level: str = "INFO"
    log_file_name: str = "app.log"
    log_file_mode: str = "a"
    log_max_bytes: int = 1 * 1024 * 1024  # 1MB per file
    log_backup_count: int = 5
    log_encoding: str = "utf-8"
    log_when: str = "D"  # Rotate daily
    log_interval: int = 1

    # Structured trajectory telemetry (Step 2.1)
    telemetry_sink: Literal["jsonl"] = "jsonl"
    telemetry_log_dir: Path = Path(__file__).resolve().parent.parent / "logs"
    telemetry_level: Literal["INFO", "DEBUG", "OFF"] = "INFO"
    telemetry_max_log_files: int = 100
    telemetry_max_total_size: int = 100 * 1024 * 1024

    # Database Configuration
    database_url: str = "sqlite:///./test.db"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Environment Variables
    environment: str = "development"

    # Encoding for all text files
    encoding: str = "utf-8"

    # Project Root Directory
    base_dir: Path = Path(__file__).resolve().parent.parent

    # Core Paths
    data_dir: Path = base_dir / "data"
    log_dir: Path = base_dir / "logs"

    model_config = SettingsConfigDict(
        extra="ignore",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        case_sensitive=True,
    )

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


# Instantiate singleton settings proxy
settings = ProjectSettings()

# Ensure directories exist
if not settings.data_dir.exists():
    settings.data_dir.mkdir(parents=True, exist_ok=True)

if not settings.log_dir.exists():
    settings.log_dir.mkdir(parents=True, exist_ok=True)

if not settings.telemetry_log_dir.exists():
    settings.telemetry_log_dir.mkdir(parents=True, exist_ok=True)
