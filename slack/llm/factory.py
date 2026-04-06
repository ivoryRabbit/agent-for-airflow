import os

from .base import LLMProvider


def create_provider() -> LLMProvider:
    """Instantiate the LLM provider selected via LLM_PROVIDER env var.

    Supported values: 'claude' (default), 'openai'.
    """
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()

    if provider == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider()

    if provider == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider()

    if provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider()

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Supported values: 'claude', 'openai', 'gemini'."
    )
