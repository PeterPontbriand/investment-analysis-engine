from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.failure_codes import FailureReasonCode
from src.core.provider_failure_element import ProviderFailure
from src.orchestrator.reliability import ReliabilityFailure


class Role(StrEnum):
    """Represents different roles in the system."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCallRequest(BaseModel):
    """Represents a request to call a tool with specific arguments."""

    model_config = ConfigDict(frozen=True)
    call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    """Represents a message in the chat system."""

    model_config = ConfigDict(frozen=True)
    role: Role
    content: str
    name: str | None = None
    tool_calls: list[ToolCallRequest] | None = None
    tool_call_id: str | None = None

    def to_ollama_dict(self) -> dict[str, Any]:
        """Converts the ChatMessage object to a dictionary suitable for Ollama."""
        payload: dict[str, Any] = {"role": self.role.value, "content": self.content}
        if self.name:
            payload["name"] = self.name
        return payload


class ToolCallResult(BaseModel):
    """Represents the result of calling a tool."""

    model_config = ConfigDict(frozen=True)
    call_id: str
    tool_name: str
    success: bool
    result: Any
    error_message: str | None = None
    reason_code: FailureReasonCode | None = None
    provider_failure: ProviderFailure | None = None

    @model_validator(mode="after")
    def validate_failure_classification(self) -> ToolCallResult:
        """Require a stable code on a failure, and nothing on a success."""
        if self.success:
            if self.reason_code is not None or self.provider_failure is not None:
                raise ValueError("A successful tool call carries no failure code or provider failure.")
        elif self.reason_code is None:
            raise ValueError("A failed tool call requires a failure reason code.")
        elif self.provider_failure is not None and self.provider_failure.reason_code is not self.reason_code:
            raise ValueError("The provider failure must carry the same code as the failed tool call.")
        return self


class AgentStepResult(BaseModel):
    """Container for single-step orchestration results and tool outputs."""

    model_config = ConfigDict(frozen=True)
    step_number: int
    message: ChatMessage
    executed_tools: list[ToolCallResult] = Field(default_factory=list)
    is_terminal: bool = False
    failure: ReliabilityFailure | None = None

    @model_validator(mode="after")
    def validate_failure_state(self) -> AgentStepResult:
        """Require reliability failures to use the terminal result path."""
        if self.failure is not None and not self.is_terminal:
            raise ValueError("A reliability failure requires a terminal step result.")
        return self
