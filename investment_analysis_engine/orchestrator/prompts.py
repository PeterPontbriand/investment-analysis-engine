from pydantic import BaseModel

from .rules import load_runtime_rules

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
    """Build a system prompt from the base instructions, the shipped runtime rules and optional tool schemas."""

    tool_schemas_json: str | None = None

    def build(self) -> str:
        """Build the system prompt: base instructions, the runtime rules and any tool schemas.

        Raises:
            OSError: If the runtime rules file shipped with the package cannot be read.
        """
        prompt = DEFAULT_SYSTEM_PROMPT

        rules = load_runtime_rules()
        if rules:
            prompt += "\n\n# RUNTIME AGENT RULES\n" + rules

        if self.tool_schemas_json:
            prompt += f"\n\nAVAILABLE TOOLS SCHEMA:\n{self.tool_schemas_json}\n"
            prompt += "Respond with JSON tool invocations matching the defined tool schemas."

        return prompt
