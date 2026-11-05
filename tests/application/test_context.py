"""The application context carries the caller's settings and nothing else."""

import dataclasses

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings


def test_the_context_holds_the_settings_it_was_built_with() -> None:
    settings = ProjectSettings(database_url="sqlite:///:memory:")
    assert ApplicationContext(settings=settings).settings is settings


def test_the_context_is_frozen_and_has_one_field() -> None:
    context = ApplicationContext(settings=ProjectSettings(database_url="sqlite:///:memory:"))
    assert [field.name for field in dataclasses.fields(context)] == ["settings"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.settings = ProjectSettings(database_url="sqlite:///:memory:")  # type: ignore[misc]
