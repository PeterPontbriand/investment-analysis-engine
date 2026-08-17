"""Integration tests for native schema enforcement with Ollama.

These tests verify the end-to-end flow of schema-constrained generation,
including constraint building, API interaction (mocked), and validation.
"""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from src.schema.constraint import format_schema_for_ollama
from src.schema.models import PlanResponse, SynthesisResponse, ToolCallResponse
from src.schema.validator import build_retry_messages, validate_response


@pytest.fixture
def mock_ollama_response():
    """Fixture for a mock Ollama response."""

    def _make_response(content: dict):
        return Mock(message=Mock(content=json.dumps(content)))

    return _make_response


@pytest.fixture
def mock_ollama_chat():
    """Fixture to mock ollama.chat without requiring the ollama package."""
    fake = ModuleType("ollama")
    fake.chat = Mock()
    with (
        patch.dict(sys.modules, {"ollama": fake}),
        patch.object(fake, "chat") as mock_chat,
    ):
        yield mock_chat


class TestNativeEnforcement:
    """Integration tests for native schema enforcement."""

    def test_tool_call_with_schema_constraint(self, mock_ollama_chat, mock_ollama_response):
        """Test a tool call generation with schema constraint."""
        expected_response = {
            "tool_name": "get_price",
            "tool_args": {"symbol": "AAPL"},
            "reasoning": "Fetch current price",
        }
        mock_ollama_chat.return_value = mock_ollama_response(expected_response)

        params = format_schema_for_ollama(ToolCallResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Get price for AAPL"}],
            **params,
        )

        result = validate_response(response.message.content, ToolCallResponse)
        assert result.valid is True
        assert result.data.tool_name == "get_price"
        assert result.data.tool_args["symbol"] == "AAPL"

        call_kwargs = mock_ollama_chat.call_args[1]
        assert "format" in call_kwargs
        assert isinstance(call_kwargs["format"], dict)
        assert call_kwargs["format"]["type"] == "object"
        assert "schema" not in call_kwargs
        assert "strict" not in call_kwargs

    def test_plan_with_schema_constraint(self, mock_ollama_chat, mock_ollama_response):
        """Test a plan generation with schema constraint."""
        expected_response = {
            "goal": "Analyze Tesla stock",
            "steps": [
                {
                    "step_id": "1",
                    "description": "Get price",
                    "tool_name": "get_price",
                    "dependencies": [],
                },
                {
                    "step_id": "2",
                    "description": "Get fundamentals",
                    "tool_name": "get_fundamentals",
                    "dependencies": ["1"],
                },
            ],
        }
        mock_ollama_chat.return_value = mock_ollama_response(expected_response)

        params = format_schema_for_ollama(PlanResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Plan analysis for TSLA"}],
            **params,
        )

        result = validate_response(response.message.content, PlanResponse)
        assert result.valid is True
        assert len(result.data.steps) == 2
        assert result.data.goal == "Analyze Tesla stock"

    def test_synthesis_with_schema_constraint(self, mock_ollama_chat, mock_ollama_response):
        """Test a synthesis generation with schema constraint."""
        expected_response = {
            "summary": "Tesla shows strong growth potential",
            "key_findings": ["Revenue up 20%", "Margin expanding"],
            "recommendation": "BUY",
            "confidence_score": 0.78,
            "metrics": {"pe_ratio": 45.2, "revenue_growth": 0.20},
        }
        mock_ollama_chat.return_value = mock_ollama_response(expected_response)

        params = format_schema_for_ollama(SynthesisResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Synthesize TSLA analysis"}],
            **params,
        )

        result = validate_response(response.message.content, SynthesisResponse)
        assert result.valid is True
        assert result.data.confidence_score == 0.78
        assert result.data.recommendation == "BUY"

    def test_schema_violation_handling(self, mock_ollama_chat, mock_ollama_response):
        """Test handling of schema violations (recoverable)."""
        bad_response = {"tool_name": "get_price", "unexpected": True}
        mock_ollama_chat.return_value = mock_ollama_response(bad_response)

        params = format_schema_for_ollama(ToolCallResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Get price"}],
            **params,
        )

        result = validate_response(response.message.content, ToolCallResponse)
        assert result.valid is False
        assert result.is_recoverable is True
        assert result.error_type is not None

    def test_malformed_json_handling(self, mock_ollama_chat):
        """Test handling of malformed JSON response."""
        mock_ollama_chat.return_value = Mock(message=Mock(content="This is not JSON"))

        params = format_schema_for_ollama(ToolCallResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Get price"}],
            **params,
        )

        result = validate_response(response.message.content, ToolCallResponse)
        assert result.valid is False
        assert result.is_recoverable is True
        assert result.error_type.value == "malformed_json"

    def test_strict_mode_rejects_extra_fields(self, mock_ollama_chat, mock_ollama_response):
        """Test that models with extra=forbid reject unexpected fields."""
        response_with_extra = {
            "tool_name": "get_price",
            "tool_args": {"symbol": "AAPL"},
            "extra_field": "should be rejected",
            "reasoning": "Some reasoning",
        }
        mock_ollama_chat.return_value = mock_ollama_response(response_with_extra)

        params = format_schema_for_ollama(ToolCallResponse, strict=True)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Get price"}],
            **params,
        )

        result = validate_response(response.message.content, ToolCallResponse, strict=True)
        assert result.valid is False
        assert result.error_type.value == "extra_field"

    def test_fallback_to_pydantic_validation(self, mock_ollama_chat, mock_ollama_response):
        """Test that Pydantic validation acts as second-line defense."""
        response_with_invalid_confidence = {
            "summary": "Test",
            "key_findings": [],
            "confidence_score": 1.5,
        }
        mock_ollama_chat.return_value = mock_ollama_response(response_with_invalid_confidence)

        params = format_schema_for_ollama(SynthesisResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Synthesize"}],
            **params,
        )

        result = validate_response(response.message.content, SynthesisResponse)
        assert result.valid is False
        assert result.error_type is not None

    def test_recoverable_error_does_not_crash(self, mock_ollama_chat, mock_ollama_response):
        """Schema violations are transient and do not crash the process."""
        bad_response = {"invalid": "data"}
        mock_ollama_chat.return_value = mock_ollama_response(bad_response)

        params = format_schema_for_ollama(ToolCallResponse)
        response = mock_ollama_chat(
            model="llama3",
            messages=[{"role": "user", "content": "Get price"}],
            **params,
        )

        result = validate_response(response.message.content, ToolCallResponse)
        assert result.valid is False
        assert result.is_recoverable is True

    def test_end_to_end_with_retry_flow(self, mock_ollama_chat, mock_ollama_response):
        """Test the full flow with retry on validation failure using build_retry_messages."""
        bad_response = {"tool_name": "get_price", "extra": True}
        good_response = {
            "tool_name": "get_price",
            "tool_args": {"symbol": "AAPL"},
            "reasoning": "Retry successful",
        }

        mock_ollama_chat.side_effect = [
            mock_ollama_response(bad_response),
            mock_ollama_response(good_response),
        ]

        params = format_schema_for_ollama(ToolCallResponse)
        original_messages = [{"role": "user", "content": "Get price"}]

        response1 = mock_ollama_chat(
            model="llama3",
            messages=original_messages,
            **params,
        )
        result1 = validate_response(response1.message.content, ToolCallResponse)
        assert result1.valid is False

        retry_messages = build_retry_messages(
            original_messages,
            result1,
            assistant_content=response1.message.content,
        )
        response2 = mock_ollama_chat(
            model="llama3",
            messages=retry_messages,
            **params,
        )
        result2 = validate_response(response2.message.content, ToolCallResponse)

        assert result2.valid is True
        assert result2.data.tool_name == "get_price"
        assert result2.data.tool_args == {"symbol": "AAPL"}

        second_call_kwargs = mock_ollama_chat.call_args_list[1][1]
        assert len(second_call_kwargs["messages"]) == 3
