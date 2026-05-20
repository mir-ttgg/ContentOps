from __future__ import annotations

import pytest

from models import Channel
from services.ai.base import AIProvider, ModerationResult, ModerationVerdict
from services.moderation.service import ModerationDecision, ModerationService


def make_channel(**settings) -> Channel:
    ch = Channel(
        tg_channel_id=-100,
        name="test",
        username=None,
        system_prompt="",
        settings_json={
            "approval_required": False,
            "auto_post": False,
            "auto_delete": False,
            "stopwords": [],
            **settings,
        },
    )
    return ch


class FakeAI(AIProvider):
    name = "fake"

    def __init__(self, verdict: ModerationVerdict, reason: str = ""):
        super().__init__("fake")
        self._verdict = verdict
        self._reason = reason

    async def generate_post(self, topic, channel_context):
        return "x"

    async def improve_post(self, text):
        return text

    async def check_content(self, text):
        return ModerationResult(self._verdict, self._reason)


@pytest.mark.asyncio
async def test_publish_when_clean_and_no_approval():
    svc = ModerationService(ai_provider=None)
    ch = make_channel()
    out = await svc.evaluate("hello world", ch)
    assert out.decision == ModerationDecision.PUBLISH


@pytest.mark.asyncio
async def test_approval_required_holds_post():
    svc = ModerationService(ai_provider=None)
    ch = make_channel(approval_required=True)
    out = await svc.evaluate("hello", ch)
    assert out.decision == ModerationDecision.NEEDS_APPROVAL


@pytest.mark.asyncio
async def test_stopword_match_routes_to_approval_when_no_auto_delete():
    svc = ModerationService(ai_provider=None)
    ch = make_channel(stopwords=["spam"])
    out = await svc.evaluate("buy spam now!", ch)
    assert out.decision == ModerationDecision.NEEDS_APPROVAL
    assert out.matched == ["spam"]


@pytest.mark.asyncio
async def test_stopword_auto_delete_when_enabled():
    svc = ModerationService(ai_provider=None)
    ch = make_channel(stopwords=["scam"], auto_delete=True)
    out = await svc.evaluate("this is a SCAM offer", ch)
    assert out.decision == ModerationDecision.AUTO_DELETE


@pytest.mark.asyncio
async def test_regex_stopword():
    svc = ModerationService(ai_provider=None)
    ch = make_channel(stopwords=[r".*crypto.*"], auto_delete=True)
    out = await svc.evaluate("free crypto airdrop", ch)
    assert out.decision == ModerationDecision.AUTO_DELETE


@pytest.mark.asyncio
async def test_ai_block_with_auto_delete():
    svc = ModerationService(FakeAI(ModerationVerdict.BLOCK, "bad"))
    ch = make_channel(auto_delete=True)
    out = await svc.evaluate("anything", ch)
    assert out.decision == ModerationDecision.AUTO_DELETE


@pytest.mark.asyncio
async def test_ai_flag_routes_to_approval():
    svc = ModerationService(FakeAI(ModerationVerdict.FLAG, "borderline"))
    ch = make_channel(approval_required=True)
    out = await svc.evaluate("anything", ch)
    assert out.decision == ModerationDecision.NEEDS_APPROVAL
