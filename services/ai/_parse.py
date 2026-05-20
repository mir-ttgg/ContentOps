from __future__ import annotations

import json
import re

from services.ai.base import ModerationResult, ModerationVerdict


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_moderation_json(raw: str) -> ModerationResult:
    if not raw:
        return ModerationResult(ModerationVerdict.FLAG, reason="empty AI response")
    match = _JSON_BLOCK.search(raw)
    if not match:
        return ModerationResult(ModerationVerdict.FLAG, reason="no JSON in AI response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return ModerationResult(ModerationVerdict.FLAG, reason=f"bad JSON: {e}")

    verdict_str = str(data.get("verdict", "flag")).lower()
    try:
        verdict = ModerationVerdict(verdict_str)
    except ValueError:
        verdict = ModerationVerdict.FLAG
    return ModerationResult(
        verdict=verdict,
        reason=str(data.get("reason", "")),
        categories=list(data.get("categories") or []),
    )
