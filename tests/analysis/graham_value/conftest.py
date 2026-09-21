"""Shared Graham-analysis test configuration."""

from __future__ import annotations

import pytest

SEC_TEST_USER_AGENT = "investment-analysis-engine-tests/0.2 tests@example.invalid"


@pytest.fixture(autouse=True)
def _declared_sec_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a declared SEC identity to deterministic Graham provider tests."""
    monkeypatch.setenv("SEC_USER_AGENT", SEC_TEST_USER_AGENT)
