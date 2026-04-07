from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class ToolDefinition:
    name: str
    description: str
    # JSON Schema "properties" and "required" fields
    properties: dict[str, Any]
    required: list[str]


class LLMProvider(ABC):
    @abstractmethod
    async def analyze(self, system: str, prompt: str) -> str:
        """Single-turn text completion. No tool use."""
        ...

    @abstractmethod
    async def run_with_tools(
        self,
        system: str,
        prompt: str,
        tools: list[ToolDefinition],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> str:
        """Agentic loop with tool use.

        The provider handles the conversation loop internally.
        executor(tool_name, inputs) is called each time the model requests a tool.
        Returns the final text response.
        """
        ...
