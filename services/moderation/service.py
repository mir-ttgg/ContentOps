from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from loguru import logger

from models import Channel
from services.ai.base import AIProvider, ModerationVerdict


class ModerationDecision(str, enum.Enum):
    PUBLISH = "publish"            # safe to publish immediately
    NEEDS_APPROVAL = "needs_approval"  # send to admin queue
    AUTO_DELETE = "auto_delete"    # block, log, don't publish


@dataclass
class ModerationOutcome:
    decision: ModerationDecision
    reason: str = ""
    matched: list[str] | None = None


class ModerationService:
    """Combines stopword filtering with optional AI content check.

    Rules:
      - If text matches a stopword/regex: AUTO_DELETE (if channel.auto_delete) else NEEDS_APPROVAL.
      - Else if AI verdict == BLOCK: AUTO_DELETE (if channel.auto_delete) else NEEDS_APPROVAL.
      - Else if AI verdict == FLAG: NEEDS_APPROVAL.
      - Else if channel.approval_required: NEEDS_APPROVAL.
      - Else: PUBLISH.
    """

    def __init__(self, ai_provider: AIProvider | None = None):
        self.ai = ai_provider

    def match_stopwords(self, text: str, stopwords: list[str]) -> list[str]:
        matched: list[str] = []
        if not text or not stopwords:
            return matched
        lowered = text.lower()
        for token in stopwords:
            token = token.strip()
            if not token:
                continue
            # heuristic: treat tokens with regex metacharacters as regex
            if any(ch in token for ch in r".*+?[]()|\^$"):
                try:
                    if re.search(token, text, flags=re.IGNORECASE):
                        matched.append(token)
                except re.error:
                    if token.lower() in lowered:
                        matched.append(token)
            else:
                if token.lower() in lowered:
                    matched.append(token)
        return matched

    async def evaluate(self, text: str, channel: Channel) -> ModerationOutcome:
        # 1. Stopwords
        matched = self.match_stopwords(text, channel.stopwords)
        if matched:
            reason = f"stopwords: {', '.join(matched)}"
            if channel.auto_delete:
                return ModerationOutcome(ModerationDecision.AUTO_DELETE, reason, matched)
            return ModerationOutcome(ModerationDecision.NEEDS_APPROVAL, reason, matched)

        # 2. AI moderation (only if configured and channel asks for auto-delete or approval)
        if self.ai and (channel.auto_delete or channel.approval_required):
            try:
                result = await self.ai.check_content(text)
            except Exception as e:
                logger.warning("AI moderation failed: {}", e)
                result = None
            if result is not None:
                if result.verdict == ModerationVerdict.BLOCK:
                    decision = (
                        ModerationDecision.AUTO_DELETE
                        if channel.auto_delete
                        else ModerationDecision.NEEDS_APPROVAL
                    )
                    return ModerationOutcome(decision, f"AI block: {result.reason}", result.categories)
                if result.verdict == ModerationVerdict.FLAG:
                    return ModerationOutcome(
                        ModerationDecision.NEEDS_APPROVAL,
                        f"AI flag: {result.reason}",
                        result.categories,
                    )

        # 3. Approval mode
        if channel.approval_required:
            return ModerationOutcome(ModerationDecision.NEEDS_APPROVAL, "approval mode")

        return ModerationOutcome(ModerationDecision.PUBLISH)
