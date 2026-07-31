from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field

from src.core.llm_client import LLMClient
from src.core.tools.parser import ToolParser
from src.orchestrator.context import MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.types import AgentStepResult, ChatMessage, Role, ToolCallRequest


class OrchestratorConfig(BaseModel):
    """Configuration for the AgentOrchestrator, including maximum steps, model name, and temperature settings."""

    max_steps: int = Field(default=10, ge=1, le=50)
    model_name: str = "qwen2.5-coder:latest"
    temperature: float = 0.0


class AgentOrchestrator:
    """Orchestrates the interaction between the LLM, tool dispatcher, and tool call parser."""

    def __init__(
        self,
        llm_client: LLMClient,
        dispatcher: AsyncToolDispatcher,
        parser: ToolParser,
        config: OrchestratorConfig | None = None,
    ) -> None:
        """Initializes the AgentOrchestrator.

        Uses the provided LLM client, tool dispatcher, parser, and optional configuration.
        """
        self.llm_client = llm_client
        self.dispatcher = dispatcher
        self.parser = parser
        self.config = config or OrchestratorConfig()

    async def run_stream(self, prompt: str, context: MessageContext) -> AsyncGenerator[AgentStepResult, None]:
        """Runs the orchestration loop, yielding AgentStepResult for each step.

        Continues until task completion or maximum steps are reached.
        """
        context.add_message(ChatMessage(role=Role.USER, content=prompt))

        for step in range(1, self.config.max_steps + 1):
            raw_response = await self.llm_client.generate(
                prompt=context.to_ollama_payload(),
                model=self.config.model_name,
                temperature=self.config.temperature,
            )

            tool_requests: list[ToolCallRequest] = []
            try:
                parsed = self.parser.parse(raw_response)
                tool_requests.append(ToolCallRequest(tool_name=parsed.tool_name, arguments=parsed.arguments))
            except Exception:
                # Proceed cleanly if raw_response is non-tool text or fails parsing
                pass

            assistant_msg = ChatMessage(
                role=Role.ASSISTANT, content=raw_response, tool_calls=tool_requests if tool_requests else None
            )
            context.add_message(assistant_msg)

            if not tool_requests:
                yield AgentStepResult(step_number=step, message=assistant_msg, is_terminal=True)
                return

            tool_results = []
            for request in tool_requests:
                response = await self.dispatcher.dispatch(request)
                tool_results.append(response)
                tool_msg_content = str(response.result) if response.success else f"Error: {response.error_message}"
                context.add_message(
                    ChatMessage(
                        role=Role.TOOL, name=response.tool_name, content=tool_msg_content, tool_call_id=response.call_id
                    )
                )

            yield AgentStepResult(
                step_number=step, message=assistant_msg, executed_tools=tool_results, is_terminal=False
            )

        yield AgentStepResult(
            step_number=self.config.max_steps,
            message=ChatMessage(role=Role.ASSISTANT, content="Exceeded maximum iteration steps."),
            is_terminal=True,
        )
