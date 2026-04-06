import json
import os
from typing import Any, Awaitable, Callable

import openai

from .base import LLMProvider, ToolDefinition


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI()
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    async def analyze(self, system: str, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def run_with_tools(
        self,
        system: str,
        prompt: str,
        tools: list[ToolDefinition],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> str:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": t.properties,
                        "required": t.required,
                    },
                },
            }
            for t in tools
        ]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        while True:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=1024,
                tools=oai_tools,
                messages=messages,
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return choice.message.content or "Done."

            if choice.finish_reason != "tool_calls":
                return "Unexpected response from the model."

            messages.append(choice.message)

            for tool_call in choice.message.tool_calls:
                inputs = json.loads(tool_call.function.arguments)
                result = await executor(tool_call.function.name, inputs)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
