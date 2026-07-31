from pydantic import BaseModel

DEFAULT_SYSTEM_PROMPT = (
    "You are a financial analysis assistant. Your role is to analyze market data, execute \n"
    "requested quantitative calculations using available tools, and synthesize concise, \n"
    "accurate insights.\n\n"
    "Guidelines:\n"
    "- Rely strictly on tool outputs for quantitative calculations.\n"
    "- Do not invent financial metrics or report calculations not verified by tool execution.\n"
    "- Use available tools to answer queries when specific quantitative analysis is requested."
)


class SystemPromptBuilder(BaseModel):
    """Builds a system prompt for the agent, including base instructions and optional tool schemas."""

    base_instructions: str = DEFAULT_SYSTEM_PROMPT
    tool_schemas_json: str | None = None

    def build(self) -> str:
        """Constructs the system prompt, appending tool schemas if provided."""
        prompt = self.base_instructions
        if self.tool_schemas_json:
            prompt += f"\n\nAVAILABLE TOOLS SCHEMA:\n{self.tool_schemas_json}\n"
            prompt += "Respond with JSON tool invocations matching the defined tool schemas."
        return prompt
