import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class AgentStepResult(BaseModel):
    """Container for single-step orchestration results and tool outputs."""

    model_config = ConfigDict(frozen=True)
    step_number: int
    message: ChatMessage
    executed_tools: list[ToolCallResult] = Field(default_factory=list)
    is_terminal: bool = False
