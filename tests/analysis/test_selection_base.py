"""Focused tests for the shared selection base."""

from typing import Literal

import pytest
from pydantic import ValidationError

from investment_analysis_engine.analysis.selection_base import FrozenSelection


class _Selection(FrozenSelection):
    """Test-local selection with a versioned literal and one ordinary field."""

    config_schema_version: Literal[1]
    label: str


def test_integer_config_schema_version_is_accepted() -> None:
    selection = _Selection(config_schema_version=1, label="a")

    assert selection.config_schema_version == 1


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_non_integer_config_schema_version_is_rejected(value: object) -> None:
    with pytest.raises(ValidationError, match="config_schema_version must be an integer."):
        _Selection.model_validate({"config_schema_version": value, "label": "a"})


def test_selection_is_frozen() -> None:
    selection = _Selection(config_schema_version=1, label="a")

    with pytest.raises(ValidationError):
        selection.label = "b"


def test_unknown_extra_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _Selection.model_validate({"config_schema_version": 1, "label": "a", "extra": 1})
