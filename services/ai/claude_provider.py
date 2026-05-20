from __future__ import annotations

from anthropic import AsyncAnthropic
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


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str):
        super().__init__(model)
        self.client = AsyncAnthropic(api_key=api_key)

    async def _chat(self, system: str, user: str) -> str:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "".join(parts).strip()

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
            logger.warning("Claude moderation failed: {}", e)
            return ModerationResult(ModerationVerdict.FLAG, reason=f"AI error: {e}")
        return parse_moderation_json(raw)
