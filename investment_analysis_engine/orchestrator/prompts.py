from pathlib import Path

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
    """Build a system prompt with optional runtime rules and tool schemas."""

    base_instructions: str = DEFAULT_SYSTEM_PROMPT
    tool_schemas_json: str | None = None
    rules_path: Path | str | None = None  # optional override
    inject_runtime_rules: bool = True  # feature flag

    def build(self) -> str:
        """Build the system prompt, optionally injecting runtime rules and tool schemas."""
        prompt = self.base_instructions

        if self.inject_runtime_rules:
            rules = load_runtime_rules(self.rules_path)
            if rules:
                prompt += "\n\n# RUNTIME AGENT RULES\n" + rules

        if self.tool_schemas_json:
            prompt += f"\n\nAVAILABLE TOOLS SCHEMA:\n{self.tool_schemas_json}\n"
            prompt += "Respond with JSON tool invocations matching the defined tool schemas."

        return prompt
