from __future__ import annotations

from config import settings
from services.ai.base import AIProvider


def build_provider(
    provider: str | None = None,
    model: str | None = None,
) -> AIProvider:
    name = (provider or settings.ai_provider).lower()
    chosen_model = model or settings.ai_model

    if name == "openai":
        from services.ai.openai_provider import OpenAIProvider
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return OpenAIProvider(settings.openai_api_key, chosen_model)
    if name == "claude":
        from services.ai.claude_provider import ClaudeProvider
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        return ClaudeProvider(settings.anthropic_api_key, chosen_model)
    if name == "gemini":
        from services.ai.gemini_provider import GeminiProvider
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        return GeminiProvider(settings.gemini_api_key, chosen_model)
    raise ValueError(f"Unknown AI provider: {name}")
