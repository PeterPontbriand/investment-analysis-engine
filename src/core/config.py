from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration options for application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FIN_DATA_",
        extra="ignore",
    )

    port: int = Field(default=8000, description="Local network port")
    host: str = Field(default="0.0.0.0", description="Host network binding")
    model_selection: str = Field(default="deepseek-r1:14b", description="Selected model name")


settings = Settings()
