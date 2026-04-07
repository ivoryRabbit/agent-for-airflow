import json
import os
from typing import Any, Awaitable, Callable

import anthropic

from app.llm.base import LLMProvider, ToolDefinition


class ClaudeProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")

    async def analyze(self, system: str, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def run_with_tools(
        self,
        system: str,
        prompt: str,
        tools: list[ToolDefinition],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> str:
        claude_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": t.properties,
                    "required": t.required,
                },
            }
            for t in tools
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        while True:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                tools=claude_tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_blocks) or "Done."

            if response.stop_reason != "tool_use":
                return "Unexpected response from the model."

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = await executor(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
