import json
import os
from typing import Any, Awaitable, Callable

import google.generativeai as genai
from google.generativeai import protos

from app.llm.base import LLMProvider, ToolDefinition


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        self._model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    def _to_gemini_tools(self, tools: list[ToolDefinition]) -> list[protos.Tool]:
        declarations = [
            protos.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=protos.Schema(
                    type=protos.Type.OBJECT,
                    properties={
                        k: protos.Schema(
                            type=_json_type(v.get("type", "string")),
                            description=v.get("description", ""),
                            enum=v.get("enum", []),
                        )
                        for k, v in t.properties.items()
                    },
                    required=t.required,
                ),
            )
            for t in tools
        ]
        return [protos.Tool(function_declarations=declarations)]

    async def analyze(self, system: str, prompt: str) -> str:
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
        )
        response = await model.generate_content_async(prompt)
        return _extract_text(response)

    async def run_with_tools(
        self,
        system: str,
        prompt: str,
        tools: list[ToolDefinition],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> str:
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
            tools=self._to_gemini_tools(tools),
        )
        chat = model.start_chat()
        response = await chat.send_message_async(prompt)

        while True:
            fn_calls = [
                p.function_call
                for p in response.parts
                if p.function_call.name  # empty name means no function call
            ]

            if not fn_calls:
                return _extract_text(response)

            fn_responses = []
            for fc in fn_calls:
                result = await executor(fc.name, dict(fc.args))
                fn_responses.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=fc.name,
                            response={"result": json.dumps(result)},
                        )
                    )
                )

            response = await chat.send_message_async(fn_responses)


def _extract_text(response) -> str:
    """Safely extract text from a Gemini response without using the .text quick accessor."""
    try:
        parts = response.candidates[0].content.parts
        text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
        return "\n".join(text_parts) if text_parts else "Done."
    except (IndexError, AttributeError):
        return "Done."


def _json_type(t: str) -> protos.Type:
    return {
        "string": protos.Type.STRING,
        "integer": protos.Type.INTEGER,
        "number": protos.Type.NUMBER,
        "boolean": protos.Type.BOOLEAN,
        "object": protos.Type.OBJECT,
        "array": protos.Type.ARRAY,
    }.get(t, protos.Type.STRING)
