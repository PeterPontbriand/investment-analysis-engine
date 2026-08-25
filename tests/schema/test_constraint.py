"""Unit tests for schema constraint building."""

import pytest
from pydantic import BaseModel, Field

from src.schema.constraint import (
    SchemaConstraint,
    build_schema_constraint,
    detect_ollama_schema_support,
    format_schema_for_ollama,
)
from src.schema.exceptions import SchemaConstraintError
from src.schema.models import PlanResponse, ToolCallResponse


class SimpleModel(BaseModel):
    name: str = Field(..., description="Name field")
    value: int = Field(..., description="Value field")


def test_build_schema_constraint() -> None:
    """Test building a schema constraint from a Pydantic model."""
    constraint = build_schema_constraint(SimpleModel)

    assert isinstance(constraint, SchemaConstraint)
    assert constraint.model_class == SimpleModel
    assert constraint.strict is True
    assert "type" in constraint.schema_dict
    assert constraint.schema_dict["type"] == "object"
    assert "properties" in constraint.schema_dict
    assert "name" in constraint.schema_dict["properties"]
    assert "value" in constraint.schema_dict["properties"]


def test_build_schema_constraint_additional_properties() -> None:
    """Test building with additional properties disabled."""
    constraint = build_schema_constraint(SimpleModel, additional_properties=False)
    assert constraint.schema_dict.get("additionalProperties") is False


def test_build_schema_constraint_required_fields() -> None:
    """Test that required fields are properly set."""
    constraint = build_schema_constraint(SimpleModel)
    assert "required" in constraint.schema_dict
    assert set(constraint.schema_dict["required"]) == {"name", "value"}


def test_schema_constraint_to_ollama_format() -> None:
    """Test converting to Ollama format value (the schema object itself)."""
    constraint = build_schema_constraint(SimpleModel)
    ollama_value = constraint.to_ollama_format()

    assert isinstance(ollama_value, dict)
    assert ollama_value["type"] == "object"
    assert "properties" in ollama_value
    assert ollama_value is constraint.schema_dict or ollama_value == constraint.schema_dict


def test_schema_constraint_to_ollama_params() -> None:
    """Test getting full Ollama parameters (correct contract)."""
    constraint = build_schema_constraint(SimpleModel)
    params = constraint.to_ollama_params()

    assert set(params.keys()) == {"format"}
    assert isinstance(params["format"], dict)
    assert params["format"]["type"] == "object"
    assert "schema" not in params
    assert "strict" not in params


def test_format_schema_for_ollama_convenience() -> None:
    """Test the convenience function returns correct kwargs."""
    params = format_schema_for_ollama(ToolCallResponse)

    assert set(params.keys()) == {"format"}
    schema = params["format"]
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "tool_name" in schema["properties"]
    assert "tool_args" in schema["properties"]
    assert schema.get("additionalProperties") is False


def test_nested_additional_properties() -> None:
    """AdditionalProperties is applied to nested object schemas too."""
    constraint = build_schema_constraint(PlanResponse, additional_properties=False)
    schema = constraint.schema_dict
    assert schema.get("additionalProperties") is False
    defs = schema.get("$defs") or schema.get("definitions") or {}
    for defn in defs.values():
        if defn.get("type") == "object" or "properties" in defn:
            assert defn.get("additionalProperties") is False


def test_detect_ollama_schema_support() -> None:
    """Test Ollama version detection (schema support ~0.5+)."""
    assert detect_ollama_schema_support("0.5.0") is True
    assert detect_ollama_schema_support("0.5.1") is True
    assert detect_ollama_schema_support("0.6.0") is True
    assert detect_ollama_schema_support("1.0.0") is True
    assert detect_ollama_schema_support("ollama version is 0.5.4") is True

    assert detect_ollama_schema_support("0.1.30") is False
    assert detect_ollama_schema_support("0.1.29") is False
    assert detect_ollama_schema_support("0.4.9") is False
    assert detect_ollama_schema_support("0.3.0") is False


def test_detect_ollama_schema_support_with_version_suffix() -> None:
    """Test version detection with suffixes."""
    assert detect_ollama_schema_support("0.5.0-rc1") is True
    assert detect_ollama_schema_support("0.4.9-dev") is False


def test_detect_ollama_schema_support_unknown_states() -> None:
    """Test UNKNOWN state (None) for missing/unparseable versions."""
    assert detect_ollama_schema_support(None) is None
    assert detect_ollama_schema_support("") is None
    assert detect_ollama_schema_support("   ") is None
    assert detect_ollama_schema_support("abc") is None
    assert detect_ollama_schema_support("1.x.0") is None


def test_detect_ollama_schema_support_edge_cases() -> None:
    """Test edge cases: single component, non-string, prefix variants."""
    assert detect_ollama_schema_support("0") is None
    assert detect_ollama_schema_support(123) is None  # type: ignore[arg-type]
    assert detect_ollama_schema_support("ollama version 0.4.2") is False
    assert detect_ollama_schema_support("version 1.0.0") is True


def test_build_schema_constraint_error() -> None:
    """Test error handling when schema building fails."""

    class Broken:
        pass

    with pytest.raises(SchemaConstraintError):
        build_schema_constraint(Broken)  # type: ignore[arg-type]
