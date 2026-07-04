"""Application configurations managed via Pydantic-settings and external TOML profiles."""

import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    """
    Application configurations loaded from environment variables and config tables.

    Inherits from pydantic_settings.BaseSettings.
    """

    # ProjectSettings
    project_name: str = "financial-data-agents"
    version: str = "0.1.0"

    # AI/Agent Settings
    ollama_base_url: str = "http://192.168.1.19:11434"
    model_name: str = "deepseek-r1:14b"

    # Logging Configuration
    log_level: str = "INFO"
    log_file_name: str = "app.log"
    log_file_mode: str = "a"
    log_max_bytes: int = 1 * 1024 * 1024  # 1MB per file
    log_backup_count: int = 5
    log_encoding: str = "utf-8"
    log_when: str = "D"  # Rotate daily
    log_interval: int = 1

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
        return load_config_file(str(self.base_dir / analysis_config_path))

    def get_momentum_analysis(self) -> dict[str, Any]:
        """Retrieve core fast/slow moving average parameters settings."""
        momentum_config_path = self.base_dir / "config" / "momentum_config" / "momentum_analysis_settings.toml"
        return load_config_file(str(self.base_dir / momentum_config_path))


# Instantiate singleton settings proxy
settings = ProjectSettings()

# Ensure directories exist
if not settings.data_dir.exists():
    settings.data_dir.mkdir(parents=True, exist_ok=True)

if not settings.log_dir.exists():
    settings.log_dir.mkdir(parents=True, exist_ok=True)

# AI/Agent Settings (Local via Ollama) - accessed through settings.ollama_base_url and settings.model_name
# Example usage would be:
# ollama_url = settings.ollama_base_url
