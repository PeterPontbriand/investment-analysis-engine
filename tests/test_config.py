"""Focused tests for application settings used by user-facing runtime setup."""

import pytest

from src.config import ProjectSettings


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
