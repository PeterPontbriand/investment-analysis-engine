"""Unit tests for Pydantic validator."""

import json

import pytest
from pydantic import BaseModel, ConfigDict

from src.schema.exceptions import SchemaValidationError
from src.schema.models import PlanResponse, SynthesisResponse, ToolCallResponse
from src.schema.validator import (
    ValidationErrorType,
    ValidationResult,
    build_retry_messages,
    classify_validation_error,
    validate_response,
    validate_with_schema,
)


class SimpleModel(BaseModel):
    name: str
    value: int


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


def test_validate_response_success():
    """Test successful validation."""
    response = '{"name": "test", "value": 42}'
    result = validate_response(response, SimpleModel)

    assert result.valid is True
    assert isinstance(result.data, SimpleModel)
    assert result.data.name == "test"
    assert result.data.value == 42
    assert result.errors == []
    assert result.error_type is None


def test_validate_response_malformed_json():
    """Test handling of malformed JSON."""
    response = '{"name": "test", "value": 42'  # Missing closing brace
    result = validate_response(response, SimpleModel)

    assert result.valid is False
    assert result.error_type == ValidationErrorType.MALFORMED_JSON
    assert result.is_recoverable is True
    assert len(result.errors) == 1


def test_validate_response_missing_field():
    """Test validation with missing required field."""
    response = '{"name": "test"}'  # Missing 'value'
    result = validate_response(response, SimpleModel)

    assert result.valid is False
    assert result.error_type == ValidationErrorType.MISSING_FIELD
    assert result.is_recoverable is True
    assert len(result.errors) >= 1


def test_validate_response_invalid_type():
    """Test validation with wrong type."""
    response = '{"name": "test", "value": "not an int"}'
    result = validate_response(response, SimpleModel)

    assert result.valid is False
    assert result.error_type == ValidationErrorType.INVALID_TYPE
    assert result.is_recoverable is True


def test_validate_response_strict_mode_extra_fields():
    """Test that extra fields are rejected when model forbids them."""
    response = '{"name": "test", "extra": "field"}'
    result = validate_response(response, StrictModel, strict=True)

    assert result.valid is False
    assert result.error_type == ValidationErrorType.EXTRA_FIELD
    assert result.is_recoverable is True


def test_tool_call_extra_fields_rejected():
    """ToolCallResponse has extra=forbid; extras must fail validation."""
    response = json.dumps(
        {
            "tool_name": "get_price",
            "tool_args": {"symbol": "AAPL"},
            "extra_field": "should be rejected",
        }
    )
    result = validate_response(response, ToolCallResponse, strict=True)
    assert result.valid is False
    assert result.error_type == ValidationErrorType.EXTRA_FIELD


def test_validate_with_schema_success():
    """Test validate_with_schema returns model on success."""
    response = '{"tool_name": "get_price", "tool_args": {"symbol": "AAPL"}}'
    result = validate_with_schema(response, ToolCallResponse)

    assert isinstance(result, ToolCallResponse)
    assert result.tool_name == "get_price"
    assert result.tool_args == {"symbol": "AAPL"}


def test_validate_with_schema_raises():
    """Test validate_with_schema raises on failure."""
    response = '{"tool_name": "", "tool_args": {}}'
    with pytest.raises(SchemaValidationError):
        validate_with_schema(response, ToolCallResponse)


def test_validate_tool_call_response():
    """Test validation of ToolCallResponse."""
    response = '{"tool_name": "get_price", "tool_args": {"symbol": "AAPL"}, "reasoning": "Need price"}'
    result = validate_response(response, ToolCallResponse)
    assert result.valid is True
    assert result.data.tool_name == "get_price"

    response = '{"tool_name": "", "tool_args": {}}'
    result = validate_response(response, ToolCallResponse)
    assert result.valid is False
    assert result.error_type == ValidationErrorType.VALUE_ERROR


def test_validate_plan_response():
    """Test validation of PlanResponse."""
    response = json.dumps(
        {
            "goal": "Analyze stock",
            "steps": [
                {
                    "step_id": "1",
                    "description": "Get data",
                    "tool_name": "fetch",
                    "dependencies": [],
                }
            ],
        }
    )
    result = validate_response(response, PlanResponse)
    assert result.valid is True
    assert len(result.data.steps) == 1

    response = json.dumps({"goal": "Analyze", "steps": []})
    result = validate_response(response, PlanResponse)
    assert result.valid is False


def test_validate_synthesis_response():
    """Test validation of SynthesisResponse."""
    response = json.dumps(
        {
            "summary": "Bullish outlook",
            "key_findings": ["Finding 1"],
            "confidence_score": 0.85,
        }
    )
    result = validate_response(response, SynthesisResponse)
    assert result.valid is True
    assert result.data.confidence_score == 0.85

    response = json.dumps(
        {
            "summary": "Test",
            "confidence_score": 1.5,
        }
    )
    result = validate_response(response, SynthesisResponse)
    assert result.valid is False
    assert result.error_type in (
        ValidationErrorType.VALUE_ERROR,
        ValidationErrorType.INVALID_TYPE,
    )


def test_classify_validation_error():
    """Test error classification via pytest.raises."""
    with pytest.raises(json.JSONDecodeError) as exc_info:
        json.loads("{invalid}")
    assert classify_validation_error(exc_info.value) == ValidationErrorType.MALFORMED_JSON


def test_validation_result_to_dict():
    """Test ValidationResult.to_dict()."""
    result = ValidationResult(
        valid=True,
        data={"test": "data"},
        errors=[],
        error_type=None,
        is_recoverable=True,
    )
    d = result.to_dict()
    assert d["valid"] is True
    assert d["error_type"] is None
    assert d["is_recoverable"] is True
    assert d["error_count"] == 0

    result = ValidationResult(
        valid=False,
        data=None,
        errors=[{"error": "test"}],
        error_type=ValidationErrorType.MALFORMED_JSON,
        is_recoverable=True,
    )
    d = result.to_dict()
    assert d["valid"] is False
    assert d["error_type"] == "malformed_json"
    assert d["error_count"] == 1


def test_error_summary():
    """error_summary produces readable text for retry prompts."""
    result = ValidationResult(
        valid=False,
        data={},
        errors=[
            {"loc": "tool_name", "msg": "Field required", "type": "missing"},
            {"loc": "tool_args", "msg": "Field required", "type": "missing"},
        ],
        error_type=ValidationErrorType.MISSING_FIELD,
    )
    summary = result.error_summary()
    assert "tool_name" in summary
    assert "missing_field" in summary or "Validation failed" in summary


def test_build_retry_messages():
    """build_retry_messages appends assistant turn (optional) and feedback."""
    original = [{"role": "user", "content": "Get price for AAPL"}]
    result = ValidationResult(
        valid=False,
        data={},
        errors=[{"loc": "tool_args", "msg": "Field required", "type": "missing"}],
        error_type=ValidationErrorType.MISSING_FIELD,
    )
    messages = build_retry_messages(
        original,
        result,
        assistant_content='{"tool_name": "get_price"}',
    )
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert "did not match the required schema" in messages[2]["content"]
    assert "tool_args" in messages[2]["content"]
