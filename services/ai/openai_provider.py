from __future__ import annotations

from loguru import logger
from openai import AsyncOpenAI

from services.ai._parse import parse_moderation_json
from services.ai.base import (
    GENERATION_SYSTEM,
    MODERATION_SYSTEM,
    AIProvider,
    ModerationResult,
    ModerationVerdict,
)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str):
        super().__init__(model)
        self.client = AsyncOpenAI(api_key=api_key)

    async def _chat(self, system: str, user: str, *, json_mode: bool = False) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self.client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    async def generate_post(self, topic: str, channel_context: str) -> str:
        prompt = f"Channel context:\n{channel_context}\n\nWrite a post about: {topic}"
        return await self._chat(GENERATION_SYSTEM, prompt)

    async def improve_post(self, text: str) -> str:
        prompt = f"Improve the following post — sharpen the hook, tighten phrasing, keep the meaning:\n\n{text}"
        return await self._chat(GENERATION_SYSTEM, prompt)

    async def check_content(self, text: str) -> ModerationResult:
        try:
            raw = await self._chat(MODERATION_SYSTEM, text, json_mode=True)
        except Exception as e:
            logger.warning("OpenAI moderation failed: {}", e)
            return ModerationResult(ModerationVerdict.FLAG, reason=f"AI error: {e}")
        return parse_moderation_json(raw)
