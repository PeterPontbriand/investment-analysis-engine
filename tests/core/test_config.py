import os
from unittest.mock import patch

from src.core.config import Settings


def test_default_settings() -> None:
    """Verify default setting values match expected LAN defaults."""
    settings = Settings()
    assert settings.port == 8000
    assert settings.host == "0.0.0.0"
    assert settings.model_selection == "deepseek-r1:14b"


def test_env_override_settings() -> None:
    """Verify environment variables with FIN_DATA_ prefix override defaults."""
    env_vars = {
        "FIN_DATA_PORT": "9090",
        "FIN_DATA_HOST": "192.168.1.100",
        "FIN_DATA_MODEL_SELECTION": "qwen2.5-coder:14b",
    }
    with patch.dict(os.environ, env_vars):
        settings = Settings()
        assert settings.port == 9090
        assert settings.host == "192.168.1.100"
        assert settings.model_selection == "qwen2.5-coder:14b"
