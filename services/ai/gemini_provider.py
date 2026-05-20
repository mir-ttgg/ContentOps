from __future__ import annotations

import asyncio

import google.generativeai as genai
from loguru import logger

from services.ai._format import normalize_post_html
from services.ai._parse import parse_moderation_json
from services.ai.base import (
    GENERATION_SYSTEM,
    MODERATION_SYSTEM,
    AIProvider,
    ModerationResult,
    ModerationVerdict,
)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        super().__init__(model)
        genai.configure(api_key=api_key)
        self._api_key = api_key

    def _client(self, system: str):
        return genai.GenerativeModel(self.model, system_instruction=system)

    async def _chat(self, system: str, user: str) -> str:
        model = self._client(system)
        # google-generativeai exposes a sync method; offload to a thread
        resp = await asyncio.to_thread(model.generate_content, user)
        return (resp.text or "").strip()

    async def generate_post(self, topic: str, channel_context: str) -> str:
        prompt = f"Channel context:\n{channel_context}\n\nWrite a post about: {topic}"
        return normalize_post_html(await self._chat(GENERATION_SYSTEM, prompt))

    async def improve_post(self, text: str) -> str:
        prompt = f"Improve the following post — sharpen the hook, tighten phrasing, keep the meaning:\n\n{text}"
        return normalize_post_html(await self._chat(GENERATION_SYSTEM, prompt))

    async def check_content(self, text: str) -> ModerationResult:
        try:
            raw = await self._chat(MODERATION_SYSTEM, text)
        except Exception as e:
            logger.warning("Gemini moderation failed: {}", e)
            return ModerationResult(ModerationVerdict.FLAG, reason=f"AI error: {e}")
        return parse_moderation_json(raw)
