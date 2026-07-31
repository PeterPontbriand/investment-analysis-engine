from typing import Any

from pydantic import BaseModel, Field

from src.orchestrator.types import ChatMessage, Role


class ContextConfig(BaseModel):
    """Configuration for the MessageContext, including maximum history messages and system prompt preservation."""

    max_history_messages: int = Field(default=30, ge=5, le=100)
    preserve_system_prompt: bool = True


class MessageContext:
    """Manages the conversation context, including messages and system prompt handling, for the agent orchestrator."""

    def __init__(self, config: ContextConfig | None = None) -> None:
        """Initializes the MessageContext with an optional configuration."""
        self.config = config or ContextConfig()
        self._messages: list[ChatMessage] = []

    def set_system_prompt(self, prompt: str) -> None:
        """Sets or updates the system prompt in the message context."""
        system_msg = ChatMessage(role=Role.SYSTEM, content=prompt)
        if self._messages and self._messages[0].role == Role.SYSTEM:
            self._messages[0] = system_msg
        else:
            self._messages.insert(0, system_msg)

    def add_message(self, message: ChatMessage) -> None:
        """Adds a new message to the context, truncating history if necessary."""
        self._messages.append(message)
        self._truncate_if_needed()

    def get_messages(self) -> list[ChatMessage]:
        """Returns the current list of messages in the context."""
        return list(self._messages)

    def to_ollama_payload(self) -> list[dict[str, Any]]:
        """Converts the message context to a list of dictionaries suitable for Ollama."""
        return [m.to_ollama_dict() for m in self._messages]

    def _truncate_if_needed(self) -> None:
        """Truncates the message history if it exceeds the maximum allowed messages.

        Preserves the system prompt if configured.
        """
        if len(self._messages) <= self.config.max_history_messages:
            return

        has_system = len(self._messages) > 0 and self._messages[0].role == Role.SYSTEM
        overflow = len(self._messages) - self.config.max_history_messages

        if has_system:
            system_msg = self._messages[0]
            # Slicing from 1 + overflow guarantees system_msg stays at index 0
            self._messages = [system_msg] + self._messages[1 + overflow :]
        else:
            self._messages = self._messages[overflow:]
